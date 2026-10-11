from abc import ABC, abstractmethod
import pandas as pd

class IOpinionRepository(ABC):
    @abstractmethod
    def save_opiniones(self, df: pd.DataFrame) -> init:
        pass