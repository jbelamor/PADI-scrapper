"""Bot de Telegram: configuración por el propio usuario, consulta de plazas y alertas."""
import asyncio
import logging
from datetime import datetime, timedelta
from html import escape

from telegram import (BotCommand, InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton,
                      LinkPreviewOptions, ReplyKeyboardMarkup, Update)
from telegram.constants import ParseMode
from telegram.error import Forbidden, TelegramError
from telegram.ext import (Application, ApplicationBuilder, CallbackQueryHandler, CommandHandler,
                          ContextTypes, MessageHandler, filters)

from . import geo, messages, settings
from .service import PadiService

log = logging.getLogger(__name__)

NO_PREVIEW = LinkPreviewOptions(is_disabled=True)
PAGE_SIZE = 8

# ---------- teclados ----------
BTN_PLAZAS = "📋 Ver plazas"
BTN_ESP = "📚 Especialidades"
BTN_LOC = "📍 Ubicación"
BTN_AJUSTES = "⚙️ Ajustes"
BTN_CANCEL = "↩️ Cancelar"

MAIN_KB = ReplyKeyboardMarkup([[BTN_PLAZAS, BTN_ESP], [BTN_LOC, BTN_AJUSTES]],
                              resize_keyboard=True, is_persistent=True)
LOC_KB = ReplyKeyboardMarkup([[KeyboardButton("📍 Enviar mi ubicación actual", request_location=True)],
                              [BTN_CANCEL]], resize_keyboard=True, one_time_keyboard=True)

TIPOS_CICLO = {"E": "O", "O": "OE", "OE": "E"}
TIPOS_TXT = {"E": "Extraordinario", "O": "Ordinario", "OE": "Ordinario y extraordinario"}


def svc(context) -> PadiService:
    return context.application.bot_data["svc"]


def ensure_user(update: Update, context):
    u = update.effective_user
    name = (u.username or u.full_name) if u else None
    svc(context).storage.ensure_user(update.effective_chat.id, name)
    return svc(context).storage.get_user(update.effective_chat.id)


async def reply(update: Update, text, **kw):
    kw.setdefault("parse_mode", ParseMode.HTML)
    kw.setdefault("link_preview_options", NO_PREVIEW)
    return await update.effective_chat.send_message(text, **kw)


async def edit_or_send(update: Update, text, markup):
    if update.callback_query:
        try:
            await update.callback_query.edit_message_text(
                text, reply_markup=markup, parse_mode=ParseMode.HTML, link_preview_options=NO_PREVIEW)
            return
        except TelegramError as e:
            if "not modified" in str(e).lower():
                return
    await reply(update, text, reply_markup=markup)


# ---------- vistas de especialidades ----------
def view_subs(s: PadiService, chat_id):
    subs = s.storage.subs(chat_id)
    if subs:
        lista = "\n".join(f"• {escape(s.catalog.label(cf))}" for cf in subs)
        text = (f"📚 <b>Tus especialidades</b>\n\n{lista}\n\n"
                "Pulsa ❌ para quitar una.\n"
                "Para añadir otra, <b>escribe su nombre</b> aquí mismo (p. ej. <i>informática</i>, "
                "<i>inglés</i>, <i>infantil</i>) o explora por cuerpo.")
    else:
        text = ("📚 <b>Aún no sigues ninguna especialidad</b>\n\n"
                "La forma más rápida: <b>escribe su nombre</b> (p. ej. <i>matemáticas</i>, "
                "<i>sistemas</i>, <i>primaria</i>) y pulsa la que quieras.\n"
                "También puedes explorar la lista completa por cuerpo 👇")
    rows = [[InlineKeyboardButton(f"❌ {s.catalog.label(cf)}", callback_data=f"t:{cf}:s")]
            for cf in subs]
    rows.append([InlineKeyboardButton("➕ Explorar por cuerpo", callback_data="cu")])
    if subs:
        rows.append([InlineKeyboardButton("📋 Ver plazas abiertas", callback_data="pl")])
    return text, InlineKeyboardMarkup(rows)


def view_cuerpos(s: PadiService):
    btns = [InlineKeyboardButton(s.catalog.cuerpo_short(code), callback_data=f"c:{code}:0")
            for code in s.catalog.cuerpos]
    rows = [btns[i:i + 2] for i in range(0, len(btns), 2)]
    rows.append([InlineKeyboardButton("⬅️ Mis especialidades", callback_data="subs")])
    return "🏛️ <b>Elige el cuerpo</b>", InlineKeyboardMarkup(rows)


