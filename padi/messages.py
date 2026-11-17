"""Formato de mensajes de Telegram (HTML)."""
from html import escape

MAX_LEN = 3900  # Telegram admite 4096; dejamos margen

TIPO_ACTO = {"O": "ordinario", "E": "extraordinario"}


def fecha(iso):
    if not iso or len(iso) < 10:
        return iso or "—"
    y, m, d = iso[:10].split("-")
    return f"{d}/{m}/{y}"


def distancia(d):
    if not d:
        return None
    km = d["km"]
    km_txt = f"{km:.1f}" if km < 10 else f"{km:.0f}"
    mins = d["min"]
    t = f"{mins:.0f} min" if mins < 60 else f"{int(mins // 60)} h {int(mins % 60):02d} min"
    return (f'📍 <b>{km_txt} km</b> en línea recta '
            f'(≈{d["road_km"]:.0f} km, ~{t} en coche) · <a href="{d["maps"]}">Cómo llegar</a>')


def plaza(p, catalog):
    centro_info = p.get("_centro") or {}
    nombre = escape(p.get("centro") or centro_info.get("nombre") or "Centro desconocido")
    localidad = escape(p.get("localidad") or centro_info.get("municipio") or "")
    # El campo "distrito" de PADI no es fiable; usamos el del directorio de centros
    distrito = centro_info.get("distrito")
    if distrito:
        localidad += f" ({escape(distrito)})"

    lines = [f"🏫 <b>{nombre}</b>", f"🏙️ {localidad}"]
    if centro_info.get("direccion"):
        lines[-1] += f" · {escape(centro_info['direccion'])}"
    lines.append(f"📘 {escape(catalog.label(p.get('cfunc', '')))}")
    jornada = p.get("dtpvacante") or p.get("dtipopuesto") or "Jornada completa"
    lines.append(f"🕒 {escape(jornada.capitalize())}")
    lines.append(f"🗓️ Hasta {fecha(p.get('fhasta'))}"
                 + (f" · {escape(p['causa'].capitalize())}" if p.get("causa") else ""))
    obs = (p.get("observaciones") or "").strip()
    if obs:
        if len(obs) > 300:
            obs = obs[:300] + "…"
        lines.append(f"📌 <i>{escape(obs)}</i>")
    dist = distancia(p.get("_dist"))
    if dist:
        lines.append(dist)
    tel = centro_info.get("telefono")
    if tel:
        lines.append(f"📞 {escape(tel)}")
    if p.get("tipo_acto") == "O":
        lines.append("🔖 Acto ordinario")
    return "\n".join(lines)


def chunk(header, blocks, footer=""):
    """Agrupa bloques en mensajes que no superen el límite de Telegram."""
    msgs, cur = [], header
    for b in blocks:
        piece = "\n\n" + b
        if len(cur) + len(piece) > MAX_LEN:
            msgs.append(cur)
            cur = b
        else:
            cur += piece
    if footer:
        if len(cur) + len(footer) + 2 > MAX_LEN:
            msgs.append(cur)
            cur = footer
        else:
            cur += "\n\n" + footer
    msgs.append(cur)
    return msgs


def lista_plazas(plazas, fechas, catalog, user):
    pubs = ", ".join(f"{TIPO_ACTO[t]} del {fecha(f)}" for t, f in fechas.items() if f)
    n = len(plazas)
    header = (f"📋 <b>{n} plaza{'s' if n != 1 else ''} abierta{'s' if n != 1 else ''}</b> "
              f"para tus especialidades\n<i>Publicación: {pubs or '—'}</i>")
    footer = ""
    if user.get("lat") is None:
        footer = "💡 Usa /ubicacion para ver a qué distancia está cada centro y ordenarlos."
    elif user.get("radius_km"):
        dentro = sum(1 for p in plazas if p["_dist"] and p["_dist"]["km"] <= user["radius_km"])
        header += f"\n{dentro} dentro de tu radio de {user['radius_km']:.0f} km"
    return chunk(header, [plaza(p, catalog) for p in plazas], footer)


def alerta(plazas, catalog):
    n = len(plazas)
    header = f"🔔 <b>{n} plaza{'s' if n != 1 else ''} nueva{'s' if n != 1 else ''} en PADI</b>"
    return chunk(header, [plaza(p, catalog) for p in plazas])
