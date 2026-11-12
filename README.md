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

Si no se configura, el proceso histórico conserva `data/web_reviews.csv`.

## API de comentarios sociales

La API de solo lectura consulta las opiniones sociales ya guardadas en
`OpinionesETL` (`IdTipoOpinion = 3`). No carga filas en la base relacional.
Iniciarla en otra terminal con:

```powershell
python -m uvicorn api:app --host 127.0.0.1 --port 8000
```

Consultar `GET /api/v1/comentarios-sociales?after_id=0&limit=100` para obtener
páginas ordenadas por `IdOpinion`. El límite permitido es de 1 a 500. La
respuesta incluye `items`, `has_more` y `next_after_id`; un cursor nulo indica
la última página. Para consumir todas las páginas con el extractor del proyecto:

```powershell
python -m tools.consume_social_api --url http://127.0.0.1:8000 --page-size 100
```

El consumidor informa cantidad e identificadores, sin imprimir comentarios.

## Preparación analítica selectiva y carga por conjuntos (pasos 3 y 4)

Crear las tablas de staging vacías en `OpinionesDW` ejecutando
[`sql/004_Staging.sql`](sql/004_Staging.sql). Después, ejecutar en orden
[`sql/005_TVP_Social.sql`](sql/005_TVP_Social.sql),
[`sql/006_Bulk_Encuestas.sql`](sql/006_Bulk_Encuestas.sql) y
[`sql/007_Reviews_Set.sql`](sql/007_Reviews_Set.sql). En instalaciones donde
`Stg_Rechazo` ya tenía `IdOrigen varchar(50)`, aplicar después
[`sql/008_Rechazo_IdOrigen.sql`](sql/008_Rechazo_IdOrigen.sql). Los scripts son
idempotentes y no modifican las dimensiones ni `Fact_Opinion`.

Con la API local iniciada, validar las fuentes sin escribir:

```powershell
python -m tools.prepare_analytic_staging --dry-run
```

El modo de validación estima las reseñas con el extractor Python; los conteos
definitivos los devuelve el procedimiento SQL de la ejecución real.

Para escribir las filas preparadas y los rechazos en staging:

```powershell
python -m tools.prepare_analytic_staging
```

La salida devuelve un `IdEjecucion` y recuentos por origen. Un reintento con
`--batch-id <IdEjecucion>` reemplaza solo las filas de ese lote y conserva los
recuentos. `SOCIAL_API_URL` permite cambiar la URL local de la API.

