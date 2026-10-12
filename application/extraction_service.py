import pandas as pd
from application.interfaces.Services.IServices import IDataExtractor

class ExtractionService:
    """
    Servicio encargado de orquestar múltiples extractores.
    """
    def __init__(self, extractores: dict[str, IDataExtractor]):
        # Ahora recibimos un diccionario con todos los extractores que queramos
        self.extractores = extractores

    def extract_all(self) -> dict[str, pd.DataFrame]:
        print("\n--- Iniciando Proceso de Extracción Global ---")
        
        datos = {}
        # Recorremos cada extractor y lo ejecutamos
        for nombre, extractor in self.extractores.items():
            print(f"Extrayendo datos de: {nombre}...")
            datos[nombre] = extractor.extract()
            
        print("--- Extracción Global Finalizada ---\n")
        return datos