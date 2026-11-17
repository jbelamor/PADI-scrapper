"""Utilidades geográficas: UTM -> lat/lon, distancias y geocodificación."""
import asyncio
import math
import time
import unicodedata

import httpx

_geocode_lock = asyncio.Lock()
_last_call = 0.0

# Factor medio entre distancia en línea recta y distancia por carretera.
# En la Comunidad de Madrid ronda 1.25-1.4; usamos 1.3 como estimación.
ROAD_FACTOR = 1.3


def utm_to_latlon(x, y, zone=30, northern=True):
    """Convierte coordenadas UTM (ETRS89/WGS84) a (lat, lon) en grados."""
    a = 6378137.0
    f = 1 / 298.257223563
    e2 = f * (2 - f)
    ep2 = e2 / (1 - e2)
    k0 = 0.9996

    x = x - 500000.0
    if not northern:
        y = y - 10000000.0

    m = y / k0
    mu = m / (a * (1 - e2 / 4 - 3 * e2 ** 2 / 64 - 5 * e2 ** 3 / 256))
    e1 = (1 - math.sqrt(1 - e2)) / (1 + math.sqrt(1 - e2))

    phi1 = (mu
            + (3 * e1 / 2 - 27 * e1 ** 3 / 32) * math.sin(2 * mu)
            + (21 * e1 ** 2 / 16 - 55 * e1 ** 4 / 32) * math.sin(4 * mu)
            + (151 * e1 ** 3 / 96) * math.sin(6 * mu)
            + (1097 * e1 ** 4 / 512) * math.sin(8 * mu))

    sin1, cos1, tan1 = math.sin(phi1), math.cos(phi1), math.tan(phi1)
    n1 = a / math.sqrt(1 - e2 * sin1 ** 2)
    t1 = tan1 ** 2
    c1 = ep2 * cos1 ** 2
    r1 = a * (1 - e2) / (1 - e2 * sin1 ** 2) ** 1.5
    d = x / (n1 * k0)

    lat = phi1 - (n1 * tan1 / r1) * (
        d ** 2 / 2
        - (5 + 3 * t1 + 10 * c1 - 4 * c1 ** 2 - 9 * ep2) * d ** 4 / 24
        + (61 + 90 * t1 + 298 * c1 + 45 * t1 ** 2 - 252 * ep2 - 3 * c1 ** 2) * d ** 6 / 720)
    lon = (d
           - (1 + 2 * t1 + c1) * d ** 3 / 6
           + (5 - 2 * c1 + 28 * t1 - 3 * c1 ** 2 + 8 * ep2 + 24 * t1 ** 2) * d ** 5 / 120) / cos1

    lon0 = math.radians((zone - 1) * 6 - 180 + 3)
    return math.degrees(lat), math.degrees(lon0 + lon)


def haversine_km(lat1, lon1, lat2, lon2):
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = p2 - p1
    dl = math.radians(lon2 - lon1)
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(h))


def estimate(lat1, lon1, lat2, lon2):
    """Devuelve (km_linea_recta, km_estimados_carretera, minutos_estimados_coche)."""
    straight = haversine_km(lat1, lon1, lat2, lon2)
    road = straight * ROAD_FACTOR
    # Tiempo orientativo en coche: ~5 min fijos (salir, aparcar) + ~50 km/h de media
    minutes = 5 + road * 1.2
    return straight, road, minutes


def maps_link(origin_lat, origin_lon, dest_lat, dest_lon):
    return ("https://www.google.com/maps/dir/?api=1"
            f"&origin={origin_lat:.6f},{origin_lon:.6f}"
            f"&destination={dest_lat:.6f},{dest_lon:.6f}")


def normalize(text):
    """Minúsculas y sin tildes, para búsquedas tolerantes."""
    text = unicodedata.normalize("NFKD", text or "")
    return "".join(c for c in text if not unicodedata.combining(c)).lower().strip()


# Caja aproximada de la Comunidad de Madrid para sesgar la geocodificación
MADRID_VIEWBOX = "-4.58,41.17,-3.05,39.88"


async def geocode(query):
    """Geocodifica una dirección/municipio/código postal con Nominatim (OSM).

    Devuelve (lat, lon, nombre_legible) o None.
    """
    params = {
        "q": query,
        "format": "jsonv2",
        "limit": 1,
        "countrycodes": "es",
        "viewbox": MADRID_VIEWBOX,
        "bounded": 0,
        "accept-language": "es",
    }
    headers = {"User-Agent": "padi-scrapper-telegram-bot/2.0"}
    # Política de uso de Nominatim: máximo 1 petición por segundo
    global _last_call
    async with _geocode_lock:
        wait = 1.1 - (time.monotonic() - _last_call)
        if wait > 0:
            await asyncio.sleep(wait)
        try:
            async with httpx.AsyncClient(timeout=20) as client:
                r = await client.get("https://nominatim.openstreetmap.org/search",
                                     params=params, headers=headers)
                r.raise_for_status()
                data = r.json()
        finally:
            _last_call = time.monotonic()
    if not data:
        return None
    hit = data[0]
    return float(hit["lat"]), float(hit["lon"]), hit.get("display_name", query)


async def reverse(lat, lon):
    """Nombre legible (barrio, municipio) para unas coordenadas, o None."""
    global _last_call
    async with _geocode_lock:
        wait = 1.1 - (time.monotonic() - _last_call)
        if wait > 0:
            await asyncio.sleep(wait)
        try:
            async with httpx.AsyncClient(timeout=20) as client:
                r = await client.get(
                    "https://nominatim.openstreetmap.org/reverse",
                    params={"lat": lat, "lon": lon, "format": "jsonv2", "zoom": 16,
                            "accept-language": "es"},
                    headers={"User-Agent": "padi-scrapper-telegram-bot/2.0"})
                r.raise_for_status()
                data = r.json()
        except httpx.HTTPError:
            return None
        finally:
            _last_call = time.monotonic()
    addr = data.get("address") or {}
    parts = [addr.get(k) for k in ("road", "suburb", "city", "town", "village")]
    parts = [p for p in parts if p]
    return ", ".join(dict.fromkeys(parts)) or data.get("display_name")
