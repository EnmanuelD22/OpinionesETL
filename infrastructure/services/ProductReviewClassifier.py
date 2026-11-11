"""Candidato local basado en estrellas de reseñas; no participa aún en el ETL."""

from pathlib import Path

from application.interfaces.services.ISentimentClassifier import ISentimentClassifier
from application.services.sentiment import Prediccion

MODEL_ID = "nlptown/bert-base-multilingual-uncased-sentiment"
MODEL_REVISION = "8f6f4e3a8f70be4b65d3a4a8762b6d781cda240d"
MODEL_VERSION = "nlptown-8f6f4e3"
STAR_LABELS = {0: "1 star", 1: "2 stars", 2: "3 stars", 3: "4 stars", 4: "5 stars"}


class ProductReviewClassifier(ISentimentClassifier):
    def __init__(self, cache_dir: Path = Path(".cache/huggingface"), local_files_only: bool = False):
        try:
            import torch
            from transformers import AutoModelForSequenceClassification, AutoTokenizer
        except ImportError as error:
            raise RuntimeError("Instala requirements-nlp.txt para evaluar el modelo") from error

        self.torch = torch
        cache_dir = Path(cache_dir)
        cache_dir.mkdir(parents=True, exist_ok=True)
        if local_files_only:
            from huggingface_hub import hf_hub_download

            config_path = hf_hub_download(
                MODEL_ID, "config.json", revision=MODEL_REVISION,
                cache_dir=str(cache_dir), local_files_only=True,
            )
            # Conservar la ruta del snapshot: resolve() seguiría el enlace a blobs/.
            model_ref = str(Path(config_path).absolute().parent)
            options = {"local_files_only": True}
        else:
            model_ref = MODEL_ID
            options = {"revision": MODEL_REVISION, "cache_dir": str(cache_dir)}
        self.tokenizer = AutoTokenizer.from_pretrained(model_ref, use_fast=False, **options)
        self.model = AutoModelForSequenceClassification.from_pretrained(
            model_ref, use_safetensors=True, trust_remote_code=False, **options
        )
        self.model.eval()
        if self.model.config.id2label != STAR_LABELS:
            raise ValueError("Etiquetas de estrellas inesperadas en el modelo")

    def predict_batch(self, comments: list[str], batch_size: int = 16) -> list[Prediccion]:
        if batch_size < 1:
            raise ValueError("batch_size debe ser positivo")
        if any(not isinstance(text, str) or not text.strip() for text in comments):
            raise ValueError("Todos los comentarios deben contener texto")
        predictions = []
        for start in range(0, len(comments), batch_size):
            batch = comments[start:start + batch_size]
            tokens = self.tokenizer(batch, padding=True, truncation=True,
                                    max_length=128, return_tensors="pt")
            with self.torch.inference_mode():
                logits = self.model(**tokens).logits
                probabilities = self.torch.softmax(logits, dim=-1).tolist()
            for row in probabilities:
                if len(row) != 5:
                    raise ValueError("El modelo no devolvió cinco puntuaciones")
                grouped = {1: row[3] + row[4], 2: row[0] + row[1], 3: row[2]}
                label = max(grouped, key=grouped.__getitem__)
                predictions.append(Prediccion(label, round(grouped[label], 4),
                                               MODEL_VERSION))
        return predictions
