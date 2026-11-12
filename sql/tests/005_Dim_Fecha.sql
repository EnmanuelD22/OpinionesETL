-- Prueba selectiva de Dim_Fecha con una opinión; se revierte al terminar.
USE [OpinionesDW];
GO
SET XACT_ABORT ON;
DECLARE @LotePrueba uniqueidentifier = NEWID();
DECLARE @Fecha date;

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
        THROW 51611, 'No hay una opinion preparada para la prueba.', 1;

    SELECT @Fecha = Fecha FROM dbo.Stg_Opinion
    WHERE IdEjecucion = @LotePrueba;
    EXEC dbo.usp_CargarDimFecha @IdEjecucion = @LotePrueba;
    IF NOT EXISTS (
        SELECT 1 FROM dbo.Dim_Fecha
        WHERE Fecha = @Fecha
          AND IdFecha = CONVERT(int, CONVERT(char(8), @Fecha, 112))
    )
        THROW 51612, 'La fecha del lote no quedo cubierta.', 1;
    EXEC dbo.usp_CargarDimFecha @IdEjecucion = @LotePrueba;

    ROLLBACK TRANSACTION;
    SELECT 'OK: una fecha cubierta y segunda ejecucion sin duplicado' AS Resultado;
END TRY
BEGIN CATCH
    IF @@TRANCOUNT > 0 ROLLBACK TRANSACTION;
    THROW;
END CATCH;
GO
