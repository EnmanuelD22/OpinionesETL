"""Prepara únicamente las tres fuentes acordadas para la carga analítica."""

from dataclasses import dataclass
from uuid import uuid4

import pandas as pd

from application.models.schema import DataSchema, FieldRule
from application.services.DataTransformer import DataTransformer


@dataclass(frozen=True)
class AnalyticCatalog:
    clients: set[int]
    products: set[int]
    sources: set[int]
    classifications: set[int]
    survey_ids: dict[str, int]


class AnalyticPreparation:
    """Extrae, valida y entrega un lote atómico de staging."""

    def __init__(self, survey_extractor, review_extractor, social_extractor,
                 catalog_reader, staging_writer):
        self.extractors = (
            ("encuesta", 1, survey_extractor),
            ("resena", 2, review_extractor),
            ("social", 3, social_extractor),
        )
        self.catalog_reader = catalog_reader
        self.staging_writer = staging_writer

    def run(self, batch_id: str | None = None) -> dict:
        batch_id = batch_id or str(uuid4())
        catalog = self.catalog_reader.read()
        prepared: list[dict] = []
        rejected: list[dict] = []
        counts = {}
        for origin, kind, extractor in self.extractors:
            source_prepared, source_rejected, source_counts = self._prepare_source(
                origin, kind, extractor, catalog, batch_id
            )
            prepared.extend(source_prepared)
            rejected.extend(source_rejected)
            counts[origin] = source_counts

        self.staging_writer.write(batch_id, prepared, rejected)
        return {"IdEjecucion": batch_id, "fuentes": counts,
                "preparados": len(prepared), "rechazados": len(rejected)}

    @classmethod
    def _prepare_source(cls, origin, kind, extractor, catalog, batch_id):
        raw = extractor.extract()
        transformer = cls._transformer(origin, catalog)
        valid, _ = transformer.transformar(raw)
        rejected = [
            {"IdEjecucion": batch_id, "Origen": origin,
             "IdOrigen": item["IdOrigen"], "Motivo": item["Motivo"]}
            for item in transformer.last_rejections.to_dict("records")
        ]
        prepared = []
        for row in valid.to_dict("records"):
            item, reason = cls._prepare_row(origin, kind, row, catalog, batch_id)
            if reason:
                rejected.append({
                    "IdEjecucion": batch_id, "Origen": origin,
                    "IdOrigen": str(row["IdOrigen"]), "Motivo": reason,
                })
            else:
                prepared.append(item)
        return prepared, rejected, {
            "leidos": len(raw), "preparados": len(prepared),
            "rechazados": len(rejected),
        }

    @staticmethod
    def _transformer(origin: str, catalog: AnalyticCatalog) -> DataTransformer:
        references = {
            "IdCliente": catalog.clients,
            "IdProducto": catalog.products,
            "IdFuente": catalog.sources,
        }
        if origin == "encuesta":
            rules = DataSchema.from_rules([
                FieldRule("IdOrigen", "text", max_length=50),
                FieldRule("IdCliente", "integer"), FieldRule("IdProducto", "integer"),
                FieldRule("Fecha", "date"), FieldRule("Comentario", "text"),
                FieldRule("IdFuente", "integer"), FieldRule("IdClasificacion", "integer"),
                FieldRule("Puntaje", "number", minimum=1, maximum=5),
            ])
            return DataTransformer(
                [r.name for r in rules.rules], ["IdOrigen"],
                renombrar={"IdOpinion": "IdOrigen", "Clasificación": "IdClasificacion",
                           "PuntajeSatisfacción": "Puntaje"},
                mapas={"IdClasificacion": {"Positiva": 1, "Negativa": 2, "Neutra": 3}},
                valores_default={"IdFuente": 2, "Canal": "Encuestas", "IdTipoOpinion": 1},
                referencias={**references, "IdClasificacion": catalog.classifications},
                esquema=rules,
            )

        rules = DataSchema.from_rules([
            FieldRule("IdOpinion", "integer"), FieldRule("IdOrigen", "text", max_length=50),
            FieldRule("IdTipoOpinion", "integer"),
            FieldRule("IdCliente", "integer"), FieldRule("IdProducto", "integer"),
            FieldRule("Fecha", "date"), FieldRule("Comentario", "text"),
            FieldRule("IdFuente", "integer"), FieldRule("Canal", "text", max_length=50),
            FieldRule("Puntaje", "number", required=(origin == "resena"),
                      minimum=1, maximum=5),
        ])
        return DataTransformer(
            [r.name for r in rules.rules if r.required], ["IdOrigen"],
            referencias=references, esquema=rules,
        )

    @staticmethod
    def _prepare_row(origin: str, kind: int, row: dict,
                     catalog: AnalyticCatalog, batch_id: str) -> tuple[dict | None, str | None]:
        source_id = str(row["IdOrigen"]).strip()
        opinion_id = catalog.survey_ids.get(source_id) if kind == 1 else row["IdOpinion"]
        if opinion_id is None or pd.isna(opinion_id):
            return None, "sin_id_opinion_relacional"
        try:
            opinion_id = int(opinion_id)
            if opinion_id <= 0:
                return None, "id_opinion_invalido"
        except (TypeError, ValueError, OverflowError):
            return None, "id_opinion_invalido"
        try:
            source_type = kind if kind == 1 else int(row["IdTipoOpinion"])
        except (TypeError, ValueError, OverflowError):
            return None, "tipo_opinion_incorrecto"
        if source_type != kind:
            return None, "tipo_opinion_incorrecto"
        original = row["IdClasificacion"] if kind == 1 else row.get("IdClasificacionOriginal")
        predicted = None if kind == 1 else row.get("IdClasificacionPredicha")
        try:
            original = None if pd.isna(original) else int(original)
            predicted = None if pd.isna(predicted) else int(predicted)
        except (TypeError, ValueError, OverflowError):
            return None, "clasificacion_invalida"
        classification = original if original is not None else predicted
        if classification not in catalog.classifications:
            return None, "sin_clasificacion_valida"
        score = row.get("Puntaje")
        score = None if pd.isna(score) else float(score)
        return {
            "IdEjecucion": batch_id, "IdTipoOpinion": kind,
            "IdOrigen": source_id, "IdOpinion": opinion_id,
            "IdCliente": int(row["IdCliente"]), "IdProducto": int(row["IdProducto"]),
            "Fecha": row["Fecha"], "Comentario": str(row["Comentario"]),
            "IdFuente": int(row["IdFuente"]), "Canal": str(row["Canal"]),
            "Puntaje": score, "IdClasificacionOriginal": original,
            "IdClasificacionPredicha": predicted,
            "IdClasificacion": classification,
        }, None


