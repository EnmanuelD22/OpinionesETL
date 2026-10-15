"""Adaptador de extracción desde archivos CSV."""

#region Imports
from pathlib import Path

import pandas as pd

from application.exceptions.etl_exceptions import ExtractionError
from application.interfaces.services.IExtractor import IExtractor
#endregion


#region Adapter
class CsvExtractor(IExtractor):
    """Implementa `IExtractor` para un archivo CSV local."""

    #region Construction
    def __init__(self, file_path):
        self.file_path = Path(file_path)
    #endregion

    #region Extraction
    def extract(self):
        try:
            data = pd.read_csv(self.file_path, encoding="utf-8")
        except (OSError, UnicodeError, pd.errors.ParserError) as error:
            raise ExtractionError(
                f"Error al leer el archivo CSV {self.file_path}: {error}"
            ) from error
        if data.empty:
            raise ExtractionError(f"El archivo CSV {self.file_path} está vacío.")
        return data
    #endregion
#endregion
