"""PADI-scrapper: bot de Telegram de plazas de sustituciones docentes (Comunidad de Madrid).

    python main.py           # arranca el bot (escucha a los usuarios y comprueba PADI periódicamente)
    python main.py --check   # una única comprobación y envío de alertas (para cron)
"""
import asyncio
import logging
import sys

from padi.bot import build_app, run_check_once

logging.basicConfig(format="%(asctime)s %(levelname)s %(name)s: %(message)s", level=logging.INFO)
logging.getLogger("httpx").setLevel(logging.WARNING)


def main():
    if "--check" in sys.argv:
        asyncio.run(run_check_once())
    else:
        build_app().run_polling()


if __name__ == "__main__":
    main()
