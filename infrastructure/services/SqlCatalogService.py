"""Adaptador SQL para preparar catálogos y claves de referencia."""

#region Imports
import pandas as pd
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from application.exceptions.etl_exceptions import CatalogError
from application.interfaces.services.ICatalogService import ICatalogService
from application.models.etl_results import CatalogContext
from application.interfaces.services.IExtractor import IExtractor
from infrastructure.persistence.base import Base
from infrastructure.persistence import models as _models  # noqa: F401
#endregion


#region Adapter
class SqlCatalogService(ICatalogService):
    """Implementa el puerto de catálogos sobre el esquema SQLAlchemy."""

    #region Construction
    def __init__(self, db_engine, products_extractor: IExtractor):
        self.db_engine = db_engine
        self.products_extractor = products_extractor
    #endregion

    #region Catalog preparation
    def preparar(self) -> CatalogContext:
        """Crea tablas y registra clasificaciones y categorías faltantes."""

        try:
            Base.metadata.create_all(self.db_engine)
            self._preparar_clasificaciones()
            productos = self.products_extractor.extract()
            self._preparar_categorias(productos)
            return CatalogContext(
                category_map=self._mapa_categorias(),
                references={},
            )
        except (SQLAlchemyError, OSError, ValueError, KeyError) as error:
            raise CatalogError(f"No fue posible preparar catálogos: {error}") from error

    def _preparar_clasificaciones(self) -> None:
        existentes = self._valores_existentes("Clasificacion", "IdClasificacion")
        catalogo = pd.DataFrame([
            {"IdClasificacion": 1, "Tipo": "Positiva"},
            {"IdClasificacion": 2, "Tipo": "Negativa"},
            {"IdClasificacion": 3, "Tipo": "Neutra"},
        ])
        faltantes = catalogo[~catalogo["IdClasificacion"].isin(existentes)]
        if not faltantes.empty:
            faltantes.to_sql(
                "Clasificacion", con=self.db_engine, if_exists="append", index=False
            )

    def _preparar_categorias(self, productos: pd.DataFrame) -> None:
        columna_categoria = next(
            (
                columna for columna in (
                    "Categoría", "CategorÃ­a", "CategorÃƒÂ­a"
                ) if columna in productos.columns
            ),
            None,
        )
        if columna_categoria is None:
            raise ValueError("products.csv debe incluir la columna Categoría")

        nombres = productos[columna_categoria].dropna().astype(str).str.strip().unique()
        categorias = self._valores_existentes("Categoria", "Nombre")
        faltantes = sorted(set(nombres) - set(categorias))
        if faltantes:
            pd.DataFrame({"Nombre": faltantes}).to_sql(
                "Categoria", con=self.db_engine, if_exists="append", index=False
            )
    #endregion

    #region References
    def obtener_referencias(self) -> CatalogContext:
        """Obtiene claves maestras para que aplicación valide opiniones."""

        try:
            return CatalogContext(
                category_map=self._mapa_categorias(),
                references={
                    "IdCliente": self._valores_existentes("Cliente", "IdCliente"),
                    "IdProducto": self._valores_existentes("Producto", "IdProducto"),
                    "IdFuente": self._valores_existentes("Fuente_Datos", "IdFuente"),
                    "IdClasificacion": self._valores_existentes(
                        "Clasificacion", "IdClasificacion"
                    ),
                },
            )
        except (SQLAlchemyError, OSError, ValueError, KeyError) as error:
            raise CatalogError(f"No fue posible obtener referencias: {error}") from error

    def _mapa_categorias(self) -> dict[str, int]:
        categorias = pd.read_sql(
            text("SELECT IdCategoria, Nombre FROM Categoria"),
            con=self.db_engine,
        )
        return dict(zip(categorias["Nombre"], categorias["IdCategoria"]))

    def _valores_existentes(self, tabla: str, columna: str) -> set:
        consulta = text(f"SELECT [{columna}] FROM [{tabla}]")
        datos = pd.read_sql(consulta, con=self.db_engine)
        return set(datos[columna])
    #endregion
#endregion
