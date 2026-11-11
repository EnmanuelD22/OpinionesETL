# ETL de opiniones de clientes

Aplicación de consola que extrae información desde archivos CSV, valida y
transforma sus registros y los carga en SQL Server respetando las relaciones
del modelo transaccional.

El proceso está organizado como un monolito modular en capas, separando la
lógica de aplicación, el dominio y la infraestructura.

## Objetivo

Poblar automáticamente la base de datos de opiniones de clientes y garantizar
la calidad, consistencia e integridad referencial de la información cargada.

## Stack tecnológico

- **Python 3.10+**: desarrollo de la aplicación ETL.
- **Pandas y NumPy**: lectura, transformación y validación de datos.
- **SQL Server**: base de datos transaccional de destino.
- **SQLAlchemy**: conexión y definición del modelo de persistencia.
- **PyODBC**: conexión entre Python y SQL Server mediante ODBC.
- **python-dotenv**: configuración de la conexión mediante variables de entorno.
- **unittest y SQLite en memoria**: pruebas automatizadas sin modificar la base real.

## Requisitos

- Python 3.10 o posterior.
- SQL Server disponible y accesible.
- Microsoft ODBC Driver 17 o 18 para SQL Server.
- Los archivos CSV ubicados en la carpeta `data/`.

## Preparación y ejecución

Crear y activar el entorno virtual:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Configurar la conexión en un archivo `.env` ubicado en la raíz del proyecto:

```env
DB_SERVER=.\SQLEXPRESS
DB_NAME=OpinionesETL
DB_DRIVER=ODBC Driver 17 for SQL Server
DB_TRUSTED_CONNECTION=yes
DW_NAME=OpinionesDW
# Solo para una instancia de desarrollo con certificado autofirmado:
DB_TRUST_SERVER_CERTIFICATE=yes
```

Ejecutar el proceso:

```powershell
python main.py
```

Antes de ejecutar en SQL Server, crear las bases con los scripts originales
`BaseRelacional.sql` y `DataWareHouse.sql`. Después ejecutar, en ese orden,
[`sql/001_OpinionesETL.sql`](sql/001_OpinionesETL.sql) y
[`sql/002_OpinionesDW.sql`](sql/002_OpinionesDW.sql). Las migraciones son
idempotentes y no borran datos existentes.

La aplicación carga fuentes, clientes, productos y opiniones en `OpinionesETL`.
Luego clasifica opiniones sin etiqueta original y sincroniza dimensiones y hechos
en `OpinionesDW`. Puede repetirse sin duplicar hechos ni predicciones. Las
etiquetas de encuestas se conservan; las predicciones se guardan aparte en
`AnalisisOpinion` con confianza y versión del clasificador.
Al reprocesar los archivos, el cargador actualiza `IdOrigen` de las filas
anteriores que aún tengan valores `CSV_*`, sin volver a insertarlas.

La clasificación incluida es una línea base léxica local en español. Debe
evaluarse con comentarios reales y etiquetas revisadas antes de usarse para
decisiones comerciales. Una confianza de 0 indica que no se encontraron palabras
del léxico. Los datos inconsistentes de muestra son intencionales.

Opcionalmente, las reseñas web pueden extraerse de otra base relacional en la
misma instancia, con una tabla que tenga las columnas del CSV `web_reviews.csv`:

```env
WEB_SOURCE_DB_NAME=BaseResenas
WEB_SOURCE_TABLE=WebReviews
```

Si no se configura, se conserva `data/web_reviews.csv`. La API REST queda para
una fase posterior, según el alcance acordado.

## Archivos CSV

| Archivo | Columnas de origen |
|---|---|
| `clients.csv` | `IdCliente, Nombre, Email` |
| `fuente_datos.csv` | `IdFuente, TipoFuente, FechaCarga` |
| `products.csv` | `IdProducto, Nombre, Categoría` |
| `surveys_part1.csv` | `IdOpinion, IdCliente, IdProducto, Fecha, Comentario, Clasificación, PuntajeSatisfacción, Fuente` |
| `social_comments.csv` | `IdComment, IdCliente, IdProducto, Fuente, Fecha, Comentario` |
| `web_reviews.csv` | `IdReview, IdCliente, IdProducto, Fecha, Comentario, Rating` |

