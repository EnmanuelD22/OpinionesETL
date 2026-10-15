"""Entrada mínima del proceso ETL."""

#region Imports
from infrastructure.composition import create_application
#endregion


#region Entry point
def main() -> dict[str, int]:
    """Construye y ejecuta la aplicación configurada."""

    return create_application().ejecutar()
#endregion


if __name__ == "__main__":
    main()
