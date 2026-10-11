import pandas as pd
import requests
from application.interfaces.Services.IServices import IDataExtractor

class APIExtractor(IDataExtractor):

    def __init__(self, endpoint_url: str):
        self.endpoint_url = endpoint_url

    def extract(self) -> pd.DataFrame:
        try:
            response = requests.get(self.endpoint_url)
            response.raise_for_status()
            data_json = response.json()
            df = pd.DataFrame(data_json)

            print(f"Datos extraidos de la API exitosamente. ({len(df)} filas)")
            return df
        except Exception as e:
            print(f"Error al consumir la API {self.endpoint_url}: {e}")
            return pd.DataFrame()