def view_cuerpo(s: PadiService, chat_id, code, page):
    items = s.catalog.by_cuerpo(code)
    pages = max(1, (len(items) + PAGE_SIZE - 1) // PAGE_SIZE)
    page = max(0, min(page, pages - 1))
    mine = set(s.storage.subs(chat_id))
    rows = []
    for cf, name in items[page * PAGE_SIZE:(page + 1) * PAGE_SIZE]:
        mark = "✅" if cf in mine else "▫️"
        rows.append([InlineKeyboardButton(f"{mark} {name.capitalize()}",
                                          callback_data=f"t:{cf}:c{code}p{page}")])
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton("◀️", callback_data=f"c:{code}:{page - 1}"))
    if pages > 1:
        nav.append(InlineKeyboardButton(f"{page + 1}/{pages}", callback_data="noop"))
    if page < pages - 1:
        nav.append(InlineKeyboardButton("▶️", callback_data=f"c:{code}:{page + 1}"))
    if nav:
        rows.append(nav)
    rows.append([InlineKeyboardButton("⬅️ Cuerpos", callback_data="cu"),
                 InlineKeyboardButton("✔️ Listo", callback_data="done")])
    text = (f"🏛️ <b>{escape(s.catalog.cuerpos.get(code, code).capitalize())}</b>\n"
            "Pulsa para marcar ✅ o desmarcar ▫️")
    return text, InlineKeyboardMarkup(rows)


def view_search(s: PadiService, chat_id, query, results):
    mine = set(s.storage.subs(chat_id))
    rows = [[InlineKeyboardButton(f"{'✅' if cf in mine else '▫️'} {s.catalog.label(cf)}",
                                  callback_data=f"t:{cf}:q")] for cf in results]
    rows.append([InlineKeyboardButton("✔️ Listo", callback_data="done")])
    text = (f"🔎 Resultados para «{escape(query)}»\n"
            "Pulsa para marcar ✅ o desmarcar ▫️")
    return text, InlineKeyboardMarkup(rows)


# ---------- vistas de ajustes ----------
def view_ajustes(s: PadiService, chat_id):
    u = s.storage.get_user(chat_id)
    alerts = bool(u["alerts"])
    loc = escape(u["address"]) if u.get("lat") is not None else "sin configurar"
    radio = f"{u['radius_km']:.0f} km" if u.get("radius_km") else "sin límite"
    tipos = u.get("tipos") or "E"
    text = ("⚙️ <b>Ajustes</b>\n\n"
            f"🔔 Alertas: <b>{'activadas' if alerts else 'desactivadas'}</b>\n"
            f"🔖 Tipo de acto: <b>{TIPOS_TXT[tipos]}</b>\n"
            f"📍 Ubicación: <b>{loc}</b>\n"
            f"📏 Radio de alertas: <b>{radio}</b>")
    rows = [
        [InlineKeyboardButton("🔕 Desactivar alertas" if alerts else "🔔 Activar alertas",
                              callback_data="al")],
        [InlineKeyboardButton(f"🔖 Cambiar tipo de acto", callback_data="ty")],
        [InlineKeyboardButton("📍 Cambiar ubicación", callback_data="loc"),
         InlineKeyboardButton("📏 Radio", callback_data="rd")],
        [InlineKeyboardButton("🗑️ Borrar mis datos", callback_data="del")],
    ]
    return text, InlineKeyboardMarkup(rows)


def view_radio(s: PadiService, chat_id):
    u = s.storage.get_user(chat_id)
    if u.get("lat") is None:
        return ("📏 Para filtrar por distancia primero necesito tu ubicación (/ubicacion).",
                InlineKeyboardMarkup([[InlineKeyboardButton("📍 Poner ubicación",
                                                            callback_data="loc")]]))
    opts = [5, 10, 15, 20, 30, 50, 75]
    cur = u.get("radius_km")
    btns = [InlineKeyboardButton(("✅ " if cur == km else "") + f"{km} km", callback_data=f"r:{km}")
            for km in opts]
    rows = [btns[i:i + 4] for i in range(0, len(btns), 4)]
    rows.append([InlineKeyboardButton(("✅ " if not cur else "") + "Sin límite",
                                      callback_data="r:0")])
    text = ("📏 <b>¿Hasta qué distancia quieres que te avise?</b>\n"
            "Solo recibirás alertas de centros a esa distancia (en línea recta) o menos. "
            "En /plazas seguirás viendo todas, ordenadas por cercanía.")
    return text, InlineKeyboardMarkup(rows)


