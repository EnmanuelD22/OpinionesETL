import pandas as pd
from application.interfaces.Services.IServices import IOpinionTransformer

class TransformationService(IOpinionTransformer):
    
    def transform(self, df: pd.DataFrame, fuente_tipo: str) -> pd.DataFrame:
        print(f"Procesando limpieza para la fuente: {fuente_tipo}...")
        df_limpio = df.copy()
        
        if df_limpio.empty:
            return df_limpio
        
        if fuente_tipo == "clientes_csv":
            df_limpio = df_limpio.drop_duplicates()
            
        elif fuente_tipo == "productos_csv":
            # Renombramos la columna original temporalmente para conservar el texto real
            df_limpio = df_limpio.rename(columns={'Categoría': 'NombreCategoria'})
            
            # Creamos un mapeo único de categorías de texto a un ID numérico (ej: Electrónica -> 1, Juguetes -> 2)
            categorias_unicas = df_limpio['NombreCategoria'].unique()
            categoria_to_id = {cat: idx + 1 for idx, cat in enumerate(categorias_unicas)}
            
            # Asignamos el IdCategoria numérico para la relación con los productos
            df_limpio['IdCategoria'] = df_limpio['NombreCategoria'].map(categoria_to_id)
            
        elif fuente_tipo == "fuente_datos_csv":
            df_limpio['FechaCarga'] = pd.to_datetime(df_limpio['FechaCarga'])
            df_limpio['IdFuente'] = df_limpio['IdFuente'].astype(str).str.replace('F', '').astype(int)

        elif fuente_tipo == "opiniones_api":
            df_limpio = df_limpio.rename(columns={
                'name': 'titulo_opinion',
                'body': 'comentario'
            })
            df_limpio = df_limpio[['id', 'email', 'titulo_opinion', 'comentario']]

        print(f"Transformacion de '{fuente_tipo}' completada.")
        return df_limpio