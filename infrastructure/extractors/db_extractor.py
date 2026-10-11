import pandas as pd
from application.interfaces.Services.IServices import IDataExtractor

class DBExtractor(IDataExtractor):

    def __init__(self, query: str, db_engine):
        self.query = query
        self.db_engine = db_engine

    def extract(self) -> pd.DataFrame:
        try:
            df = pd.read_sql(self.query, self.db_engine)
            print(f"Datos extraidos de la BD correctamente. ({len(df)} filas)")
            return df
        except Exception as e:
            print(f"Error al extraer los datos: {e}")
            return pd.DataFrame()