// Archivo: assets/navegacion.js

/**
 * Función para navegar hacia atrás en el historial del navegador.
 * Si no hay historial, redirige a una URL de "casa" específica para la sección.
 * @param {string} homeUrl - La URL a la que redirigir si no hay historial previo.
 */
function goBackOrHome(homeUrl) {
  // Ponemos una URL global por defecto como red de seguridad
  const fallbackHome = homeUrl || '/Pantallas/Pantallas_Generales/Pantalla_INICIO.html';

  if (history.length > 1) {
    history.back();
  } else {
    window.location.href = fallbackHome;
  }
}