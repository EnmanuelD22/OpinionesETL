from abc import ABC, abstractmethod
import pandas as pd

class IExtractor(ABC):
    @abstractmethod
    def extract(self) -> pd.DataFrame: 
        pass 