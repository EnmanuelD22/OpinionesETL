# Módulo 1: datos y evaluación de sentimiento

Este módulo **no entrena ni reemplaza** el clasificador. Mide la línea base
`lexico-es-v1`, perfila los comentarios y prepara una muestra para revisión
humana. Los CSV proporcionados por el maestro son **fuentes de solo lectura**:
no se editan, se renombran ni se sobrescriben. La herramienta rechaza cualquier
ruta de salida dentro del directorio de fuentes. Tampoco modifica
`OpinionesETL` ni `OpinionesDW`.

## Ejecutar con los CSV de muestra

Desde la raíz del repositorio:

```powershell
python -m tools.evaluate_nlp
```

La salida agregada queda en `reports/nlp_baseline.json`. La plantilla de textos
únicos queda en `evaluation/private/annotation_queue.csv`, una ruta ignorada
por Git. La herramienta **no sobrescribe** esa plantilla al repetir el comando;
`--overwrite-queue` solo debe usarse cuando se quiere regenerarla deliberadamente.
El reporte fija semilla, tamaño solicitado y huellas SHA-256 de los CSV para
poder repetir la evaluación sobre exactamente las mismas fuentes.

El reporte actual compara 500 filas etiquetadas de encuesta, pero solo 15
textos distintos. Sus métricas son un diagnóstico del conjunto de prueba y no
una estimación del desempeño con opiniones nuevas. Las reseñas web y los
comentarios sociales no tienen etiquetas humanas de referencia. El puntaje
`Rating` tampoco se toma como etiqueta verdadera del texto.

## Preparar datos reales

1. Reunir comentarios representativos de cada canal y período en archivos
   **separados** de los CSV del maestro. Mantenerlos fuera de Git, por ejemplo
   en `evaluation/private/real_data/`, con los mismos nombres de CSV y columnas
   para que la herramienta pueda leerlos. Los originales de `data/` permanecen
   intactos.
2. Eliminar o sustituir datos personales del texto **antes** de crear la
   plantilla. La herramienta solo extrae `Comentario`, canal e ID de muestra;
   no detecta ni elimina automáticamente nombres, teléfonos o correos dentro
   del comentario. No enviar estos archivos a un servicio externo.
3. Ejecutar `python -m tools.evaluate_nlp --data-dir evaluation/private/real_data`
   y revisar la distribución de textos únicos por canal.
4. Etiquetar de forma independiente la misma muestra con dos revisores. Crear
   una copia del CSV para cada persona; resolver desacuerdos en un archivo
   `revision_final.csv`. No cambiar `sample_id` ni `comentario` después de
   generar la muestra.

## Guía de etiquetado

| Etiqueta | Regla |
|---|---|
| `Positiva` | Valoración favorable explícita del producto o servicio. |
| `Negativa` | Queja, falla o valoración desfavorable explícita. |
| `Neutra` | Descripción factual, opinión equilibrada o sin polaridad dominante. |

La etiqueta debe derivarse del **comentario**, no de `Rating`, `Puntaje`, la
clasificación original ni de la predicción del modelo. Si el texto está
incompleto, contiene información sensible pendiente de limpiar o no se puede
resolver una ambigüedad, dejar `etiqueta_revisada` vacía hasta adjudicarla.
Registrar el identificador del revisor en `anotador`, sin incluir nombres
personales si el archivo se compartirá.

## Evaluar una revisión final

```powershell
python -m tools.evaluate_nlp --reviewed evaluation/private/revision_final.csv
```

El reporte añade precisión, recall y F1 por clase, globales y por canal. Las
filas sin `etiqueta_revisada` se cuentan como pendientes y no entran en las
métricas. IDs duplicados, etiquetas desconocidas y comentarios modificados
producen un error en lugar de contaminar la evaluación.

Para comparar modelos en el módulo 2, reservar un conjunto de prueba **antes**
de ajustar reglas o parámetros. Agrupar por `sample_id` al dividir los datos:
el mismo texto normalizado no debe aparecer a la vez en entrenamiento y prueba.
Conservar también la procedencia por canal y medir por separado el recall de
opiniones negativas. No elegir el modelo usando repetidamente el conjunto de
prueba final.

## Criterio de cierre

El conjunto académico quedó revisado en `evaluation/revision_fixture.csv`, un
archivo **nuevo y separado** de los CSV del maestro. La revisión fue realizada
por Codex en una sola pasada; no hubo un segundo anotador independiente. Las
45 etiquetas están completas: 15 por canal. Ejecutar:

```powershell
python -m tools.evaluate_nlp --reviewed evaluation/revision_fixture.csv
```

La línea base acertó 42 de 45 textos distintos: accuracy 0,9333 y F1 macro
0,9344. Por canal: encuesta 1,0000; social 0,8667; web 0,9333 en accuracy.
Los tres desacuerdos son:

| Canal | Texto | Revisión | Predicción léxica |
|---|---|---|---|
| Social | `Calidad superior, muy contento` | Positiva | Neutra |
| Social | `No cumple con lo anunciado, insatisfecho` | Negativa | Neutra |
| Web | `No cumple con lo anunciado, insatisfecho. No volvería a comprar.` | Negativa | Neutra |

Estos errores quedan como casos de comparación para el módulo 2; no se ajustó
la línea base después de observarlos. Este resultado completa el módulo 1 para
los datos académicos, pero **no valida el desempeño en producción**: los textos
son pocos, repetidos en las fuentes y la revisión no fue independiente. Para
una evaluación representativa se necesitan comentarios reales adicionales y
revisión humana independiente, sin alterar los CSV originales.
