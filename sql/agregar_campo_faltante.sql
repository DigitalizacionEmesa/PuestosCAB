-- Script para agregar el campo Faltante a la tabla DatosUserCAB
-- Ejecutar este script en SQL Server Management Studio

USE [Digitalizacion];
GO

-- Verificar si el campo Faltante ya existe
IF NOT EXISTS (
    SELECT * 
    FROM INFORMATION_SCHEMA.COLUMNS 
    WHERE TABLE_SCHEMA = 'CAB' 
    AND TABLE_NAME = 'DatosUserCAB' 
    AND COLUMN_NAME = 'Faltante'
)
BEGIN
    -- Agregar el campo Faltante como NVARCHAR(500) permitiendo NULL
    ALTER TABLE [CAB].[DatosUserCAB] 
    ADD Faltante NVARCHAR(500) NULL;
    
    PRINT 'Campo Faltante agregado exitosamente a la tabla DatosUserCAB';
END
ELSE
BEGIN
    PRINT 'El campo Faltante ya existe en la tabla DatosUserCAB';
END
GO

-- Verificar la estructura actualizada de la tabla
SELECT 
    COLUMN_NAME,
    DATA_TYPE,
    CHARACTER_MAXIMUM_LENGTH,
    IS_NULLABLE
FROM INFORMATION_SCHEMA.COLUMNS 
WHERE TABLE_SCHEMA = 'CAB' 
AND TABLE_NAME = 'DatosUserCAB'
ORDER BY ORDINAL_POSITION;