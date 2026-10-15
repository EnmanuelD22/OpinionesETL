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
```

Ejecutar el proceso:

```powershell
python main.py
```

La aplicación crea las tablas que no existan, prepara las categorías y
clasificaciones requeridas y procesa las cargas en orden: fuentes de datos,
clientes, productos y opiniones.

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
- Muestra los registros procesados, insertados y rechazados por pipeline.
- Presenta un resumen final con los principales motivos de rechazo.

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

## Organización

- `application/`: contratos, transformación y coordinación del proceso ETL.
- `domain/`: entidades independientes de la tecnología de persistencia.
- `infrastructure/`: lectura de CSV, conexión, modelos ORM y carga en SQL Server.
- `data/`: archivos CSV utilizados como fuentes de entrada.
- `tests/`: pruebas unitarias e integración local.
- `main.py`: punto de entrada de la aplicación.
