from fastapi import APIRouter

from ..etl import ejecutar_ciclo_etl

router = APIRouter(prefix="/etl", tags=["ETL"])


@router.post("/ejecutar")
async def ejecutar_etl_manual():
    resultado = await ejecutar_ciclo_etl()
    return resultado