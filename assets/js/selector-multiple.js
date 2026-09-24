const INSTANCIAS = new WeakMap();

function normalizar(valor) {
  if (valor === null || valor === undefined) return '';
  return String(valor).trim();
}

function normalizarBusqueda(valor) {
  const texto = normalizar(valor).toLowerCase();
  if (!texto) return '';
  try {
    return texto.normalize('NFD').replace(/\p{Diacritic}/gu, '');
  } catch {
    return texto;
  }
}

function cerrarTodasExcepto(actual) {
  document.querySelectorAll('.selector-multiple.selector-abierto').forEach((item) => {
    if (item !== actual) {
      const api = INSTANCIAS.get(item);
      if (api) api.cerrar();
    }
  });
}

export function initSelectorMultiple(selector, opciones = {}) {
  if (!(selector instanceof HTMLElement)) {
    throw new Error('selector debe ser un HTMLElement');
  }
  if (INSTANCIAS.has(selector)) {
    return INSTANCIAS.get(selector).apiPublica;
  }

  const boton = selector.querySelector('.selector-boton');
  const panel = selector.querySelector('.selector-panel');
  const lista = selector.querySelector('.selector-opciones');
  const resumen = selector.querySelector('.selector-resumen');
  const botonLimpiar = selector.querySelector('.selector-limpiar');
  const botonCerrar = selector.querySelector('.selector-cerrar');
  const botonLimpiarInline = selector.querySelector('.selector-clear-icon');

  if (!boton || !panel || !lista || !resumen) {
    throw new Error('Estructura HTML incompleta para selector-multiple');
  }

  const estado = {
    opciones: [],
    seleccionados: new Set(),
    placeholder: normalizar(opciones.placeholder || resumen.textContent || 'Todos') || 'Todos',
    onChange: typeof opciones.onChange === 'function' ? opciones.onChange : null,
    textoSeleccionados: normalizar(opciones.textoSeleccionados || 'seleccionados') || 'seleccionados',
    textoSinDatos: normalizar(opciones.textoSinDatos || 'Sin datos') || 'Sin datos',
    buscador: null,
    checkboxTodos: null,
    todosLabel: null,
    destruido: false,
  };

  resumen.textContent = estado.placeholder;

  function obtenerOpcionesVisibles() {
    return Array.from(lista.querySelectorAll('.selector-opcion'))
      .filter((item) => item.style.display !== 'none')
      .map((item) => ({
        item,
        checkbox: item.querySelector('input[type="checkbox"]'),
      }))
      .filter((entry) => entry.checkbox instanceof HTMLInputElement && !entry.checkbox.disabled);
  }

  function actualizarCheckboxTodos() {
    if (!(estado.checkboxTodos instanceof HTMLInputElement)) return;
    const visibles = obtenerOpcionesVisibles();
    if (visibles.length === 0) {
      estado.checkboxTodos.checked = false;
      estado.checkboxTodos.indeterminate = false;
      estado.checkboxTodos.disabled = true;
    } else {
      const seleccionadas = visibles.reduce((acc, entry) => (entry.checkbox.checked ? acc + 1 : acc), 0);
      estado.checkboxTodos.disabled = false;
      if (seleccionadas === 0) {
        estado.checkboxTodos.checked = false;
        estado.checkboxTodos.indeterminate = false;
      } else if (seleccionadas === visibles.length) {
        estado.checkboxTodos.checked = true;
        estado.checkboxTodos.indeterminate = false;
      } else {
        estado.checkboxTodos.checked = false;
        estado.checkboxTodos.indeterminate = true;
      }
    }
    estado.checkboxTodos.setAttribute(
      'aria-checked',
      estado.checkboxTodos.indeterminate ? 'mixed' : (estado.checkboxTodos.checked ? 'true' : 'false'),
    );
    if (estado.todosLabel) {
      estado.todosLabel.classList.toggle('is-disabled', estado.checkboxTodos.disabled);
      estado.todosLabel.classList.toggle('is-indeterminate', !estado.checkboxTodos.disabled && estado.checkboxTodos.indeterminate);
      estado.todosLabel.classList.toggle('is-checked', !estado.checkboxTodos.disabled && estado.checkboxTodos.checked && !estado.checkboxTodos.indeterminate);
    }
  }

  function actualizarResumen() {
    const total = estado.opciones.filter((o) => !o.disabled).length;
    const seleccionados = Array.from(estado.seleccionados);
    if (total === 0) {
      resumen.textContent = estado.textoSinDatos;
      selector.classList.remove('selector-activo');
      actualizarCheckboxTodos();
      return;
    }
    if (seleccionados.length === 0) {
      resumen.textContent = estado.placeholder;
      selector.classList.remove('selector-activo');
      actualizarCheckboxTodos();
      return;
    }
    if (seleccionados.length === 1) {
      const valor = seleccionados[0];
      const opcion = estado.opciones.find((item) => item.value === valor);
      resumen.textContent = opcion?.label || '1';
      selector.classList.add('selector-activo');
      actualizarCheckboxTodos();
      return;
    }
    resumen.textContent = `${seleccionados.length} ${estado.textoSeleccionados}`;
    selector.classList.add('selector-activo');
    actualizarCheckboxTodos();
  }

  function emitirCambio() {
    const valores = Array.from(estado.seleccionados);
    if (estado.onChange) {
      estado.onChange(valores, { selector });
    }
    selector.dispatchEvent(new CustomEvent('selector-multiple:change', {
      bubbles: true,
      detail: {
        values: valores,
        selector,
      },
    }));
  }

  function aplicarBusqueda() {
    const termino = normalizarBusqueda(estado.buscador?.value || '');
    lista.querySelectorAll('.selector-opcion').forEach((item) => {
      const texto = item.dataset.labelNorm || normalizarBusqueda(item.textContent || '');
      item.style.display = !termino || texto.includes(termino) ? '' : 'none';
    });
    actualizarCheckboxTodos();
  }

  function cerrar() {
    selector.classList.remove('selector-abierto');
    panel.hidden = true;
    boton.setAttribute('aria-expanded', 'false');
  }

  function abrir() {
    cerrarTodasExcepto(selector);
    selector.classList.add('selector-abierto');
    panel.hidden = false;
    boton.setAttribute('aria-expanded', 'true');
    if (estado.buscador) {
      try {
        estado.buscador.focus({ preventScroll: true });
      } catch {
        estado.buscador.focus();
      }
    }
  }

  function alternar() {
    if (selector.classList.contains('selector-abierto')) {
      cerrar();
    } else {
      abrir();
    }
  }

  function asegurarBuscadorYTodos() {
    let contBusqueda = panel.querySelector('.selector-busqueda');
    if (!contBusqueda) {
      contBusqueda = document.createElement('div');
      contBusqueda.className = 'selector-busqueda';
      panel.insertBefore(contBusqueda, lista);
    }

    let buscador = contBusqueda.querySelector('.selector-buscar');
    if (!buscador) {
      buscador = document.createElement('input');
      buscador.type = 'text';
      buscador.className = 'selector-buscar';
      buscador.placeholder = normalizar(opciones.placeholderBuscar || 'Buscar...') || 'Buscar...';
      buscador.setAttribute('aria-label', normalizar(opciones.ariaBuscar || 'Buscar en el selector') || 'Buscar en el selector');
      contBusqueda.appendChild(buscador);
    }
    estado.buscador = buscador;

    let labelTodos = contBusqueda.querySelector('.selector-todos');
    if (!labelTodos) {
      labelTodos = document.createElement('label');
      labelTodos.className = 'selector-todos';
      const chk = document.createElement('input');
      chk.type = 'checkbox';
      chk.className = 'selector-todos-checkbox';
      const span = document.createElement('span');
      span.className = 'selector-todos-texto';
      span.textContent = normalizar(opciones.textoTodos || 'Todos') || 'Todos';
      labelTodos.append(chk, span);
      contBusqueda.prepend(labelTodos);
    }

    estado.todosLabel = labelTodos;
    estado.checkboxTodos = labelTodos.querySelector('.selector-todos-checkbox');
  }

  function renderizarOpciones() {
    lista.innerHTML = '';
    estado.opciones.forEach((opcion) => {
      const item = document.createElement('li');
      item.className = 'selector-opcion';
      item.setAttribute('role', 'option');
      const label = document.createElement('label');
      label.className = 'selector-opcion-label';
      const chk = document.createElement('input');
      chk.type = 'checkbox';
      chk.value = opcion.value;
      chk.disabled = Boolean(opcion.disabled);
      chk.checked = estado.seleccionados.has(opcion.value);
      chk.setAttribute('aria-checked', chk.checked ? 'true' : 'false');
      item.setAttribute('aria-selected', chk.checked ? 'true' : 'false');
      const texto = document.createElement('span');
      texto.textContent = opcion.label;
      label.append(chk, texto);
      item.appendChild(label);
      item.dataset.labelNorm = normalizarBusqueda(`${opcion.label} ${opcion.value}`);
      lista.appendChild(item);
    });
    boton.disabled = estado.opciones.length === 0;
    if (boton.disabled) {
      cerrar();
    }
    aplicarBusqueda();
    actualizarResumen();
  }

  function setOptions(nuevasOpciones, config = {}) {
    const raw = Array.isArray(nuevasOpciones) ? nuevasOpciones : [];
    estado.opciones = raw
      .map((entry) => {
        const value = normalizar(entry?.value);
        if (!value) return null;
        return {
          value,
          label: normalizar(entry?.label) || value,
          disabled: Boolean(entry?.disabled),
        };
      })
      .filter(Boolean);

    const permitidos = new Set(estado.opciones.filter((o) => !o.disabled).map((o) => o.value));
    estado.seleccionados = new Set(Array.from(estado.seleccionados).filter((value) => permitidos.has(value)));

    if (Array.isArray(config.selected)) {
      estado.seleccionados = new Set(config.selected.map(normalizar).filter((value) => permitidos.has(value)));
    }

    renderizarOpciones();

    if (config.emit === true) {
      emitirCambio();
    }
  }

  function setSelected(valores, config = {}) {
    const permitidos = new Set(estado.opciones.filter((o) => !o.disabled).map((o) => o.value));
    estado.seleccionados = new Set((Array.isArray(valores) ? valores : []).map(normalizar).filter((value) => permitidos.has(value)));
    lista.querySelectorAll('input[type="checkbox"]').forEach((chk) => {
      if (!(chk instanceof HTMLInputElement)) return;
      const checked = estado.seleccionados.has(chk.value);
      chk.checked = checked;
      chk.setAttribute('aria-checked', checked ? 'true' : 'false');
      const item = chk.closest('.selector-opcion');
      if (item) item.setAttribute('aria-selected', checked ? 'true' : 'false');
    });
    actualizarResumen();
    if (config.emit !== false) {
      emitirCambio();
    }
  }

  function clear(config = {}) {
    estado.seleccionados.clear();
    lista.querySelectorAll('input[type="checkbox"]').forEach((chk) => {
      if (!(chk instanceof HTMLInputElement)) return;
      chk.checked = false;
      chk.setAttribute('aria-checked', 'false');
      const item = chk.closest('.selector-opcion');
      if (item) item.setAttribute('aria-selected', 'false');
    });
    if (estado.buscador) {
      estado.buscador.value = '';
      aplicarBusqueda();
    }
    actualizarResumen();
    if (config.emit !== false) {
      emitirCambio();
    }
  }

  function getSelected() {
    return Array.from(estado.seleccionados);
  }

  function destroy() {
    if (estado.destruido) return;
    estado.destruido = true;
    document.removeEventListener('click', handleClickDocumento, true);
    selector.removeEventListener('keydown', handleKeydown);
    boton.removeEventListener('click', handleClickBoton);
    if (botonLimpiar) botonLimpiar.removeEventListener('click', handleLimpiar);
    if (botonLimpiarInline) botonLimpiarInline.removeEventListener('click', handleLimpiar);
    if (botonCerrar) botonCerrar.removeEventListener('click', handleCerrar);
    if (estado.buscador) estado.buscador.removeEventListener('input', handleBuscar);
    if (estado.checkboxTodos) estado.checkboxTodos.removeEventListener('change', handleTodos);
    lista.removeEventListener('change', handleChangeLista);
    INSTANCIAS.delete(selector);
  }

  function handleClickBoton(evento) {
    evento.preventDefault();
    alternar();
  }

  function handleCerrar(evento) {
    evento.preventDefault();
    cerrar();
    boton.focus();
  }

  function handleLimpiar(evento) {
    evento.preventDefault();
    evento.stopPropagation();
    clear();
  }

  function handleBuscar() {
    aplicarBusqueda();
  }

  function handleTodos() {
    const marcar = Boolean(estado.checkboxTodos?.checked);
    obtenerOpcionesVisibles().forEach(({ checkbox, item }) => {
      checkbox.checked = marcar;
      checkbox.setAttribute('aria-checked', marcar ? 'true' : 'false');
      item.setAttribute('aria-selected', marcar ? 'true' : 'false');
      if (marcar) {
        estado.seleccionados.add(checkbox.value);
      } else {
        estado.seleccionados.delete(checkbox.value);
      }
    });
    actualizarResumen();
    emitirCambio();
  }

  function handleChangeLista(evento) {
    const chk = evento.target;
    if (!(chk instanceof HTMLInputElement) || chk.type !== 'checkbox') return;
    const value = normalizar(chk.value);
    if (!value) return;
    if (chk.checked) {
      estado.seleccionados.add(value);
    } else {
      estado.seleccionados.delete(value);
    }
    chk.setAttribute('aria-checked', chk.checked ? 'true' : 'false');
    const item = chk.closest('.selector-opcion');
    if (item) item.setAttribute('aria-selected', chk.checked ? 'true' : 'false');
    actualizarResumen();
    emitirCambio();
  }

  function handleClickDocumento(evento) {
    const target = evento.target;
    if (!(target instanceof Element)) return;
    if (!selector.contains(target)) {
      cerrar();
    }
  }

  function handleKeydown(evento) {
    if (evento.key === 'Escape') {
      cerrar();
      boton.focus();
      return;
    }
    const target = evento.target;
    const editable = target instanceof HTMLElement
      && (target.tagName === 'INPUT' || target.tagName === 'TEXTAREA' || target.isContentEditable);
    if (editable) return;
    const caracter = evento.key && evento.key.length === 1 && !evento.ctrlKey && !evento.altKey && !evento.metaKey;
    if (!caracter) return;
    if (!selector.classList.contains('selector-abierto')) {
      abrir();
    }
    if (estado.buscador) {
      const anterior = estado.buscador.value || '';
      estado.buscador.value = `${anterior}${evento.key}`;
      aplicarBusqueda();
      try {
        estado.buscador.focus({ preventScroll: true });
      } catch {
        estado.buscador.focus();
      }
    }
    evento.preventDefault();
  }

  boton.addEventListener('click', handleClickBoton);
  if (botonLimpiar) botonLimpiar.addEventListener('click', handleLimpiar);
  if (botonLimpiarInline) botonLimpiarInline.addEventListener('click', handleLimpiar);
  if (botonCerrar) botonCerrar.addEventListener('click', handleCerrar);
  selector.addEventListener('keydown', handleKeydown);
  lista.addEventListener('change', handleChangeLista);
  document.addEventListener('click', handleClickDocumento, true);

  asegurarBuscadorYTodos();
  if (estado.buscador) estado.buscador.addEventListener('input', handleBuscar);
  if (estado.checkboxTodos) estado.checkboxTodos.addEventListener('change', handleTodos);
  panel.hidden = true;
  boton.setAttribute('aria-expanded', 'false');
  setOptions(Array.isArray(opciones.items) ? opciones.items : [], { selected: opciones.selected, emit: false });

  const apiInterna = {
    cerrar,
    apiPublica: {
      setOptions,
      setSelected,
      clear,
      getSelected,
      open: abrir,
      close: cerrar,
      destroy,
    },
  };

  INSTANCIAS.set(selector, apiInterna);
  return apiInterna.apiPublica;
}

export function initSelectorMultiples(scope = document, opcionesPorCampo = {}) {
  const nodos = Array.from(scope.querySelectorAll('.selector-multiple[data-campo]'));
  return nodos.map((nodo) => {
    const campo = nodo.dataset.campo || '';
    const opciones = opcionesPorCampo[campo] || {};
    return {
      campo,
      node: nodo,
      instance: initSelectorMultiple(nodo, opciones),
    };
  });
}