## Validaciones y carga

- Comprueba que existan las columnas obligatorias.
- Rechaza campos vacíos y datos con formatos inválidos.
- Convierte identificadores, fechas y puntuaciones a los tipos de destino.
- Normaliza espacios y direcciones de correo electrónico.
- Detecta duplicados dentro de los archivos y en la base de datos.
- Valida las referencias de clientes, productos, fuentes y clasificaciones.
- Carga los registros respetando las claves primarias y foráneas.
- Muestra los registros procesados, insertados, rechazados y ya existentes por pipeline.
- Presenta un resumen final con los principales motivos de rechazo.

Los totales y motivos se muestran en consola durante la ejecución. Los
registros ya existentes no se cuentan como errores de calidad.

Los errores de lectura, transformación, catálogo o persistencia se manejan
mediante excepciones específicas y detienen la ejecución cuando la operación
no puede continuar de forma segura.

## Pruebas

Ejecutar las pruebas automatizadas con:

```powershell
python -m unittest discover -s tests -v
```

Las pruebas utilizan SQLite en memoria para validar el flujo sin modificar la
base de datos SQL Server.

Incluyen una carga integral de la base relacional al DW, clasificación de texto,
extracción desde una tabla SQL y una segunda ejecución sin duplicados.

## Indicadores y rendimiento

La evaluación previa de NLP se ejecuta con `python -m tools.evaluate_nlp`.
El procedimiento de anotación y las limitaciones de los datos actuales están
en [`docs/nlp_evaluation.md`](docs/nlp_evaluation.md).
El módulo 2 incorpora un modelo candidato en español y lo compara con la línea
base sin alterar el ETL. Instalación, resultados y criterio de adopción están en
[`docs/nlp_model_comparison.md`](docs/nlp_model_comparison.md).
El módulo 3 conecta la interfaz NLP con la carga analítica y conserva el léxico
como clasificador activo; ver [`docs/nlp_etl_integration.md`](docs/nlp_etl_integration.md).
El módulo 4 establece el control de calidad y rendimiento previo a promover un
modelo; ver [`docs/nlp_release_validation.md`](docs/nlp_release_validation.md).

El dashboard local se inicia con `python dashboard.py` y abre en
`http://127.0.0.1:8765`. Lee `OpinionesDW`, permite filtrar por producto y mes,
y muestra cantidad, sentimiento, satisfacción y tendencia mensual.
Satisfacción se define como **opiniones positivas / opiniones clasificadas**;
las neutras cuentan en el denominador. Las vistas SQL usan la misma fórmula.

Para Power BI, conectar a `OpinionesDW`. La tabla de hechos y las seis dimensiones
mantienen el modelo estrella y permiten crear medidas propias. Las vistas ofrecen
un inicio rápido:

| Vista | Uso sugerido |
|---|---|
| `vw_KPIGeneral` | Tarjetas de opiniones analizadas, clases y satisfacción global |
| `vw_KPIProductoMes` | Tendencia mensual y comparación por producto |
| `vw_ClasificacionPorCanal` | Distribución de opiniones por canal y tipo |
| `vw_OpinionesDetalle` | Tabla filtrable por fecha, producto, canal y clasificación |

Los registros procesados y rechazados son métricas de ejecución mostradas en
consola; el DW contiene únicamente opiniones válidas. No se deben sumar los
porcentajes de vistas agregadas: calcular satisfacción con positivas / total
en el contexto de filtros de Power BI.

Para verificar la meta de 50.000 comentarios en menos de 5 minutos, usar una
muestra de al menos ese tamaño en SQL Server y ejecutar `python benchmark.py`.
El script falla si el volumen o el tiempo no cumplen la meta. La muestra actual
de 1.700 registros no permite certificar ese requisito.

## Organización

- `application/`: contratos, transformación y coordinación del proceso ETL.
- `domain/`: entidades independientes de la tecnología de persistencia.
- `infrastructure/`: lectura de CSV, conexión, modelos ORM y carga en SQL Server.
- `data/`: archivos CSV utilizados como fuentes de entrada.
- `tests/`: pruebas unitarias e integración local.
- `main.py`: punto de entrada de la aplicación.
