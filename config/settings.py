import os 
from dotenv import load_dotenv

load_dotenv()

class Settings:
    DB_SERVER = os.getenv("DB_SERVER", "localhost")
    DB_NAME = os.getenv("DB_NAME", "OpinionesETL")
    DB_DRIVER = os.getenv("DB_DRIVER", "ODBC Driver 17 for SQL Server")
    DB_TRUSTED_CONNECTION = os.getenv("DB_TRUSTED_CONNECTION", "yes")
    DB_USER = os.getenv("DB_USER", "")
    DB_PASSWORD = os.getenv("DB_PASSWORD", "")

    @property
    def connection_string(self) -> str:
        if self.DB_TRUSTED_CONNECTION.lower() == "yes":
            return (f"mssql+pyodbc://@{self.DB_SERVER}/{self.DB_NAME}?"
                f"driver={self.DB_DRIVER}&trusted_connection=yes")


settings = Settings()
