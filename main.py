"""Entrada mínima del proceso ETL."""

#region Imports
from infrastructure.composition import create_application, create_sentiment_classifier
from infrastructure.database import get_engine, get_dw_engine
from infrastructure.services.WarehouseSync import sincronizar_warehouse
#endregion


#region Entry point
def main() -> dict[str, int]:
    """Construye y ejecuta la aplicación configurada."""

    application = create_application()
    resultado = application.ejecutar()
    dw = get_dw_engine()
    try:
        print("Carga analítica:", sincronizar_warehouse(
            get_engine(), dw, classifier=create_sentiment_classifier()
        ))
    finally:
        dw.dispose()
    return resultado
#endregion


if __name__ == "__main__":
    main()
