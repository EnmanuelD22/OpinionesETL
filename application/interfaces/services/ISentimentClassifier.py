"""Contrato de inferencia para clasificar opiniones sin acoplar el ETL al modelo."""

from abc import ABC, abstractmethod

from application.services.sentiment import Prediccion


class ISentimentClassifier(ABC):
    @abstractmethod
    def predict_batch(self, comments: list[str], batch_size: int = 16) -> list[Prediccion]:
        """Devuelve una predicción por comentario en el mismo orden."""
        raise NotImplementedError
