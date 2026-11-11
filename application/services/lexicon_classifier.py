"""Adaptador del clasificador ya usado por el ETL."""

from application.interfaces.services.ISentimentClassifier import ISentimentClassifier
from application.services.sentiment import Prediccion, clasificar


class LexiconClassifier(ISentimentClassifier):
    def predict_batch(self, comments: list[str], batch_size: int = 16) -> list[Prediccion]:
        if batch_size < 1:
            raise ValueError("batch_size debe ser positivo")
        if any(not isinstance(text, str) or not text.strip() for text in comments):
            raise ValueError("Todos los comentarios deben contener texto")
        return [clasificar(comment) for comment in comments]
