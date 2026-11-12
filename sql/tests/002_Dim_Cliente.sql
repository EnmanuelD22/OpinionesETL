-- Prueba selectiva de Dim_Cliente con una opinión; se revierte al terminar.
USE [OpinionesDW];
GO
SET XACT_ABORT ON;
DECLARE @LotePrueba uniqueidentifier = NEWID();
DECLARE @Cliente int;

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
    FROM dbo.Stg_Opinion
    ORDER BY IdOpinion;
    IF @@ROWCOUNT <> 1
        THROW 51311, 'No hay una opinion preparada para la prueba.', 1;

    SELECT @Cliente = IdCliente
    FROM dbo.Stg_Opinion WHERE IdEjecucion = @LotePrueba;

    EXEC dbo.usp_CargarDimCliente @IdEjecucion = @LotePrueba;
    IF NOT EXISTS (
        SELECT 1 FROM dbo.Dim_Cliente WHERE IdCliente = @Cliente
    )
        THROW 51312, 'El cliente del lote no quedo cubierto.', 1;
    EXEC dbo.usp_CargarDimCliente @IdEjecucion = @LotePrueba;

    ROLLBACK TRANSACTION;
    SELECT 'OK: un cliente cubierto y segunda ejecucion sin duplicado' AS Resultado;
END TRY
BEGIN CATCH
    IF @@TRANCOUNT > 0 ROLLBACK TRANSACTION;
    THROW;
END CATCH;
GO
