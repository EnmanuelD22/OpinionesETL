# Módulo 4: validación para promover un modelo NLP

Este módulo añade un control de promoción reproducible. **El candidato no está
aprobado ni activo en el ETL.** El comando `tools.nlp_release_gate` reúne las
comprobaciones de calidad y rendimiento antes de cambiar la selección del
clasificador. Solo lee CSV y reportes; no escribe en `OpinionesETL`,
`OpinionesDW` ni en los CSV originales. El resultado agregado se guarda bajo
`reports/`, una carpeta ignorada por Git.

La validación se puede hacer en dos etapas: `--stage quality` revisa anotaciones
y métricas ahora; la etapa `final` exige además la prueba de 50.000 comentarios
en SQL Server. Aprobar calidad no activa el candidato ni aprueba el despliegue.

## Evidencia exigida

1. Preparar datos representativos de encuestas, reseñas web y comentarios
   sociales en `evaluation/private/real_data/`, con los mismos nombres y
   columnas que las tres fuentes actuales. Eliminar datos personales antes de
   anotarlos. Conservar los CSV del maestro sin cambios.
2. Dos personas etiquetan de forma independiente **los mismos textos únicos**.
   Cada archivo de revisión contiene `sample_id`, `canales`, `comentario`,
   `etiqueta_revisada` y un identificador distinto en `anotador`. Resolver
   desacuerdos en un tercer archivo final. El control verifica IDs, textos,
   cobertura y coincidencias de los revisores, pero la independencia humana
   debe confirmarse fuera del software.
   Las plantillas académicas separadas están en
   `evaluation/private/revision_a.csv` y `evaluation/private/revision_b.csv`;
   contienen 45 textos sin etiquetas. Cada persona completa su archivo sin
   consultar el de la otra ni las predicciones. Esas plantillas sirven para
   practicar el proceso, pero no alcanzan los mínimos de cobertura siguientes.
   Para datos reales, generar una nueva plantilla con `tools.evaluate_nlp` y
   entregar copias nuevas a los dos revisores; no reutilizar las 45 filas.
3. La muestra final debe tener al menos **100 textos únicos por canal** y **20
   por clase en cada canal**. Los textos idénticos se agrupan por `sample_id`.
   Reservar la prueba final antes de ajustar reglas o parámetros.
4. Comparar ambos clasificadores sobre la adjudicación final. La F1 macro y el
   recall negativo del candidato deben ser al menos iguales a la línea base,
   tanto globalmente como por canal. El reporte debe corresponder a las mismas
   fuentes, etiquetas y versión fijada del modelo.
5. Medir el **ETL completo en SQL Server** con al menos 50.000 comentarios y
   verificar que termina en 300 segundos o menos. Registrar el volumen, tiempo,
   versión del clasificador y SHA-256 del conjunto medido. El control revisa la
   estructura del reporte; la ejecución y sus tiempos deben verificarse con
   los registros reales del proceso. Una medición solo del modelo no acredita
   el requisito de rendimiento del sistema.

## Comandos

Una vez disponibles las tres revisiones y las fuentes privadas:

```powershell
python -m tools.compare_nlp_models --data-dir evaluation/private/real_data --reviewed evaluation/private/revision_final.csv --report reports/nlp_comparison_real.json --offline
python -m tools.nlp_release_gate --stage quality --data-dir evaluation/private/real_data --final evaluation/private/revision_final.csv --reviewer-a evaluation/private/real_revision_a.csv --reviewer-b evaluation/private/real_revision_b.csv --comparison reports/nlp_comparison_real.json
```

Al terminar la medición de rendimiento, repetir el control con `--stage final`
y `--performance evaluation/private/sqlserver_performance.json`. El modo `final`
es el predeterminado.

El reporte de rendimiento debe tener este formato, con valores **medidos** y
una huella real del conjunto usado:

```json
{
  "motor": "SQL Server",
  "alcance": "ETL completo",
  "modelo_version": "nlptown-8f6f4e3",
  "dataset_sha256": "<64 caracteres hexadecimales>",
  "comentarios": 50000,
  "segundos": 300
}
```

El control devuelve código de salida distinto de cero si falta evidencia o
algún criterio falla. El reporte `reports/nlp_release_gate.json` solo contiene
conteos, versión, resultado y motivos; no copia comentarios ni datos de
clientes.

## Estado actual

Al ejecutarlo sobre el fixture académico, la etapa de calidad da **NO APROBADA**:
solo hay 45 textos únicos (15 por canal), una revisión, F1 macro inferior del
candidato. La etapa final también carece de una medición de 50.000 comentarios
en SQL Server. Esto impide
promoverlo automáticamente. El léxico sigue activo y `AnalisisOpinion` conserva
las versiones ya registradas. No se requiere una migración SQL para este
control de validación.
