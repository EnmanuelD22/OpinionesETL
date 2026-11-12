"""Extracción selectiva de reseñas ya almacenadas en la base relacional."""

import pandas as pd
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from application.exceptions.etl_exceptions import ExtractionError
from application.interfaces.services.IExtractor import IExtractor
from infrastructure.persistence.models import AnalisisOpinionModel, OpinionModel


REVIEW_COLUMNS = (
    "IdOpinion", "IdOrigen", "IdTipoOpinion", "IdCliente", "IdProducto",
    "Fecha", "Comentario", "IdFuente", "Canal", "Puntaje",
    "IdClasificacionOriginal", "IdClasificacionPredicha",
)


class OpinionReviewExtractor(IExtractor):
    """Lee solo `Opinion` de tipo reseña; conserva ambas clasificaciones."""

    def __init__(self, db_engine):
        self.db_engine = db_engine

    def extract(self) -> pd.DataFrame:
        opinion = OpinionModel
        analisis = AnalisisOpinionModel
        query = (
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
            .where(opinion.IdTipoOpinion == 2)
            .order_by(opinion.IdOpinion)
        )
        try:
            return pd.read_sql(query, con=self.db_engine)[list(REVIEW_COLUMNS)]
        except (SQLAlchemyError, pd.errors.DatabaseError, KeyError, ValueError) as error:
            raise ExtractionError("No fue posible leer las reseñas relacionales") from error
