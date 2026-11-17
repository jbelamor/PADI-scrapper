"""Catálogo de especialidades y directorio de centros."""
import json
import re
from pathlib import Path

from .geo import geocode, normalize

DATA = Path(__file__).resolve().parent.parent / "data"

# Nombres cortos para los botones de cuerpos
CUERPO_CORTO = {
    "0590": "Secundaria",
    "0591": "Técnicos FP",
    "0592": "EOI (Idiomas)",
    "0593": "Catedráticos Música",
    "0594": "Música y Artes Escénicas",
    "0595": "Artes Plásticas y Diseño",
    "0596": "Maestros de Taller",
    "0597": "Maestros",
    "0598": "Especialistas FP",
}


class Catalog:
    def __init__(self, storage):
        self.storage = storage
        raw = json.loads((DATA / "especialidades.json").read_text(encoding="utf-8"))
        self.cuerpos = raw["cuerpos"]
        self._base = raw["especialidades"]
        self.reload()

    def reload(self):
        self.esp = dict(self._base)
        self.esp.update(self.storage.catalog_extra())
        self._norm = {code: normalize(v["name"]) for code, v in self.esp.items()}

    def merge(self, found):
        """Añade especialidades descubiertas en publicaciones nuevas."""
        new = {k: v for k, v in found.items() if k not in self.esp}
        if new:
            self.storage.add_catalog(new)
            self.reload()
        return new

    def name(self, cfunc):
        e = self.esp.get(cfunc)
        return e["name"] if e else f"Especialidad {cfunc}"

    def cuerpo_short(self, code):
        return CUERPO_CORTO.get(code) or self.cuerpos.get(code, code).title()

    def label(self, cfunc):
        """Nombre de especialidad + cuerpo, para distinguir p.ej. INGLÉS de Secundaria vs EOI."""
        return f"{self.name(cfunc).capitalize()} ({self.cuerpo_short(cfunc[:4])})"

    def by_cuerpo(self, cuerpo):
        items = [(k, v["name"]) for k, v in self.esp.items() if v["cuerpo"] == cuerpo]
        return sorted(items, key=lambda kv: normalize(kv[1]))

    def search(self, query, limit=12):
        q = normalize(query)
        if not q:
            return []
        code = re.sub(r"\s", "", query).upper()
        if code in self.esp:
            return [code]
        tokens = q.split()
        hits = []
        for c, n in self._norm.items():
            if all(t in n for t in tokens):
                # prioriza coincidencias al principio del nombre y nombres cortos
                score = (0 if n.startswith(tokens[0]) else 1, len(n))
                hits.append((score, c))
        hits.sort()
        return [c for _, c in hits[:limit]]


class Centros:
    def __init__(self, storage):
        self.storage = storage
        self.data = json.loads((DATA / "centros.json").read_text(encoding="utf-8"))

    def get(self, ccentro):
        return self.data.get(str(ccentro))

    async def coords(self, ccentro, nombre_padi="", localidad=""):
        """(lat, lon) del centro. Usa el directorio y, si falta, geocodifica y cachea."""
        info = self.get(ccentro)
        if info and info.get("lat"):
            return info["lat"], info["lon"]
        cached = self.storage.geocache_get(str(ccentro))
        if cached:
            return cached if cached[0] is not None else None
        queries = []
        if info and info.get("direccion"):
            queries.append(f'{info["direccion"]}, {info.get("cp", "")} {info["municipio"]}, Madrid')
        if nombre_padi:
            queries.append(f"{nombre_padi}, {localidad}, Comunidad de Madrid")
        for q in queries:
            try:
                hit = await geocode(q)
            except Exception:
                hit = None
            if hit:
                self.storage.geocache_set(str(ccentro), hit[0], hit[1])
                return hit[0], hit[1]
        self.storage.geocache_set(str(ccentro), None, None)
        return None
