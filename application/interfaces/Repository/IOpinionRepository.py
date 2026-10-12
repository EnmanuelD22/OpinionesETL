from abc import ABC, abstractmethod
import pandas as pd

class IOpinionRepository(ABC):
    @abstractmethod
    def save_dataframe(self, df: pd.DataFrame, nombre_tabla) -> int:
        pass