-- Prueba de cobertura e idempotencia con una opinión, sin conservar cambios.
USE [OpinionesDW];
GO
SET XACT_ABORT ON;
DECLARE @LotePrueba uniqueidentifier = NEWID();
DECLARE @Fuente int;

BEGIN TRY
    BEGIN TRANSACTION;
    INSERT INTO dbo.Stg_Opinion (
        IdEjecucion, IdTipoOpinion, IdOrigen, IdOpinion, IdCliente,
        IdProducto, Fecha, Comentario, IdFuente, Canal, Puntaje,
        IdClasificacionOriginal, IdClasificacionPredicha, IdClasificacion
    )
    SELECT TOP (1)
        @LotePrueba, IdTipoOpinion, IdOrigen, IdOpinion, IdCliente,
        IdProducto, Fecha, Comentario, IdFuente, Canal, Puntaje,
        IdClasificacionOriginal, IdClasificacionPredicha, IdClasificacion
    FROM dbo.Stg_Opinion ORDER BY IdOpinion;
    IF @@ROWCOUNT <> 1
        THROW 51511, 'No hay una opinion preparada para la prueba.', 1;

    SELECT @Fuente = IdFuente FROM dbo.Stg_Opinion
    WHERE IdEjecucion = @LotePrueba;
    EXEC dbo.usp_CargarDimFuente @IdEjecucion = @LotePrueba;
    IF NOT EXISTS (SELECT 1 FROM dbo.Dim_Fuente WHERE IdFuente = @Fuente)
        THROW 51512, 'La fuente del lote no quedo cubierta.', 1;
    EXEC dbo.usp_CargarDimFuente @IdEjecucion = @LotePrueba;

    ROLLBACK TRANSACTION;
    SELECT 'OK: una fuente cubierta y segunda ejecucion sin duplicado' AS Resultado;
END TRY
BEGIN CATCH
    IF @@TRANCOUNT > 0 ROLLBACK TRANSACTION;
    THROW;
END CATCH;
GO

-- Un canal distinto para una fuente existente debe rechazarse.
DECLARE @LoteConflicto uniqueidentifier = NEWID();
BEGIN TRY
    BEGIN TRANSACTION;
    INSERT INTO dbo.Stg_Opinion (
        IdEjecucion, IdTipoOpinion, IdOrigen, IdOpinion, IdCliente,
        IdProducto, Fecha, Comentario, IdFuente, Canal, Puntaje,
        IdClasificacionOriginal, IdClasificacionPredicha, IdClasificacion
    )
    SELECT TOP (1)
        @LoteConflicto, IdTipoOpinion, IdOrigen, IdOpinion, IdCliente,
        IdProducto, Fecha, Comentario, IdFuente, 'Canal de prueba', Puntaje,
        IdClasificacionOriginal, IdClasificacionPredicha, IdClasificacion
    FROM dbo.Stg_Opinion ORDER BY IdOpinion;
    IF @@ROWCOUNT <> 1
        THROW 51513, 'No hay una opinion preparada para la prueba.', 1;
    EXEC dbo.usp_CargarDimFuente @IdEjecucion = @LoteConflicto;
    IF @@TRANCOUNT > 0 ROLLBACK TRANSACTION;
    THROW 51514, 'No se rechazo el canal contradictorio.', 1;
END TRY
BEGIN CATCH
    DECLARE @Error int = ERROR_NUMBER();
    IF @@TRANCOUNT > 0 ROLLBACK TRANSACTION;
    IF @Error <> 51504 THROW;
    SELECT 'OK: canal contradictorio rechazado con error 51504' AS Resultado;
END CATCH;
GO
