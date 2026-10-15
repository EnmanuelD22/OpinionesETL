"""Puerto para preparar catálogos y consultar referencias."""

#region Imports
from abc import ABC, abstractmethod

from application.models.etl_results import CatalogContext
#endregion


#region Port
class ICatalogService(ABC):
    """Contrato requerido por el flujo antes de cargar opiniones."""

    @abstractmethod
    def preparar(self) -> CatalogContext:
        """Crea el esquema y deja listos los catálogos base."""

        raise NotImplementedError

    @abstractmethod
    def obtener_referencias(self) -> CatalogContext:
        """Obtiene las claves válidas después de cargar maestros."""

        raise NotImplementedError
#endregion
