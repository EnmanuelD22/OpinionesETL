import pandas as pd
from application.interfaces.Services.IServices import IDataExtractor

class ExtractionService:
    def __init__(self, csv_ext: IDataExtractor, db_ext: IDataExtractor, api_ext: IDataExtractor):
        self.csv_ext = csv_ext
        self.db_ext = db_ext
        self.api_ext = api_ext

    def extract_all(self) -> dict[str, pd.DataFrame]:
        print("\n--- Iniciando Proceso de Extraccion Global ---")

        datos = {
            "clientes_csv": self.csv_ext.extract(),
            "ventas_db": self.db_ext.extract(),
            "opiniones_api": self.api_ext.extract()
        }

        print("--- Extraccion Global Finalizada ---\n")
        return datos