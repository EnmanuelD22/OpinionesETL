import pandas as pd
from application.interfaces.services.IExtractor import IExtractor

class CsvExtractor(IExtractor):
    def __init__(self, file_path):
        self.file_path = file_path

    def extract(self):
        try:
            data = pd.read_csv(self.file_path, encoding='utf-8')
        except (OSError, UnicodeError, pd.errors.ParserError) as e:
            raise RuntimeError(f"Error al leer el archivo CSV {self.file_path}: {e}")
        if data.empty:
            raise ValueError(f"El archivo CSV {self.file_path} está vacío.")
        return data