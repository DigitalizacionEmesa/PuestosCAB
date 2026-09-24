/*
  DatosPedidos.TipoDecoracion admite valores decimales de hasta 6 posiciones.
  Los valores enteros existentes se conservan sin cambios.
*/
ALTER TABLE [Digitalizacion].[CAB].[DatosPedidos]
ALTER COLUMN [TipoDecoracion] DECIMAL(18, 6) NULL;
