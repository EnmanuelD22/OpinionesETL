"""Configuración única de la aplicación.

La configuración pertenece a la frontera de la aplicación y no a un adaptador
concreto. De esta forma SQLAlchemy, los extractores y el punto de arranque
consumen la misma fuente de valores.
"""

#region Imports
from dataclasses import dataclass
import os
from urllib.parse import quote_plus

from dotenv import load_dotenv
#endregion


#region Settings
@dataclass(frozen=True)
class Settings:
    """Valores de configuración necesarios para ejecutar el ETL."""

    db_server: str = "localhost"
    db_name: str = "OpinionesETL"
    db_driver: str = "ODBC Driver 17 for SQL Server"
    db_trusted_connection: bool = True
    db_user: str = ""
    db_password: str = ""

    @classmethod
    def from_environment(cls) -> "Settings":
        """Crea la configuración leyendo `.env` y variables de entorno.

        Se aceptan temporalmente los nombres `SQL_*` como compatibilidad con
        instalaciones anteriores; `DB_*` es la nomenclatura oficial.
        """

        load_dotenv()
        trusted = os.getenv(
            "DB_TRUSTED_CONNECTION",
            os.getenv("SQL_TRUSTED_CONNECTION", "yes"),
        ).strip().lower() in {"1", "true", "yes", "y", "si"}
        return cls(
            db_server=os.getenv("DB_SERVER", os.getenv("SQL_SERVER", "localhost")),
            db_name=os.getenv("DB_NAME", os.getenv("SQL_DATABASE", "OpinionesETL")),
            db_driver=os.getenv("DB_DRIVER", os.getenv("ODBC_DRIVER", "ODBC Driver 17 for SQL Server")),
            db_trusted_connection=trusted,
            db_user=os.getenv("DB_USER", ""),
            db_password=os.getenv("DB_PASSWORD", ""),
        )

    @property
    def connection_string(self) -> str:
        """Devuelve la URL de conexión que consume SQLAlchemy."""

        driver = quote_plus(self.db_driver)
        if self.db_trusted_connection:
            return (
                f"mssql+pyodbc://@{self.db_server}/{self.db_name}?"
                f"driver={driver}&trusted_connection=yes&encrypt=yes&trustServerCertificate=yes"
            )

        user = quote_plus(self.db_user)
        password = quote_plus(self.db_password)
        return (
            f"mssql+pyodbc://{user}:{password}@{self.db_server}/{self.db_name}?"
            f"driver={driver}&encrypt=yes&trustServerCertificate=yes"
        )


settings = Settings.from_environment()
#endregion
