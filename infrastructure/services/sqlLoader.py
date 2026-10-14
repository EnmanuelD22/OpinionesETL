from datetime import date, datetime
import pandas as pd
from sqlalchemy import MetaData, Table, inspect, select

from infrastructure.database import engine
from application.interfaces.services.ILoader import ILoader

class sqlLoader(ILoader):
    def __init__(self, nombre_tabla, claves_duplicados=None):
        self.nombre_tabla = nombre_tabla
        self.claves_duplicados = claves_duplicados or []

    def cargar(self, datos):
        if datos.empty:
            return 0, 0

        tabla = Table(self.nombre_tabla, MetaData(), autoload_with=engine)
        pendientes = datos.copy()
        columnas_clave = [c for c in self.claves_duplicados if c in pendientes.columns]

        if columnas_clave:
            existentes = pd.read_sql(
                select(*(tabla.c[columna] for columna in columnas_clave)), con=engine
            )
            claves_existentes = {
                tuple(self._normalizar(valor) for valor in fila)
                for fila in existentes.itertuples(index=False, name=None)
            }
            nuevas = pendientes[columnas_clave].apply(
                lambda fila: tuple(self._normalizar(valor) for valor in fila), axis=1
            ).map(lambda clave: clave not in claves_existentes)
            pendientes = pendientes[nuevas]

        claves_primarias = inspect(engine).get_pk_constraint(self.nombre_tabla).get(
            "constrained_columns", []
        )
        if len(claves_primarias) == 1 and claves_primarias[0] in pendientes.columns:
            pendientes = pendientes.drop_duplicates(subset=claves_primarias[0], keep="first")

        rechazados = len(datos) - len(pendientes)
        if not pendientes.empty:
            pendientes.to_sql(self.nombre_tabla, con=engine, if_exists="append", index=False)
        return len(pendientes), rechazados

    @staticmethod
    def _normalizar(valor):
        if pd.isna(valor):
            return None
        if isinstance(valor, (date, datetime, pd.Timestamp)):
            return pd.Timestamp(valor).date()
        return valor