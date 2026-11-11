# Módulo 2: modelo candidato y comparación

El módulo 2 añade un clasificador de sentimiento en español para **evaluación
local**, conserva la línea base del ETL y compara ambos con las mismas etiquetas
revisadas. No carga datos en `OpinionesETL` ni `OpinionesDW`, no cambia las vistas
del dashboard y no modifica ninguno de los CSV entregados por el maestro.

## Implementación

El contrato `ISentimentClassifier.predict_batch` mantiene el orden de entrada y
devuelve una clase por comentario: `1` positiva, `2` negativa y `3` neutra. Hay
dos adaptadores:

- `LexiconClassifier`: usa el clasificador léxico vigente, `lexico-es-v1`.
- `ProductReviewClassifier`: usa
  [`nlptown/bert-base-multilingual-uncased-sentiment`](https://huggingface.co/nlptown/bert-base-multilingual-uncased-sentiment),
  fijado a la revisión `8f6f4e3a8f70be4b65d3a4a8762b6d781cda240d` y
  registrado como `nlptown-8f6f4e3`. Su ficha declara licencia MIT y describe
  entrenamiento con reseñas de productos en español y otros cinco idiomas. El
  modelo predice de 1 a 5 estrellas; se suman las probabilidades de 1–2 para
  `Negativa`, se toma 3 para `Neutra` y se suman 4–5 para `Positiva`. Esta
  correspondencia es una **decisión del proyecto**, no una etiqueta nativa del
  modelo, y se contrasta con anotaciones humanas de cada canal.

Se descartó el candidato inicial RoBERTuito para esta implementación: sus
autores requieren un [preprocesamiento específico](https://github.com/pysentimiento/robertuito)
y el [paquete oficial declara uso no comercial](https://github.com/pysentimiento/pysentimiento/blob/master/LICENSE.md).
El sistema se plantea para una empresa de comercio electrónico.

Las dependencias pesadas están en `requirements-nlp.txt`, separadas de las del
ETL. El modelo se descarga una vez en `.cache/huggingface/` y luego ejecuta la
inferencia localmente. Se carga con `trust_remote_code=False`, pesos
`safetensors`, modo de evaluación y `torch.inference_mode()`; se procesan lotes
de 16 por defecto y se trunca a 128 tokens. El reporte no contiene comentarios
ni identificadores de clientes. Los pesos descargados y los datos privados no
se versionan.

La `confianza` del léxico es una medida heurística de evidencia; la del modelo
es la suma de probabilidades softmax de las estrellas de la clase elegida. No
son escalas calibradas ni directamente comparables.

## Reproducir la comparación

Desde la raíz del repositorio, después de crear el entorno virtual e instalar
`requirements.txt`:

```powershell
pip install -r requirements-nlp.txt
python -m tools.compare_nlp_models
```

La primera ejecución requiere acceso a Hugging Face para descargar los pesos.
Después puede repetirse sin red:

```powershell
python -m tools.compare_nlp_models --offline
```

La salida agregada se guarda en `reports/nlp_model_comparison.json`. Contiene la
revisión del modelo, el tamaño de lote, huellas SHA-256 de las fuentes y de las
etiquetas, métricas globales y por canal, y tiempos de una ejecución. El
comparador valida que cada comentario revisado esté en las fuentes, que no haya
IDs duplicados, que todas las etiquetas sean válidas y que cada clasificador
devuelva exactamente una clase conocida por entrada. Rechaza rutas de reporte
dentro de `data/` o que sobrescriban el archivo de etiquetas.

Para datos representativos posteriores, usar `--data-dir`, `--reviewed` y
`--report` con rutas privadas fuera de `data/`; preparar las etiquetas según
[`nlp_evaluation.md`](nlp_evaluation.md). Las etiquetas del fixture académico
son una revisión única, no una validación independiente.

## Resultado del fixture académico

La comparación usa **45 textos únicos**, 15 por canal y 15 por clase en total.
Es un conjunto pequeño y repetitivo construido para comprobar funcionalidad;
los datos inconsistentes fueron colocados intencionalmente. No representa la
distribución de comentarios nuevos.

| Modelo | Aciertos | Accuracy | F1 macro | Recall negativo | Recall neutro |
|---|---:|---:|---:|---:|---:|
| Léxico actual | 42/45 | 0,9333 | 0,9344 | 0,8667 | 1,0000 |
| Modelo de reseñas | 37/45 | 0,8222 | 0,8024 | 1,0000 | 0,4667 |

| Canal | Textos | Accuracy léxico | Accuracy modelo de reseñas |
|---|---:|---:|---:|
| Encuesta | 15 | 1,0000 | 0,8667 |
| Social | 15 | 0,8667 | 0,8000 |
| Web | 15 | 0,9333 | 0,8000 |

El candidato detecta todas las opiniones negativas de este fixture, pero
confunde varias neutras con positivas o negativas. Su F1 macro global es menor.
Por ello **se conserva el léxico como clasificador activo** y el modelo de
reseñas queda como candidato reproducible. No se ajustaron reglas, umbrales ni
pesos después de ver estas etiquetas. Los tiempos observados de carga e
inferencia figuran en el JSON;
una sola corrida de 45 textos no certifica la meta de 50.000 comentarios en
menos de cinco minutos.

## Criterio de adopción posterior

Antes de conectar un modelo nuevo al flujo ETL y al DW, se necesita una muestra
de comentarios reales de cada canal y período, sin datos personales, con
etiquetas adjudicadas por al menos dos revisores. Los textos idénticos deben
permanecer en el mismo grupo al separar desarrollo y prueba. La selección debe
comparar F1 macro y recall negativo globales y por canal con la línea base,
revisar errores y medir el tiempo del pipeline completo sobre al menos 50.000
comentarios en SQL Server. La muestra de prueba final se reserva para una sola
evaluación. El [módulo 3](nlp_etl_integration.md) ya integra la interfaz y el
versionado de predicciones y mantiene el léxico como clasificador activo.
