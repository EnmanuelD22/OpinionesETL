import pandas as pd
from typing import List
from dataclasses import asdict  # Importación vital corregida
from sqlalchemy import text
from application.interfaces.Repository.IOpinionRepository import IOpinionRepository

# Importar entidades de dominio
from domain.entities.Categoria import Categoria
from domain.entities.Cliente import Cliente
from domain.entities.Clasificacion import Clasificacion
from domain.entities.FuenteDatos import Fuente_Datos
from domain.entities.Producto import Producto
from domain.entities.Opinion import Opinion

class SQLOpinionRepository(IOpinionRepository):
    def __init__(self, db_engine):
        self.db_engine = db_engine

    def save_dataframe(self, df: pd.DataFrame, nombre_tabla: str) -> int:
        if df.empty:
            return 0
        try:
            # Hacemos una copia para no alterar el DataFrame original
            df_to_save = df.copy()
            
            # Determinamos dinámicamente el nombre de la columna ID según la tabla
            id_column_map = {
                "Cliente": "IdCliente",
                "Producto": "IdProducto",
                "Fuente_Datos": "IdFuente",
                "Categoria": "IdCategoria",
                "Opinion": "IdOpinion", # Corregido según el script SQL
                "Clasificacion": "IdClasificacion"
            }
            
            id_col = id_column_map.get(nombre_tabla)
            if id_col and id_col in df_to_save.columns:
                df_to_save = df_to_save.drop(columns=[id_col])

            with self.db_engine.begin() as conn:
                # Insertamos los datos dejando que SQL Server asigne los IDs automáticos
                df_to_save.to_sql(
                    name=nombre_tabla,
                    con=conn,
                    if_exists="append",
                    index=False
                )
                    
            return len(df)
            
        except Exception as e:
            print(f"Error al guardar en '{nombre_tabla}': {e}")
            return 0

    # Indentación corregida: ahora estos métodos pertenecen a la clase
    def save_categorias(self, categorias: List[Categoria]) -> int:
        if not categorias:
            return 0
        df = pd.DataFrame([asdict(c) for c in categorias])
        return self.save_dataframe(df, "Categoria")

    def save_clientes(self, clientes: List[Cliente]) -> int:
        if not clientes:
            return 0
        df = pd.DataFrame([asdict(c) for c in clientes])
        return self.save_dataframe(df, "Cliente")

    def save_clasificaciones(self, clasificaciones: List[Clasificacion]) -> int:
        if not clasificaciones:
            return 0
        df = pd.DataFrame([asdict(c) for c in clasificaciones])
        return self.save_dataframe(df, "Clasificacion")

    def save_fuentes_datos(self, fuentes: List[Fuente_Datos]) -> int:
        if not fuentes:
            return 0
        df = pd.DataFrame([asdict(f) for f in fuentes])
        return self.save_dataframe(df, "Fuente_Datos")

    def save_productos(self, productos: List[Producto]) -> int:
        if not productos:
            return 0
        df = pd.DataFrame([asdict(p) for p in productos])
        return self.save_dataframe(df, "Producto")

    def save_opiniones(self, opiniones: List[Opinion]) -> int:
        if not opiniones:
            return 0
        df = pd.DataFrame([asdict(o) for o in opiniones])
        return self.save_dataframe(df, "Opinion")