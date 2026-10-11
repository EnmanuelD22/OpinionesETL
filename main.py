from infrastructure.extractors.csv_extractor import CSVExtractor
from infrastructure.extractors.db_extractor import DBExtractor
from infrastructure.extractors.api_extractor import APIExtractor
from infrastructure.database import engine
from application.extraction_service import ExtractionService

def test_orquestador():
    print("Iniciando prueba del Orquestador de Extracción...\n")
    
    # 1. Preparamos las herramientas (Infraestructura)
    csv_ext = CSVExtractor("data/clients.csv")
    
    # Consulta de prueba que devuelve la versión de tu SQL Server
    db_ext = DBExtractor("SELECT @@VERSION AS Version", engine) 
    
    # API pública de prueba que devuelve comentarios falsos
    api_ext = APIExtractor("https://jsonplaceholder.typicode.com/comments?postId=1")
    
    # 2. Inyectamos las herramientas al coordinador (Aplicación)
    servicio = ExtractionService(csv_ext, db_ext, api_ext)
    
    # 3. ¡El coordinador hace todo el trabajo pesado!
    datos = servicio.extract_all()
    
    # 4. Revisamos qué nos entregó
    print("\n--- Resumen de Datos Extraídos ---")
    for llave, df in datos.items():
        print(f"[{llave}]: {len(df)} filas.")
        if not df.empty:
            # Imprimimos solo las primeras 2 filas de cada fuente para no llenar toda la pantalla
            print(df.head(2)) 
        print("-" * 50)

if __name__ == "__main__":
    test_orquestador()