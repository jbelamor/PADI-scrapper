"""Regenera los ficheros de datos estáticos del bot.

    python tools/actualizar_datos.py            # centros + especialidades
    python tools/actualizar_datos.py centros
    python tools/actualizar_datos.py especialidades

- data/centros.json: centros educativos públicos de la Comunidad de Madrid
  (datos abiertos) con dirección, teléfono y coordenadas lat/lon.
- data/especialidades.json: catálogo de cuerpos/especialidades, obtenido
  recorriendo las publicaciones de PADI del último año y pico.
"""
import asyncio
import csv
import io
import json
import sys
from datetime import date
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from padi.api import PadiClient  # noqa: E402
from padi.geo import utm_to_latlon  # noqa: E402

DATA = ROOT / "data"
CENTROS_CSV = ("https://datos.comunidad.madrid/dataset/c750856d-3166-4dac-8e80-d1b824c968b5/"
               "resource/28d60557-1d73-4281-ab08-6cfd3b2f5f83/download/centros_educativos.csv")


def build_centros():
    print("Descargando directorio de centros...")
    r = httpx.get(CENTROS_CSV, timeout=120, follow_redirects=True)
    r.raise_for_status()
    rows = csv.DictReader(io.StringIO(r.content.decode("utf-8-sig")), delimiter=";")
    centros = {}
    for row in rows:
        if row.get("TITULARIDAD", "").upper() != "PÚBLICO":
            continue
        x, y = row.get("UTM_X", "").strip(), row.get("UTM_Y", "").strip()
        lat = lon = None
        if x and y:
            try:
                lat, lon = utm_to_latlon(float(x.replace(",", ".")), float(y.replace(",", ".")))
            except ValueError:
                pass
        via = " ".join(p for p in (row.get("CDTPVIA", ""), row.get("DOMICILIO", ""),
                                   row.get("NMVIAL", "")) if p).strip()
        centros[row["CODIGO"]] = {
            "nombre": f'{row.get("TIPO_ABRV", "")} {row.get("CENTRO", "")}'.strip(),
            "direccion": via,
            "cp": row.get("CDPOSTAL", ""),
            "municipio": row.get("MUNICIPIO", ""),
            "distrito": row.get("DISTRITO", ""),
            "telefono": row.get("TELEFONO", "") if row.get("TELEFONO", "") not in ("", "0") else "",
            "web": row.get("WEB", ""),
            "lat": round(lat, 6) if lat else None,
            "lon": round(lon, 6) if lon else None,
        }
    DATA.mkdir(exist_ok=True)
    out = DATA / "centros.json"
    out.write_text(json.dumps(centros, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    con_coord = sum(1 for c in centros.values() if c["lat"])
    print(f"{len(centros)} centros públicos ({con_coord} con coordenadas) -> {out}")


async def build_especialidades(months_back=15):
    client = PadiClient()
    out_path = DATA / "especialidades.json"
    catalog = {}
    if out_path.exists():
        catalog = json.loads(out_path.read_text(encoding="utf-8"))
    cuerpos = catalog.setdefault("cuerpos", {})
    esps = catalog.setdefault("especialidades", {})

    today = date.today()
    months = []
    y, m = today.year, today.month
    for _ in range(months_back):
        months.append((y, m))
        y, m = (y - 1, 12) if m == 1 else (y, m - 1)

    print(f"Recorriendo {len(months)} meses de publicaciones de PADI...")
    fechas = set()
    for tipo in ("O", "E"):
        res = await asyncio.gather(*[
            client._post("getFiltroFechaNec", {"year": y, "monthId": m, "itperfilacto": tipo})
            for y, m in months], return_exceptions=True)
        for lst in res:
            if isinstance(lst, Exception):
                continue
            fechas.update((f["fcpublico"], tipo) for f in lst if f.get("fcpublico"))
    print(f"{len(fechas)} publicaciones encontradas")

    async def one(fc, tipo):
        try:
            cs = await client._post("getFiltroCuerpoNec", {"fcpublico": fc, "itperfilacto": tipo})
        except Exception:
            return
        for c in cs or []:
            cuerpos[c["codcuerpocfunc"]] = c["cuerpocfunc"].strip()
            try:
                es = await client._post("getFiltroEspNec", {
                    "codcuerpocfunc": c["codcuerpocfunc"], "fcpublico": fc, "itperfilacto": tipo})
            except Exception:
                continue
            for e in es or []:
                esps[c["codcuerpocfunc"] + e["codespcfunc"]] = {
                    "cuerpo": c["codcuerpocfunc"], "name": e["espcfunc"].strip()}

    await asyncio.gather(*[one(fc, t) for fc, t in sorted(fechas)])
    await client.close()

    catalog["especialidades"] = dict(sorted(esps.items()))
    catalog["cuerpos"] = dict(sorted(cuerpos.items()))
    DATA.mkdir(exist_ok=True)
    out_path.write_text(json.dumps(catalog, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{len(cuerpos)} cuerpos, {len(esps)} especialidades -> {out_path}")


if __name__ == "__main__":
    what = sys.argv[1] if len(sys.argv) > 1 else "todo"
    if what in ("todo", "centros"):
        build_centros()
    if what in ("todo", "especialidades"):
        asyncio.run(build_especialidades())
