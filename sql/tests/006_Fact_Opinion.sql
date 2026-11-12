-- Prueba de inserción e idempotencia de Fact_Opinion; ROLLBACK al terminar.
USE [OpinionesDW];
GO
SET XACT_ABORT ON;
DECLARE @LotePrueba uniqueidentifier = NEWID();
DECLARE @IdPrueba int = (SELECT MAX(IdOpinion) + 100000 FROM dbo.Fact_Opinion);
CREATE TABLE #Resultado (
    Leidos int, Insertados int, Actualizados int, SinCambios int
);

BEGIN TRY
    BEGIN TRANSACTION;
    IF @IdPrueba IS NULL OR EXISTS (
        SELECT 1 FROM dbo.Fact_Opinion WHERE IdOpinion = @IdPrueba
    )
        THROW 51711, 'No hay una clave de prueba disponible.', 1;

    INSERT INTO dbo.Stg_Opinion (
        IdEjecucion, IdTipoOpinion, IdOrigen, IdOpinion, IdCliente,
        IdProducto, Fecha, Comentario, IdFuente, Canal, Puntaje,
        IdClasificacionOriginal, IdClasificacionPredicha, IdClasificacion
    )
    SELECT TOP (1)
        @LotePrueba, IdTipoOpinion, CONCAT('FACT_TEST_', @IdPrueba),
        @IdPrueba, IdCliente, IdProducto, Fecha, Comentario, IdFuente,
        Canal, Puntaje, IdClasificacionOriginal, IdClasificacionPredicha,
        IdClasificacion
    FROM dbo.Stg_Opinion ORDER BY IdOpinion;
    IF @@ROWCOUNT <> 1
        THROW 51712, 'No hay una opinion preparada para la prueba.', 1;

    INSERT INTO #Resultado
    EXEC dbo.usp_CargarFactOpinion @IdEjecucion = @LotePrueba;
    IF NOT EXISTS (
        SELECT 1 FROM #Resultado
        WHERE Leidos = 1 AND Insertados = 1
          AND Actualizados = 0 AND SinCambios = 0
    )
        THROW 51713, 'La primera ejecución no insertó el hecho esperado.', 1;
    IF NOT EXISTS (
        SELECT 1 FROM dbo.Fact_Opinion WHERE IdOpinion = @IdPrueba
    )
        THROW 51714, 'El hecho de prueba no quedó disponible.', 1;

    DELETE FROM #Resultado;
    INSERT INTO #Resultado
    EXEC dbo.usp_CargarFactOpinion @IdEjecucion = @LotePrueba;
    IF NOT EXISTS (
        SELECT 1 FROM #Resultado
        WHERE Leidos = 1 AND Insertados = 0
          AND Actualizados = 0 AND SinCambios = 1
    )
        THROW 51715, 'La segunda ejecución duplicó o modificó el hecho.', 1;

    ROLLBACK TRANSACTION;
    SELECT 'OK: inserción y repetición de un hecho, todo revertido' AS Resultado;
END TRY
BEGIN CATCH
    IF @@TRANCOUNT > 0 ROLLBACK TRANSACTION;
    THROW;
END CATCH;
GO
