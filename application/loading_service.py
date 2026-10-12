import pandas as pd
from application.interfaces.Repository.IOpinionRepository import IOpinionRepository

class LoadingService:
    def __init__(self, repository: IOpinionRepository):
        self.repository = repository

    def load_data(self, datos_limpios: dict[str, pd.DataFrame]):
        print("\n--- Iniciando Fase de Carga (load) ---")

        if "productos_csv" in datos_limpios:
            df_prod = datos_limpios["productos_csv"]
            if 'IdCategoria' in df_prod.columns and 'NombreCategoria' in df_prod.columns:
                # Extraemos los pares únicos de IdCategoria y NombreCategoria para llenar la tabla padre primero
                df_categorias = df_prod[['IdCategoria', 'NombreCategoria']].drop_duplicates().copy()
                
                # Renombramos 'NombreCategoria' a 'Nombre' para que coincida exactamente con la columna de la base de datos
                df_categorias = df_categorias.rename(columns={'NombreCategoria': 'Nombre'})
                
                print(f"Cargando {len(df_categorias)} registros únicos en la tabla 'Categoria'...")
                self.repository.save_dataframe(df_categorias, "Categoria")

        mapeo_tablas = {
            "clientes_csv": "Cliente",
            "productos_csv": "Producto",
            "fuente_datos_csv": "Fuente_Datos"
        }

        for fuente, nombre_tabla_sql in mapeo_tablas.items():
            if fuente in datos_limpios:
                df = datos_limpios[fuente]
                
                # Si estamos cargando productos, debemos remover 'NombreCategoria' temporalmente 
                # ya que esa columna es exclusiva para la tabla Categoria y no existe en la tabla Producto de SQL
                if fuente == "productos_csv" and 'NombreCategoria' in df.columns:
                    df = df.drop(columns=['NombreCategoria'])

                print(f"Cargando {len(df)} registros en la tabla '{nombre_tabla_sql}'...")

                filas_guardadas = self.repository.save_dataframe(df, nombre_tabla_sql)
                if filas_guardadas > 0:
                    print(f"Tablas '{nombre_tabla_sql}' actualizada.")

        print("--- Fase de Carga Finalizada ---\n")