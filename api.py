"""API de solo lectura para comentarios sociales ya almacenados en OpinionesETL."""

from datetime import date
import logging
from typing import Annotated

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from infrastructure.persistence.models import AnalisisOpinionModel, OpinionModel


logger = logging.getLogger(__name__)


class SocialComment(BaseModel):
    IdOpinion: int
    IdOrigen: str | None
    IdTipoOpinion: int
    IdCliente: int | None
    IdProducto: int | None
    Fecha: date | None
    Comentario: str | None
    IdFuente: int | None
    Canal: str | None
    Puntaje: float | None
    IdClasificacionOriginal: int | None
    IdClasificacionPredicha: int | None


class SocialPage(BaseModel):
    items: list[SocialComment]
    next_after_id: int | None
    has_more: bool


def create_app(db_engine=None) -> FastAPI:
    """Crea la API; el motor inyectado permite probarla sin SQL Server."""
    if db_engine is None:
        from infrastructure.database import get_engine

        db_engine = get_engine()

    api = FastAPI(title="API de comentarios sociales", version="1.0.0")

    @api.get("/api/v1/comentarios-sociales", response_model=SocialPage)
    def listar_comentarios_sociales(
        after_id: Annotated[int, Query(ge=0)] = 0,
        limit: Annotated[int, Query(ge=1, le=500)] = 100,
    ) -> SocialPage:
        opinion = OpinionModel
        analisis = AnalisisOpinionModel
        consulta = (
            select(
                opinion.IdOpinion,
                opinion.IdOrigen,
                opinion.IdTipoOpinion,
                opinion.IdCliente,
                opinion.IdProducto,
                opinion.Fecha,
                opinion.Comentario,
                opinion.IdFuente,
                opinion.Canal,
                opinion.Puntaje,
                opinion.IdClasificacion.label("IdClasificacionOriginal"),
                analisis.IdClasificacion.label("IdClasificacionPredicha"),
            )
            .outerjoin(analisis, analisis.IdOpinion == opinion.IdOpinion)
            .where(opinion.IdTipoOpinion == 3, opinion.IdOpinion > after_id)
            .order_by(opinion.IdOpinion)
            .limit(limit + 1)
        )
        try:
            with db_engine.connect() as connection:
                rows = [dict(row) for row in connection.execute(consulta).mappings()]
        except SQLAlchemyError as error:
            logger.exception("Error al consultar comentarios sociales")
            raise HTTPException(
                status_code=503, detail="Base relacional no disponible"
            ) from error

        has_more = len(rows) > limit
        items = [SocialComment.model_validate(row) for row in rows[:limit]]
        return SocialPage(
            items=items,
            next_after_id=items[-1].IdOpinion if has_more else None,
            has_more=has_more,
        )

    return api


app = create_app()
