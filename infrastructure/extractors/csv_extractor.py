import pandas as pd
from application.interfaces.Services.IServices import IDataExtractor

class CSVExtractor(IDataExtractor):

    def __init__(self, file_path: str):
        self.file_path = file_path

    def extract(self) -> pd.DataFrame:
        try:
            df = pd.read_csv(self.file_path)
            print(f"Archivo {self.file_path} extraido correctamente. ({len(df)} filas)")
            return df
        except Exception as e:
            print(f"Error al leer el archivo {self.file_path}: {e}")
            return pd.DataFrame()