La escritura usa `INSERT … SELECT` para reseñas tipo 2 directamente desde
`OpinionesETL`, TVP en lotes de 100 para comentarios de la API y un CSV temporal
con solo las encuestas validadas para `BULK INSERT`. En modo automático, se
intenta BULK primero; solo si SQL Server informa que no puede abrir o leer el
archivo, las encuestas se insertan por lotes con
`pyodbc.fast_executemany`. Se puede indicar
`--survey-mode bulk --bulk-dir <directorio>` cuando el servidor tiene acceso, o
`--survey-mode batch` para forzar la alternativa. El CSV temporal se elimina al
terminar normalmente; si el proceso se interrumpe abruptamente, revisar
`tmp/bulk/` y eliminar los CSV remanentes. `tmp/` está excluido de Git.
Ver [TVP en SQL Server](https://learn.microsoft.com/en-us/sql/relational-databases/tables/use-table-valued-parameters-database-engine),
[BULK INSERT](https://learn.microsoft.com/en-us/sql/t-sql/statements/bulk-insert-transact-sql)
y [fast_executemany en SQLAlchemy](https://docs.sqlalchemy.org/en/20/dialects/mssql.html#fast-executemany-mode).

El flujo toma encuestas de `data/surveys_part1.csv`, reseñas de la base
relacional con `IdTipoOpinion=2` y comentarios sociales de la API con
`IdTipoOpinion=3`. Los catálogos y el `IdOpinion` de las encuestas se resuelven
en la base relacional. Las 494 encuestas de la muestra sin cliente o producto
existente quedan en `Stg_Rechazo`; no se cargan en la FACT. Los procedimientos
de dimensiones y FACT se describen a continuación.
`python main.py` conserva el proceso histórico y no se usa para esta preparación.

## Procedimientos y usuarios SQL (paso 5)

Tras preparar un lote, instalar en `OpinionesDW` los scripts
`sql/009_Dim_Clasificacion.sql` a `sql/015_Fact_Opinion.sql` en orden.
Cada procedimiento recibe el `IdEjecucion` devuelto por la preparación.
Ejecutar las seis dimensiones antes de `dbo.usp_CargarFactOpinion`:

```sql
EXEC dbo.usp_CargarDimClasificacion @IdEjecucion = 'ID-DEL-LOTE';
EXEC dbo.usp_CargarDimTipoOpinion @IdEjecucion = 'ID-DEL-LOTE';
EXEC dbo.usp_CargarDimCliente @IdEjecucion = 'ID-DEL-LOTE';
EXEC dbo.usp_CargarDimProducto @IdEjecucion = 'ID-DEL-LOTE';
EXEC dbo.usp_CargarDimFuente @IdEjecucion = 'ID-DEL-LOTE';
EXEC dbo.usp_CargarDimFecha @IdEjecucion = 'ID-DEL-LOTE';
EXEC dbo.usp_CargarFactOpinion @IdEjecucion = 'ID-DEL-LOTE';
```

Cada dimensión compara sus claves del lote con el catálogo relacional (fecha
se deriva de la fecha de la opinión), inserta las faltantes y actualiza cambios.
Comprobar sus columnas `ClavesLote`, `Insertadas` y `Actualizadas`; al repetir
el mismo lote, las dos últimas deben ser cero. La FACT verifica sus seis
claves y devuelve `Leidos`, `Insertados`, `Actualizados` y `SinCambios`.
`sql/tests/006_Fact_Opinion.sql` prueba inserción y repetición con `ROLLBACK`.
La opción `--load` del comando analítico realiza esta secuencia desde Python.

Para crear las cuentas SQL de carga y consulta, con un administrador de la
instancia de desarrollo, ejecutar:

```powershell
.venv\Scripts\python.exe -m tools.create_sql_users
```

`opiniones_etl_writer` tiene permisos acotados para leer catálogos de origen y
preparar/cargar el DW. `opiniones_dw_reader` solo consulta las seis dimensiones,
la FACT y las cuatro vistas analíticas; no tiene acceso al staging ni a la base
relacional. Las contraseñas generadas se guardan fuera del repositorio en
`%LOCALAPPDATA%\OpinionesETL\sql_users.env` y no se imprimen. El instalador
verifica los permisos efectivos de ambas cuentas.

## Ejecución integrada (paso 6)

Con la API social local activa, el comando selectivo prepara el lote en staging
y llama las seis dimensiones y luego la FACT:

```powershell
.venv\Scripts\python.exe -m tools.prepare_analytic_staging --load
```

Para cargar un lote ya preparado, sin volver a extraer las fuentes:

```powershell
.venv\Scripts\python.exe -m tools.prepare_analytic_staging --load-existing-batch ID-DEL-LOTE
```

`--dry-run` solo valida la preparación y no se combina con las opciones de
carga. Los recuentos y las pruebas observadas en la instancia local se registran
en [`docs/evidencia_entrega_etl.md`](docs/evidencia_entrega_etl.md).

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

Para medir 50.000 comentarios sintéticos sin alterar la base relacional,
ejecutar `.venv\Scripts\python.exe -m tools.benchmark_50k_api` para paginación
HTTP simulada y `.venv\Scripts\python.exe -m tools.benchmark_50k_social` para
TVP, dimensiones y FACT en SQL Server con `ROLLBACK`. Estos resultados miden
dos tramos separados; la meta integral de API real a DW con 50.000 comentarios
requiere una muestra de ese tamaño en la fuente relacional. `benchmark.py`
corresponde al proceso histórico y no mide la carga selectiva de esta entrega.

## Organización

- `application/`: contratos, transformación y coordinación del proceso ETL.
- `domain/`: entidades independientes de la tecnología de persistencia.
- `infrastructure/`: lectura de CSV, conexión, modelos ORM y carga en SQL Server.
- `data/`: archivos CSV utilizados como fuentes de entrada.
- `tests/`: pruebas unitarias e integración local.
- `main.py`: punto de entrada de la aplicación.
