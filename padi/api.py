"""Cliente de la API pública de PADI (actos públicos de sustituciones)."""
import asyncio
import json
from datetime import date

import httpx

BASE_URL = "https://gestiona7.madrid.org/nsus_rest_ares/v1/ActosPublicosSustituciones/"

HEADERS = {
    "Accept": "application/json, text/plain, */*",
    "Content-Type": "application/json;charset=UTF-8",
    "Origin": "https://gestiona.comunidad.madrid",
    "Referer": "https://gestiona.comunidad.madrid/",
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36"),
}

class PadiClient:
    def __init__(self, concurrency=4):
        self._client = httpx.AsyncClient(timeout=30, headers=HEADERS)
        self._sem = asyncio.Semaphore(concurrency)

    async def close(self):
        await self._client.aclose()

    async def _post(self, endpoint, payload):
        async with self._sem:
            for attempt in range(3):
                try:
                    r = await self._client.post(BASE_URL + endpoint, json=payload)
                    r.raise_for_status()
                    try:
                        txt = r.content.decode("utf-8")
                    except UnicodeDecodeError:
                        txt = r.content.decode("cp1252")
                    return json.loads(txt)
                except (httpx.HTTPError, json.JSONDecodeError):
                    if attempt == 2:
                        raise
                    await asyncio.sleep(2 * (attempt + 1))

    async def latest_date(self, tipo):
        """Última fecha de publicación (fcpublico) disponible para un tipo de acto."""
        today = date.today()
        months = [(today.year, today.month)]
        prev = (today.year - 1, 12) if today.month == 1 else (today.year, today.month - 1)
        months.append(prev)
        for year, month in months:
            fechas = await self._post("getFiltroFechaNec",
                                      {"year": year, "monthId": month, "itperfilacto": tipo})
            fechas = [f["fcpublico"] for f in fechas or [] if f.get("fcpublico")]
            if fechas:
                return max(fechas)
        return None

    async def necesidades(self, cfunc, fcpublico, tipo):
        data = await self._post("consultaNecesidades", {
            "fcpublico": fcpublico,
            "cfunc": cfunc,
            "coddat": "T",
            "itperfilacto": tipo,
        })
        out = []
        for rec in data or []:
            rec = dict(rec)
            rec["cfunc"] = cfunc
            rec["tipo_acto"] = tipo
            out.append(rec)
        return out

    async def plazas(self, cfuncs, tipos=("E",)):
        """Plazas abiertas en la última publicación para una lista de especialidades.

        tipos: tipos de acto, "O" (ordinario) y/o "E" (extraordinario).
        Devuelve (lista_de_plazas, {tipo: fcpublico}).
        """
        fechas = {}
        for tipo in tipos:
            fechas[tipo] = await self.latest_date(tipo)
        tasks = [self.necesidades(cf, fechas[t], t)
                 for t in tipos if fechas[t]
                 for cf in cfuncs]
        results = await asyncio.gather(*tasks)
        plazas, seen = [], set()
        for lst in results:
            for rec in lst:
                key = rec.get("idnsustituciones")
                if key in seen:
                    continue
                seen.add(key)
                plazas.append(rec)
        return plazas, fechas

    async def especialidades_publicadas(self, fcpublico, tipo):
        """Cuerpos y especialidades con necesidades en una fecha (para ampliar el catálogo)."""
        out = {}
        cuerpos = await self._post("getFiltroCuerpoNec",
                                   {"fcpublico": fcpublico, "itperfilacto": tipo})
        for c in cuerpos or []:
            esps = await self._post("getFiltroEspNec", {
                "codcuerpocfunc": c["codcuerpocfunc"],
                "fcpublico": fcpublico,
                "itperfilacto": tipo,
            })
            for e in esps or []:
                code = c["codcuerpocfunc"] + e["codespcfunc"]
                out[code] = {"cuerpo": c["codcuerpocfunc"],
                             "name": e["espcfunc"].strip()}
        return out
