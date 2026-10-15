"""Adaptador de carga tabular para SQL Server."""

#region Imports
from datetime import date, datetime

import pandas as pd
from sqlalchemy import MetaData, Table, inspect, select
from sqlalchemy.exc import SQLAlchemyError

from application.exceptions.etl_exceptions import PersistenceError
from application.interfaces.services.ILoader import ILoader
from infrastructure.database import get_engine
#endregion


#region Adapter
class SqlLoader(ILoader):
    """Carga lotes evitando duplicados definidos por el pipeline."""

    #region Construction
    def __init__(self, nombre_tabla, claves_duplicados=None, db_engine=None):
        self.nombre_tabla = nombre_tabla
        self.claves_duplicados = list(claves_duplicados or [])
        self.db_engine = db_engine or get_engine()
    #endregion

    #region Loading
    def cargar(self, datos):
        if datos.empty:
            return 0, 0

        try:
            tabla = Table(self.nombre_tabla, MetaData(), autoload_with=self.db_engine)
            pendientes = datos.copy()
            columnas_clave = [c for c in self.claves_duplicados if c in pendientes.columns]

            if columnas_clave:
                existentes = pd.read_sql(
                    select(*(tabla.c[columna] for columna in columnas_clave)),
                    con=self.db_engine,
                )
                claves_existentes = {
                    tuple(self._normalizar(valor) for valor in fila)
                    for fila in existentes.itertuples(index=False, name=None)
                }
                nuevas = pendientes[columnas_clave].apply(
                    lambda fila: tuple(self._normalizar(valor) for valor in fila), axis=1
                ).map(lambda clave: clave not in claves_existentes)
                pendientes = pendientes[nuevas]

            claves_primarias = inspect(self.db_engine).get_pk_constraint(
                self.nombre_tabla
            ).get("constrained_columns", [])
            if len(claves_primarias) == 1 and claves_primarias[0] in pendientes.columns:
                pendientes = pendientes.drop_duplicates(
                    subset=claves_primarias[0], keep="first"
                )

            rechazados = len(datos) - len(pendientes)
            if not pendientes.empty:
                with self.db_engine.begin() as connection:
                    pendientes.to_sql(
                        self.nombre_tabla,
                        con=connection,
                        if_exists="append",
                        index=False,
                    )
            return len(pendientes), rechazados
        except (SQLAlchemyError, ValueError, TypeError, KeyError, AttributeError) as error:
            raise PersistenceError(
                f"Error al cargar la tabla '{self.nombre_tabla}': {error}"
            ) from error

    @staticmethod
    def _normalizar(valor):
        if pd.isna(valor):
            return None
        if isinstance(valor, (date, datetime, pd.Timestamp)):
            return pd.Timestamp(valor).date()
        return valor
    #endregion


# Compatibilidad con el nombre original. El nombre oficial usa PascalCase.
sqlLoader = SqlLoader
#endregion
