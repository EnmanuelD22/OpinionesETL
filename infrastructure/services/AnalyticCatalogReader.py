"""Catálogos relacionales para validar una carga analítica selectiva."""

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from application.exceptions.etl_exceptions import CatalogError
from application.services.analytic_preparation import AnalyticCatalog
from infrastructure.persistence import models as m


class AnalyticCatalogReader:
    def __init__(self, db_engine):
        self.db_engine = db_engine

    def read(self) -> AnalyticCatalog:
        try:
            with self.db_engine.connect() as connection:
                clients = set(connection.scalars(select(m.ClienteModel.IdCliente)))
                products = set(connection.scalars(
                    select(m.ProductoModel.IdProducto)
                    .join(m.CategoriaModel, m.ProductoModel.IdCategoria == m.CategoriaModel.IdCategoria)
                ))
                sources = set(connection.scalars(
                    select(m.FuenteDatosModel.IdFuente)
                    .where(m.FuenteDatosModel.TipoFuente.is_not(None))
                ))
                classifications = set(connection.scalars(
                    select(m.ClasificacionModel.IdClasificacion)
                ))
                survey_ids = {}
                for origin_id, opinion_id in connection.execute(
                    select(m.OpinionModel.IdOrigen, m.OpinionModel.IdOpinion)
                    .where(m.OpinionModel.IdTipoOpinion == 1,
                           m.OpinionModel.IdOrigen.is_not(None))
                ):
                    if origin_id in survey_ids:
                        raise CatalogError(f"IdOrigen de encuesta ambiguo: {origin_id}")
                    survey_ids[str(origin_id)] = opinion_id
            return AnalyticCatalog(clients, products, sources, classifications, survey_ids)
        except SQLAlchemyError as error:
            raise CatalogError(f"No fue posible leer catálogos analíticos: {error}") from error
