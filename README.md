# PADI-scrapper
Bot de Telegram que vigila [PADI](https://gestiona.comunidad.madrid/padi/#!/main-menu) (actos públicos de sustituciones docentes de la Comunidad de Madrid) y avisa de las plazas nuevas.

Cada usuario lo configura todo desde el propio chat, sin tocar ficheros:

- **Especialidades**: escribe el nombre (o un trozo, sin preocuparte de tildes: `informatica`, `ingles`, `infantil`) o el código (`0590107`) y pulsa para marcar ✅ o desmarcar. También puedes explorar la lista por cuerpo (Secundaria, Maestros, FP, EOI...).
- **Ubicación**: comparte tu ubicación GPS o escribe una dirección, municipio o código postal. A partir de ahí cada plaza muestra la distancia estimada al centro (en línea recta, aproximación por carretera y tiempo en coche) y un enlace «Cómo llegar».
- **Plazas abiertas** (`/plazas` o el botón 📋): consulta en ese momento todas las plazas de tus especialidades, ordenadas de la más cercana a la más lejana.
- **Radio** (`/radio`): solo te avisa de los centros que estén a menos de X km.
- **Ajustes** (`/ajustes`): activar o desactivar alertas, tipo de acto (extraordinario, ordinario o ambos) y borrar tus datos.

Al añadir una especialidad no te llegan de golpe todas las plazas que ya estaban publicadas (esas se ven en `/plazas`); solo te avisa de las nuevas.

## Puesta en marcha
1. Crea un bot con [BotFather](https://core.telegram.org/bots/tutorial) y copia el token.
2. `pip install -r requirements.txt`
3. Copia `my_config.py` como `config.py` y pon tu `TOKEN`.
4. `python main.py`

El bot queda escuchando a los usuarios y además consulta PADI cada 30 minutos en días laborables, de 8:00 a 21:00. Se puede cambiar en `config.py` (`CHECK_EVERY_MINUTES`, `CHECK_HOURS`, `CHECK_WEEKENDS`).

Si prefieres lanzar las comprobaciones desde cron en vez de dejar el bot corriendo:

    python main.py --check

Ten en cuenta que en ese modo el bot no responde a los usuarios, así que para que puedan configurarse tiene que estar corriendo `python main.py` en algún sitio.

### Migración desde la versión anterior
Si tu `config.py` todavía tiene el diccionario `users` del formato antiguo, en el primer arranque esos usuarios y sus asignaturas se importan solos a la base de datos (`padi.db`). Después ya se gestionan desde el bot.

## Datos
- `data/especialidades.json`: catálogo de cuerpos y especialidades, sacado de las publicaciones de PADI. El bot lo amplía solo cada día si aparece alguna especialidad nueva.
- `data/centros.json`: centros públicos de la Comunidad de Madrid ([datos abiertos](https://datos.comunidad.madrid/dataset/centros_educativos)) con dirección, teléfono y coordenadas. Si a un centro le faltan coordenadas, se geocodifica con OpenStreetMap (Nominatim) y se guarda en caché.

Para regenerarlos:

    python tools/actualizar_datos.py

## Estructura
```
main.py              punto de entrada (bot o --check)
padi/api.py          cliente de la API de PADI
padi/service.py      plazas por usuario, distancias y detección de novedades
padi/bot.py          comandos, botones y bucle de alertas de Telegram
padi/catalog.py      catálogo de especialidades y directorio de centros
padi/geo.py          UTM a lat/lon, distancias y geocodificación
padi/storage.py      SQLite (usuarios, suscripciones, plazas ya avisadas)
padi/messages.py     formato de los mensajes
tools/               regeneración de los ficheros de data/
legacy/              código y datos de la versión anterior (ya no se usan)
```
