from infrastructure.extractors.csv_extractor import CSVExtractor
from infrastructure.extractors.db_extractor import DBExtractor
from infrastructure.extractors.api_extractor import APIExtractor
from infrastructure.database import engine
from application.extraction_service import ExtractionService
from application.transformation_service import TransformationService 
# --- NUEVAS IMPORTACIONES ---
from infrastructure.repositories.opinion_repository import SQLOpinionRepository
from application.loading_service import LoadingService

def test_pipeline():
    print("Iniciando Pipeline ETL...\n")
    
    # ==========================================
    # FASE 1: EXTRACCIÓN (E)
    # ==========================================
    mis_extractores = {
        "clientes_csv": CSVExtractor("data/clients.csv"),
        "productos_csv": CSVExtractor("data/products.csv"),
        "fuente_datos_csv": CSVExtractor("data/fuente_datos.csv")
    }
    
    servicio_extraccion = ExtractionService(mis_extractores)
    datos_crudos = servicio_extraccion.extract_all()
    
    # ==========================================
    # FASE 2: TRANSFORMACIÓN (T)
    # ==========================================
    print("\n--- Iniciando Fase de Transformación ---")
    transformador = TransformationService()
    datos_limpios = {}
    
    for fuente, df in datos_crudos.items():
        datos_limpios[fuente] = transformador.transform(df, fuente)
        
    # ==========================================
    # FASE 3: CARGA (L)
    # ==========================================
    # 1. Instanciamos el repositorio pasándole el motor de la BD
    repo = SQLOpinionRepository(engine)
    
    # 2. Se lo inyectamos al servicio de carga
    servicio_carga = LoadingService(repo)
    
    # 3. ¡Ejecutamos la carga!
    servicio_carga.load_data(datos_limpios)

if __name__ == "__main__":
    test_pipeline()