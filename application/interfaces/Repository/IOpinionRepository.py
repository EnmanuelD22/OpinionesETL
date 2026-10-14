from abc import ABC, abstractmethod
from typing import List
import pandas as pd
from domain.entities.Categoria import Categoria
from domain.entities.Cliente import Cliente
from domain.entities.Clasificacion import Clasificacion
from domain.entities.FuenteDatos import Fuente_Datos
from domain.entities.Producto import Producto
from domain.entities.Opinion import Opinion

class IOpinionRepository(ABC):
    # region Abstract methods
    @abstractmethod
    def save_dataframe(self, df: pd.DataFrame, nombre_tabla: str) -> int:
        pass

    @abstractmethod
    def save_categorias(self, categorias: List[Categoria]) -> int:
        pass

    @abstractmethod
    def save_clientes(self, clientes: List[Cliente]) -> int:
        pass
    
    @abstractmethod
    def save_clasificaciones(self, clasificaciones: List[Clasificacion]) -> int:
        pass

    @abstractmethod
    def save_fuentes_datos(self, fuentes: List[Fuente_Datos]) -> int:
        pass

    @abstractmethod
    def save_productos(self, productos: List[Producto]) -> int:
        pass

    @abstractmethod
    def save_opiniones(self, opiniones: List[Opinion]) -> int:
        pass
    # endregion