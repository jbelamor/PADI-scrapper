"""Lógica de negocio: plazas por usuario, distancias y detección de novedades."""
import logging
from collections import defaultdict
from datetime import date

from . import geo
from .api import PadiClient
from .catalog import Catalog, Centros
from .storage import Storage

log = logging.getLogger(__name__)


class PadiService:
    def __init__(self, db_path):
        self.storage = Storage(db_path)
        self.catalog = Catalog(self.storage)
        self.centros = Centros(self.storage)
        self.api = PadiClient()
        self._catalog_refreshed_on = None

    async def close(self):
        await self.api.close()

    @staticmethod
    def user_tipos(user):
        return tuple((user or {}).get("tipos") or "E")

    # ---------- enriquecido ----------
    async def enrich(self, plazas, user):
        """Añade datos del centro y distancia al usuario. Ordena por distancia."""
        lat, lon = (user or {}).get("lat"), (user or {}).get("lon")
        for p in plazas:
            info = self.centros.get(p.get("ccentro")) or {}
            p["_centro"] = info
            p["_dist"] = None
            if lat is None:
                continue
            coords = await self.centros.coords(p.get("ccentro"), p.get("centro", ""),
                                               p.get("localidad", ""))
            if coords:
                straight, road, minutes = geo.estimate(lat, lon, *coords)
                p["_dist"] = {
                    "km": straight, "road_km": road, "min": minutes,
                    "maps": geo.maps_link(lat, lon, *coords),
                }
        plazas.sort(key=lambda p: (p["_dist"] is None,
                                   p["_dist"]["km"] if p["_dist"] else 0,
                                   p.get("centro", "")))
        return plazas

    # ---------- consulta bajo demanda ----------
    async def plazas_usuario(self, chat_id):
        user = self.storage.get_user(chat_id)
        cfuncs = self.storage.subs(chat_id)
        if not cfuncs:
            return [], {}
        plazas, fechas = await self.api.plazas(cfuncs, self.user_tipos(user))
        return await self.enrich(plazas, user), fechas

    async def plazas_ahora(self, chat_id, cfuncs):
        """Número de plazas abiertas ahora en unas especialidades (sin enriquecer)."""
        user = self.storage.get_user(chat_id)
        plazas, _ = await self.api.plazas(cfuncs, self.user_tipos(user))
        return len(plazas)

    # ---------- comprobación periódica ----------
    async def refresh_catalog(self):
        """Una vez al día, añade al catálogo especialidades que aparezcan nuevas."""
        if self._catalog_refreshed_on == date.today():
            return
        for tipo in ("O", "E"):
            try:
                fc = await self.api.latest_date(tipo)
                if fc:
                    new = self.catalog.merge(await self.api.especialidades_publicadas(fc, tipo))
                    if new:
                        log.info("Especialidades nuevas en catálogo: %s", list(new))
            except Exception:
                log.exception("No se pudo refrescar el catálogo (%s)", tipo)
        self._catalog_refreshed_on = date.today()

    async def check_alerts(self):
        """Devuelve {chat_id: [plazas_nuevas_enriquecidas]} y las marca como vistas."""
        await self.refresh_catalog()
        users = self.storage.all_users(only_alerts=True)
        need = defaultdict(set)  # tipo -> cfuncs
        user_subs = {}
        for u in users:
            subs = self.storage.subs_full(u["chat_id"])
            user_subs[u["chat_id"]] = subs
            for t in self.user_tipos(u):
                need[t].update(cf for cf, _ in subs)

        by_key = defaultdict(list)  # (tipo, cfunc) -> plazas
        for tipo, cfuncs in need.items():
            if not cfuncs:
                continue
            plazas, _ = await self.api.plazas(sorted(cfuncs), (tipo,))
            for p in plazas:
                by_key[(tipo, p["cfunc"])].append(p)

        result = {}
        for u in users:
            chat_id = u["chat_id"]
            seen = self.storage.seen_ids(chat_id)
            fresh, to_mark, baselined = [], set(), []
            for cfunc, is_base in user_subs[chat_id]:
                for t in self.user_tipos(u):
                    for p in by_key.get((t, cfunc), []):
                        pid = p.get("idnsustituciones")
                        if pid in seen or pid in to_mark:
                            continue
                        to_mark.add(pid)
                        if is_base:
                            fresh.append(dict(p))
                if not is_base:
                    baselined.append(cfunc)
            if baselined:
                self.storage.set_baselined(chat_id, baselined)
            if to_mark:
                self.storage.mark_seen(chat_id, to_mark)
            if not fresh:
                continue
            fresh = await self.enrich(fresh, u)
            radius = u.get("radius_km")
            if radius:
                # Si no sabemos dónde está el centro, avisamos igualmente
                fresh = [p for p in fresh if p["_dist"] is None or p["_dist"]["km"] <= radius]
            if fresh:
                result[chat_id] = fresh
        return result
