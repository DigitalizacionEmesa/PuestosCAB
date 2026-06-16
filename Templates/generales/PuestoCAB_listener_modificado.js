// Función modificada para confirmar antes de desmarcar un estado "Hecho"

// Función para verificar si una orden está marcada como hecho en los estados activos
function isOrdenMarcadaComoHecho(codlinea, gfh) {
  const claveItem = `${codlinea}_${gfh}`;
  console.log(`🔍 isOrdenMarcadaComoHecho(${codlinea}, ${gfh}) -> ${claveItem}`);
  console.log(`   📋 ESTADOS_ACTIVOS existe:`, !!ESTADOS_ACTIVOS);
  console.log(`   📋 Total claves en ESTADOS_ACTIVOS:`, Object.keys(ESTADOS_ACTIVOS || {}).length);
  console.log(`   📋 Clave buscada existe:`, !!(ESTADOS_ACTIVOS && ESTADOS_ACTIVOS[claveItem]));
  
  if (ESTADOS_ACTIVOS && ESTADOS_ACTIVOS[claveItem]) {
    console.log(`   📊 Estado encontrado:`, ESTADOS_ACTIVOS[claveItem]);
    const estadoLimpio = ESTADOS_ACTIVOS[claveItem].estado.trim(); // Eliminar espacios en blanco
    const resultado = estadoLimpio === 'Hecho';
    console.log(`   🧹 Estado limpio: "${estadoLimpio}"`);
    console.log(`   ✅ Resultado: ${resultado}`);
    return resultado;
  } else {
    console.log(`   ❌ No se encontró estado para la clave ${claveItem}`);
    return false;
  }
}

// Delegación de eventos para toggles en la tabla (modificada)
$tableBody.addEventListener('change', async (e) => {
  const row = e.target.closest('.orden-row');
  if (!row) return;
  const id = row.getAttribute('data-id');
  const orden = ORDENES.find(x => x.CODLINEA === id);
  if (!orden) return;

  let estadoARegistrar = null;
  let progreso = null;

  if (e.target.classList.contains('t-hecho')) {
    const nuevoEstado = e.target.checked;
    const input = row.querySelector('.progress-input');
    const checkboxProceso = row.querySelector('.t-proceso');
    const flechaUp = row.querySelector('.progress-arrow.up');
    const flechaDown = row.querySelector('.progress-arrow.down');
    
    // Si está marcando como "Hecho", procesar normalmente
    if (nuevoEstado) {
      // Marcar como Hecho: poner 100%, desmarcar proceso, deshabilitar flechas
      input.value = 100;
      input.setAttribute('data-original-value', 100);
      checkboxProceso.checked = false;
      flechaUp.disabled = true;
      flechaDown.disabled = true;
      console.log(`✅ Marcado como "Hecho": progreso establecido a 100%`);
      estadoARegistrar = 'Hecho';
    } else {
      // NUEVO: Confirmación al desmarcar "Hecho"
      if (confirm('¿Está seguro que desea desmarcar esta tarea como "Hecho"?')) {
        // Desmarcar Hecho: habilitar flechas, mantener progreso actual
        flechaUp.disabled = false;
        flechaDown.disabled = false;
        console.log(`🔄 Desmarcado "Hecho": flechas habilitadas`);
        estadoARegistrar = 'NoHecho';
        progreso = -100; // Establecer Realización a -100 como solicitado
      } else {
        // Si cancela, revertir el checkbox
        console.log(`❌ Operación cancelada: se mantiene estado "Hecho"`);
        e.target.checked = true; // Mantener checkbox marcado
        return; // Salir sin registrar cambios
      }
    }
  }
  
  if (e.target.classList.contains('t-faltante')) {
    const nuevoEstado = e.target.checked;
    // Determinar estado a registrar
    estadoARegistrar = nuevoEstado ? 'Faltante' : 'NoFaltante';
  }

  // El "En proceso" ya no se controla con click, ahora es un indicador automático
  // pero mantenemos el código para compatibilidad, aunque no debería ejecutarse nunca
  if (e.target.classList.contains('t-proceso')) {
    console.log('⚠️ Intento de marcar "En proceso" manualmente - Esta funcionalidad ha cambiado');
    // Prevenir la acción ya que el checkbox está deshabilitado y es solo un indicador
    e.preventDefault();
    e.stopPropagation();
    
    // Informar al usuario del cambio
    alert('El estado "En Proceso" ahora es automático y se activa cuando el progreso es mayor que 0%.');
    
    // Restaurar estado original (aunque no debería poder cambiar por estar disabled)
    const input = row.querySelector('.progress-input');
    const valorOriginal = parseFloat(input.getAttribute('data-original-value')) || 0;
    let valorActual = clampStep5(input.value) || 0;
    
    // Determinar si debería estar checked basado en el valor actual
    e.target.checked = valorActual > 0;
    return; // No continuar con el registro de estado
  }

  // Registrar cambio de estado en la base de datos PRIMERO
  if (estadoARegistrar && orden.CODLINEA && orden.GFH) {
    console.log(`Registrando estado: ${estadoARegistrar} para CODLINEA: ${orden.CODLINEA}, GFH: ${orden.GFH}, progreso: ${progreso}`);
    
    const registroExitoso = await registrarEstado(orden.CODLINEA, orden.GFH, estadoARegistrar, progreso);
    
    if (registroExitoso) {
      console.log(`✅ Estado registrado exitosamente, actualizando fila específica...`);
      // Usar actualización selectiva para TODOS los estados para evitar parpadeo
      await actualizarFilaEspecifica(orden.CODLINEA, orden.GFH);
    } else {
      console.error(`❌ Error registrando estado, revirtiendo checkbox...`);
      // Revertir el checkbox si hubo error
      e.target.checked = !e.target.checked;
    }
  } else {
    console.warn(`No se pudo registrar estado:`, {
      estadoARegistrar,
      CODLINEA: orden.CODLINEA,
      GFH: orden.GFH,
      orden: orden
    });
    // Revertir el checkbox si no se puede registrar
    e.target.checked = !e.target.checked;
  }
});