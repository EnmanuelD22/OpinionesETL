from abc import ABC, abstractmethod
import pandas as pd

class IDataExtractor(ABC):
    @abstractmethod
    def extract(self) -> pd.DataFrame:
        pass

class IOpinionTransformer(ABC):
    @abstractmethod
    def transform(self, df: pd.DataFrame, fuente_tipo: str) -> pd.DataFrame:
        pass