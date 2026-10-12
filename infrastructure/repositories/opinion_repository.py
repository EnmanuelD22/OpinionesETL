import pandas as pd
from sqlalchemy import text
from application.interfaces.Repository.IOpinionRepository import IOpinionRepository

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
                "Categoria": "IdCategoria"
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