# ---------- comandos ----------
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ensure_user(update, context)
    await reply(update,
                "👋 <b>¡Hola!</b> Te aviso cuando salgan plazas nuevas en PADI "
                "(sustituciones docentes de la Comunidad de Madrid) para las especialidades que elijas.\n\n"
                "1️⃣ Elige tus especialidades (abajo 👇)\n"
                "2️⃣ Opcional: comparte tu ubicación para ver a qué distancia está cada centro\n"
                "3️⃣ Consulta cuando quieras las plazas abiertas con <b>📋 Ver plazas</b>\n\n"
                "Escribe /ayuda para ver todo lo que puedo hacer.",
                reply_markup=MAIN_KB)
    await cmd_especialidades(update, context)


async def cmd_ayuda(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await reply(update,
                "🤖 <b>Cómo usarme</b>\n\n"
                "• <b>Escribe el nombre de una especialidad</b> (o parte, sin preocuparte de tildes) "
                "para añadirla o quitarla. También vale el código, p. ej. <code>0590107</code>.\n"
                "• /especialidades — ver y editar las que sigues\n"
                "• /plazas — plazas abiertas ahora, ordenadas por distancia\n"
                "• /ubicacion — tu ubicación (GPS, dirección, municipio o código postal)\n"
                "• /radio — avisarte solo de centros cercanos\n"
                "• /ajustes — alertas, tipo de acto, borrar datos\n\n"
                "Las distancias son estimadas: línea recta y aproximación por carretera. "
                "Usa «Cómo llegar» para la ruta real.",
                reply_markup=MAIN_KB)


async def cmd_especialidades(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ensure_user(update, context)
    text, kb = view_subs(svc(context), update.effective_chat.id)
    await reply(update, text, reply_markup=kb)


async def cmd_plazas(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = ensure_user(update, context)
    s = svc(context)
    chat_id = update.effective_chat.id
    if not s.storage.subs(chat_id):
        await reply(update, "Primero elige alguna especialidad 👇")
        return await cmd_especialidades(update, context)
    wait = await reply(update, "⏳ Consultando PADI…")
    try:
        plazas, fechas = await s.plazas_usuario(chat_id)
    except Exception:
        log.exception("Error consultando PADI")
        await wait.edit_text("⚠️ No he podido consultar PADI ahora mismo. Prueba en unos minutos.")
        return
    await wait.delete()
    if not plazas:
        await reply(update, "🙁 Ahora mismo no hay plazas abiertas para tus especialidades.\n"
                            "Te avisaré en cuanto salga alguna.", reply_markup=MAIN_KB)
        return
    for msg in messages.lista_plazas(plazas, fechas, s.catalog, user):
        await reply(update, msg)


async def cmd_ubicacion(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ensure_user(update, context)
    context.user_data["awaiting"] = "address"
    await reply(update,
                "📍 <b>¿Desde dónde te desplazas?</b>\n\n"
                "• Pulsa el botón de abajo para enviar tu ubicación actual, o\n"
                "• Escribe una dirección, un municipio o un código postal "
                "(p. ej. <i>Calle Alcalá 100, Madrid</i>, <i>Getafe</i>, <i>28850</i>).\n\n"
                "Solo la uso para calcular distancias.",
                reply_markup=LOC_KB)


async def cmd_radio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ensure_user(update, context)
    text, kb = view_radio(svc(context), update.effective_chat.id)
    await reply(update, text, reply_markup=kb)


async def cmd_ajustes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ensure_user(update, context)
    text, kb = view_ajustes(svc(context), update.effective_chat.id)
    await reply(update, text, reply_markup=kb)


# ---------- ubicación ----------
async def save_location(update: Update, context, lat, lon, name):
    s = svc(context)
    chat_id = update.effective_chat.id
    s.storage.set_location(chat_id, lat, lon, name)
    context.user_data.pop("awaiting", None)
    await reply(update, f"✅ Ubicación guardada: <b>{escape(name)}</b>\n"
                        "Ahora verás la distancia a cada centro en /plazas y en las alertas.",
                reply_markup=MAIN_KB)
    text, kb = view_radio(s, chat_id)
    await reply(update, text, reply_markup=kb)


async def on_location(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ensure_user(update, context)
    loc = update.effective_message.location
    name = await geo.reverse(loc.latitude, loc.longitude) or \
        f"{loc.latitude:.4f}, {loc.longitude:.4f}"
    await save_location(update, context, loc.latitude, loc.longitude, name)


async def handle_address(update: Update, context, text):
    try:
        hit = await geo.geocode(text)
    except Exception:
        log.exception("Error geocodificando")
        hit = None
    if not hit:
        await reply(update, "🤔 No encuentro esa dirección. Prueba con más detalle "
                            "(calle, número y municipio) o envía tu ubicación con el botón.",
                    reply_markup=LOC_KB)
        return
    lat, lon, display = hit
    short = ", ".join(display.split(", ")[:3])
    await save_location(update, context, lat, lon, short)


# ---------- texto libre ----------
async def on_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ensure_user(update, context)
    text = update.effective_message.text.strip()
    routes = {BTN_PLAZAS: cmd_plazas, BTN_ESP: cmd_especialidades,
              BTN_LOC: cmd_ubicacion, BTN_AJUSTES: cmd_ajustes}
    if text in routes:
        context.user_data.pop("awaiting", None)
        return await routes[text](update, context)
    if text == BTN_CANCEL:
        context.user_data.pop("awaiting", None)
        return await reply(update, "Vale 👍", reply_markup=MAIN_KB)
    if context.user_data.get("awaiting") == "address":
        return await handle_address(update, context, text)

    s = svc(context)
    results = s.catalog.search(text)
    if not results:
        await reply(update, f"🤔 No encuentro ninguna especialidad con «{escape(text)}».\n"
                            "Prueba con otra palabra o explora la lista completa con /especialidades.")
        return
    context.user_data["last_query"] = text
    context.user_data["last_results"] = results
    msg, kb = view_search(s, update.effective_chat.id, text, results)
    await reply(update, msg, reply_markup=kb)


# ---------- botones ----------
async def on_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    ensure_user(update, context)
    s = svc(context)
    chat_id = update.effective_chat.id
    data = q.data or ""

    if data == "noop":
        return await q.answer()

    if data.startswith("t:"):
        _, cf, where = data.split(":", 2)
        on = s.storage.toggle_sub(chat_id, cf)
        await q.answer(("✅ Añadida: " if on else "Quitada: ") + s.catalog.name(cf).capitalize())
        if where == "s":
            text, kb = view_subs(s, chat_id)
        elif where == "q":
            text, kb = view_search(s, chat_id, context.user_data.get("last_query", ""),
                                   context.user_data.get("last_results", [cf]))
        else:  # c{cuerpo}p{page}
            code, page = where[1:].split("p")
            text, kb = view_cuerpo(s, chat_id, code, int(page))
        return await edit_or_send(update, text, kb)

    await q.answer()
    if data == "subs":
        return await edit_or_send(update, *view_subs(s, chat_id))
    if data == "cu":
        return await edit_or_send(update, *view_cuerpos(s))
    if data.startswith("c:"):
        _, code, page = data.split(":")
        return await edit_or_send(update, *view_cuerpo(s, chat_id, code, int(page)))
    if data == "done":
        await edit_or_send(update, *view_subs(s, chat_id))
        user = s.storage.get_user(chat_id)
        if s.storage.subs(chat_id) and user.get("lat") is None:
            await reply(update, "💡 Consejo: comparte tu ubicación con /ubicacion y te diré "
                                "a qué distancia está cada centro.")
        return
    if data == "pl":
        return await cmd_plazas(update, context)

    # ajustes
    if data == "al":
        user = s.storage.get_user(chat_id)
        s.storage.set_alerts(chat_id, not user["alerts"])
        return await edit_or_send(update, *view_ajustes(s, chat_id))
    if data == "ty":
        user = s.storage.get_user(chat_id)
        s.storage.set_tipos(chat_id, TIPOS_CICLO.get(user.get("tipos") or "E", "E"))
        return await edit_or_send(update, *view_ajustes(s, chat_id))
    if data == "loc":
        return await cmd_ubicacion(update, context)
    if data == "rd":
        return await edit_or_send(update, *view_radio(s, chat_id))
    if data.startswith("r:"):
        km = float(data[2:])
        s.storage.set_radius(chat_id, km or None)
        txt = (f"✅ Te avisaré solo de centros a {km:.0f} km o menos." if km
               else "✅ Te avisaré de todas las plazas, sin límite de distancia.")
        return await edit_or_send(update, txt, None)
    if data == "del":
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("Sí, borrar todo", callback_data="delok"),
                                    InlineKeyboardButton("No", callback_data="aj")]])
        return await edit_or_send(update, "🗑️ ¿Seguro? Se borrarán tus especialidades, "
                                          "ubicación y ajustes.", kb)
    if data == "delok":
        s.storage.delete_user(chat_id)
        context.user_data.clear()
        return await edit_or_send(update, "Hecho. He borrado tus datos. "
                                          "Si quieres volver, escribe /start 👋", None)
    if data == "aj":
        return await edit_or_send(update, *view_ajustes(s, chat_id))


# ---------- alertas periódicas ----------
async def send_alerts(bot, s: PadiService):
    alerts = await s.check_alerts()
    for chat_id, plazas in alerts.items():
        try:
            for msg in messages.alerta(plazas, s.catalog):
                await bot.send_message(chat_id, msg, parse_mode=ParseMode.HTML,
                                       link_preview_options=NO_PREVIEW)
        except Forbidden:
            log.info("Usuario %s ha bloqueado el bot; desactivo sus alertas", chat_id)
            s.storage.set_alerts(chat_id, False)
        except TelegramError:
            log.exception("Error enviando alerta a %s", chat_id)
    log.info("Comprobación hecha: %d usuarios con novedades", len(alerts))
    return alerts


def next_check(now: datetime):
    step = settings.CHECK_EVERY_MINUTES
    start_h, end_h = settings.CHECK_HOURS
    t = now.replace(second=0, microsecond=0)
    t += timedelta(minutes=step - (t.minute % step))
    for _ in range(60 * 24 * 8 // step):
        if (settings.CHECK_WEEKENDS or t.weekday() < 5) and start_h <= t.hour < end_h:
            return t
        t += timedelta(minutes=step)
    return now + timedelta(hours=1)


async def alerts_loop(app: Application):
    s = app.bot_data["svc"]
    while True:
        when = next_check(datetime.now())
        log.info("Próxima comprobación: %s", when.strftime("%a %d/%m %H:%M"))
        await asyncio.sleep(max(1.0, (when - datetime.now()).total_seconds()))
        try:
            await send_alerts(app.bot, s)
        except Exception:
            log.exception("Error en la comprobación periódica")


# ---------- arranque ----------
def import_legacy_users(s: PadiService):
    """Importa los usuarios definidos a mano en config.py (formato antiguo), una sola vez."""
    if not settings.LEGACY_USERS or s.storage.all_users():
        return
    for username, info in settings.LEGACY_USERS.items():
        try:
            chat_id = int(info["user_id"])
        except (KeyError, ValueError):
            continue
        s.storage.ensure_user(chat_id, username)
        for subj in info.get("asignaturas", []):
            s.storage.add_sub(chat_id, subj["code"])
        log.info("Usuario importado de config.py: %s", username)


async def post_init(app: Application):
    s = PadiService(settings.DB_PATH)
    import_legacy_users(s)
    app.bot_data["svc"] = s
    await app.bot.set_my_commands([
        BotCommand("plazas", "Ver plazas abiertas ahora"),
        BotCommand("especialidades", "Elegir especialidades"),
        BotCommand("ubicacion", "Poner tu ubicación"),
        BotCommand("radio", "Avisar solo de centros cercanos"),
        BotCommand("ajustes", "Alertas, tipo de acto, datos"),
        BotCommand("ayuda", "Cómo funciona"),
    ])
    app.bot_data["loop_task"] = asyncio.create_task(alerts_loop(app))


async def post_shutdown(app: Application):
    task = app.bot_data.get("loop_task")
    if task:
        task.cancel()
    if "svc" in app.bot_data:
        await app.bot_data["svc"].close()


def build_app():
    app = (ApplicationBuilder().token(settings.TOKEN)
           .post_init(post_init).post_shutdown(post_shutdown).build())
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler(["ayuda", "help"], cmd_ayuda))
    app.add_handler(CommandHandler(["especialidades", "asignaturas"], cmd_especialidades))
    app.add_handler(CommandHandler("plazas", cmd_plazas))
    app.add_handler(CommandHandler("ubicacion", cmd_ubicacion))
    app.add_handler(CommandHandler("radio", cmd_radio))
    app.add_handler(CommandHandler("ajustes", cmd_ajustes))
    app.add_handler(MessageHandler(filters.LOCATION, on_location))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text))
    app.add_handler(CallbackQueryHandler(on_callback))
    return app


async def run_check_once():
    """Una sola comprobación + envío (modo cron)."""
    from telegram import Bot
    s = PadiService(settings.DB_PATH)
    import_legacy_users(s)
    try:
        async with Bot(settings.TOKEN) as bot:
            await send_alerts(bot, s)
    finally:
        await s.close()
