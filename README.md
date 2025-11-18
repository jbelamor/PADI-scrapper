# PADI-scrapper
Este repositorio es un bot de Telegram que obtiene los resultados de PADI (https://gestiona.comunidad.madrid/padi/#!/main-menu) y te notifica de los nuevos puestos que se han ofertado.

La primera vez que se ejecuta te notifica de todos los que existen. A partir de ahí, va guardando los resultados en un fichero que usa como histórico y sólo te va notificando de los nuevos resultados que vayan apareciendo.

# Uso
## En local
Para poder correr tu propio instancia de este bot necesitas dos cosas:
1. El token de tu propio bot
2. El chat id de tu conversación con el bot

### Bot token
Existen mil tutoriales sobre cómo hacer esto, aquí la documentación oficial [Telegram - BotFather](https://core.telegram.org/bots/tutorial)

### Chat ID
Una vez que hayas creado tu bot, inicia una conversación con él y dale a START.
Después, desde el navegador ve a la dirección 'https://api.telegram.org/bot<BOT_TOKEN>/getUpdates' sustitutendo donde pone "<BOT_TOKEN>" con el token que has obtenido en el paso anterior.

    "ok":true,"result":[{"update_id":00000000,
    "message":{"message_id":1,"from":{"id":XXXXXXXXX, ...

El número que verás donde pone "XXXXXXX" es el chat ID de tu conversación con tu bot.

### Config
1. Cambia el nombre al fichero "my_config.py" por "config.py"
2. Sustituye los valores por los nuevos valores que has generado en los pasos anteriores

### Ejecuta
Corriendo el fichero "main.py" ya tendrías el bot funcionando. 

Ahora puedes meter esto en un cron o donde quieras para que se ejecute diariamente a las 9:00 y a las 15:00 para que te actualice con los nuevos ofertados

#### Bonus track: crontab
Puedes automatizar la notificación si incluyes la ejecución de tu programa como un cron job en Linux. Para ello:
1. Crea un script `sh` que ejecute el comando de python:
    python3 /home/usuario/PADI-scrapper/main.py
2. Dale permisos de ejecución
    chmod +x padi_checker.sh
3. Abre el editor de crontabs
    crontab -e
4. Añade esta línea. OJO a la ruta de tu fichero. Esta línea ejecutará el script todos los días de la semana (excepto fin de semana a las 9:10):
    10 9 * * 1-5    /home/usuario/padi_checker.sh


## Bot ya publicado (en desarrollo)
Existe un bot que se llama [¿Qué pasa PADI?](https://t.me/que_pasa_padi_bot)

La idea es que puedas definir qué asignatura te interesa consultar y definir los filtros que te interesen y el bot te informará de ello.

De momento no pienso seguir trabajando en esta línea, pero si suficientes personas me lo piden, lo desarrollo.