import os
from datetime import datetime

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from .etl import ejecutar_ciclo_etl

INTERVALO_MINUTOS = int(os.getenv("ETL_INTERVALO_MINUTOS", "5"))

scheduler = AsyncIOScheduler()


def iniciar_scheduler():
    scheduler.add_job(
        ejecutar_ciclo_etl, "interval",
        minutes=INTERVALO_MINUTOS,
        id="etl_periodico",
        next_run_time=datetime.now(),  # corre una vez de inmediato al arrancar
        replace_existing=True,
    )
    scheduler.start()
    return scheduler