class SetBasedAnalyticPreparation(AnalyticPreparation):
    """Prepara CSV y API en Python; delega reseñas a INSERT … SELECT en SQL."""

    def __init__(self, survey_extractor, social_extractor,
                 catalog_reader, set_writer):
        self.extractors = (("encuesta", 1, survey_extractor),
                           ("social", 3, social_extractor))
        self.catalog_reader = catalog_reader
        self.staging_writer = set_writer

    def run(self, batch_id: str | None = None, survey_mode: str = "auto") -> dict:
        batch_id = batch_id or str(uuid4())
        catalog = self.catalog_reader.read()
        prepared = {}
        rejected = []
        counts = {}
        for origin, kind, extractor in self.extractors:
            rows, source_rejected, source_counts = self._prepare_source(
                origin, kind, extractor, catalog, batch_id
            )
            prepared[origin] = rows
            rejected.extend(source_rejected)
            counts[origin] = source_counts

        metrics = self.staging_writer.write_set_based(
            batch_id, prepared["encuesta"], prepared["social"],
            rejected, survey_mode=survey_mode,
        )
        counts["resena"] = metrics["resena"]
        return {
            "IdEjecucion": batch_id, "fuentes": counts,
            "preparados": sum(value["preparados"] for value in counts.values()),
            "rechazados": sum(value["rechazados"] for value in counts.values()),
            "carga": {key: value for key, value in metrics.items() if key != "resena"},
        }
