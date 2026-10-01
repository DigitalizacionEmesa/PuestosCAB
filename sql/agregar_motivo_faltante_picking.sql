/*
    Motivo opcional para cada episodio de faltante de Picking.
    Ejecutar antes de reiniciar la API con el código actualizado.
    Se puede volver a ejecutar sin modificar los registros existentes.
*/
USE [Digitalizacion];
GO

IF OBJECT_ID(N'[CAB].[faltantes_picking]', N'U') IS NULL
BEGIN
    THROW 50000, N'No existe CAB.faltantes_picking. Ejecuta primero sql/faltantes_picking.sql.', 1;
END;
GO

IF COL_LENGTH(N'CAB.faltantes_picking', N'MOTIVO_FALTANTE') IS NULL
BEGIN
    ALTER TABLE [CAB].[faltantes_picking]
        ADD [MOTIVO_FALTANTE] NVARCHAR(500) NULL;
END;
GO
