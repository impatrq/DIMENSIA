// ── NAVEGACIÓN ──────────────────────────────────────────────
function showPage(id, el) {
  document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
  document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
  const page = document.getElementById('page-' + id);
  if (page) page.classList.add('active');
  if (el) el.classList.add('active');
  const titles = {
    dashboard:  'Dashboard',
    inspeccion: 'Inspección en vivo',
    piezas:     'Tipos de piezas',
    historial:  'Historial',
    reportes:   'Reportes',
  };
  document.getElementById('page-title').textContent = titles[id] || id;
  if (id === 'reportes') cargarReportes();
}

// ── FORMULARIO NUEVA PIEZA ───────────────────────────────────
function toggleForm() {
  const form = document.getElementById('form-card');
  const abriendo = form.style.display === 'none';
  form.style.display = abriendo ? 'block' : 'none';
  if (!abriendo) {
    document.getElementById('pieza-id-editando').value = '';
    document.getElementById('form-card-titulo').textContent = 'Nueva pieza';
  }
}

// ── FECHA Y HORA ─────────────────────────────────────────────
function updateDate() {
  const now = new Date();
  const fecha = now.toLocaleDateString('es-AR', { weekday:'long', year:'numeric', month:'long', day:'numeric' });
  const hora  = now.toLocaleTimeString('es-AR', { hour:'2-digit', minute:'2-digit' });
  const el = document.getElementById('page-date');
  if (el) el.textContent = `${fecha} — ${hora}`;
}
updateDate();
setInterval(updateDate, 60000);

// ── BACKEND URL ──────────────────────────────────────────────
const API = 'http://localhost:5000';

// ── FORMATO DE DIMENSIONES (pueden llegar null en mediciones parciales) ──
function fmtDim(v, unidad = '') {
  return v != null && v !== '' ? Number(v).toFixed(1) + unidad : '—' + unidad;
}

// ── CARGAR INSPECCIONES DESDE EL BACKEND ────────────────────
async function cargarInspecciones() {
  try {
    const res = await fetch(`${API}/inspecciones`);
    const data = await res.json();
    const tabla = document.getElementById('live-table');
    if (!tabla) return;

    if (data.length === 0) {
      tabla.innerHTML = '<tr><td colspan="5" style="text-align:center;color:#9AA3B8;padding:16px">Sin inspecciones todavía</td></tr>';
      return;
    }

    tabla.innerHTML = '';
    data.slice(0, 5).forEach(insp => {
      const fila = document.createElement('tr');
      fila.innerHTML = `
        <td>${insp.pieza}</td>
        <td class="mono">${fmtDim(insp.alto)}</td>
        <td class="mono">${fmtDim(insp.ancho)}</td>
        <td class="mono">${fmtDim(insp.largo)}</td>
        <td><span class="pill ${insp.resultado === 'APROBADA' ? 'ok' : 'fail'}">${insp.resultado}</span></td>
      `;
      tabla.appendChild(fila);
    });

    // ── ALERTA DE RACHA DE RECHAZOS ──────────────────
    const alerta = document.getElementById('alerta-racha');
    const alertaTexto = document.getElementById('alerta-racha-texto');
    if (alerta && alertaTexto) {
      const ultimas3 = data.slice(0, 3);
      const rachaRechazos = ultimas3.length === 3 && ultimas3.every(i => i.resultado === 'RECHAZADA');
      if (rachaRechazos) {
        const pieza = data[0].pieza || 'pieza desconocida';
        alertaTexto.innerHTML = `<strong>⚠ Alerta:</strong> Las últimas 3 inspecciones de <strong>${pieza}</strong> fueron RECHAZADAS. Detener producción y revisar herramienta.`;
        alerta.style.display = 'flex';
      } else {
        alertaTexto.innerHTML = '';
        alerta.style.display = 'none';
      }
    }

  } catch (err) {
    console.log('Backend no disponible, mostrando datos de ejemplo');
  }
}

// ── RESUMEN DEL DÍA (métricas, rendimiento por pieza y contador) ──
// Porcentaje con 1 decimal; "—" si no hay total (evita dividir por cero)
function pctDelTotal(n, total) {
  return total ? fmtDim(n * 100 / total, '%') : '—';
}

async function cargarResumen() {
  try {
    const [resResumen, resPiezas] = await Promise.all([fetch(`${API}/resumen`), fetch(`${API}/piezas`)]);
    const resumen = await resResumen.json();
    const piezas  = resPiezas.ok ? await resPiezas.json() : [];

    const { total, aprobadas, rechazadas } = resumen;
    document.querySelector('.metric-value.blue').textContent  = total || '—';
    document.querySelector('.metric-value.green').textContent = total ? aprobadas : '—';
    document.querySelector('.metric-value.red').textContent   = total ? rechazadas : '—';
    document.getElementById('metric-aprobadas-pct').textContent  = `${pctDelTotal(aprobadas, total)} del total`;
    document.getElementById('metric-rechazadas-pct').textContent = `${pctDelTotal(rechazadas, total)} del total`;

    document.getElementById('contador-total').textContent      = total || '—';
    document.getElementById('contador-aprobadas').textContent  = `${total ? aprobadas : '—'} aprobadas`;
    document.getElementById('contador-rechazadas').textContent = `${total ? rechazadas : '—'} rechazadas`;

    // Barras: todas las piezas registradas más las inspeccionadas que no estén en la tabla
    const porPieza = Object.fromEntries((resumen.por_pieza || []).map(p => [p.pieza, p]));
    const nombres  = [...new Set([...(Array.isArray(piezas) ? piezas.map(p => p.nombre) : []), ...Object.keys(porPieza)])];
    const lista = document.getElementById('rendimiento-piezas');
    if (!lista) return;
    if (nombres.length === 0) {
      lista.innerHTML = '<div style="text-align:center;color:#9AA3B8;padding:16px">Sin datos</div>';
      return;
    }
    lista.innerHTML = nombres.map(nombre => {
      const p     = porPieza[nombre];
      const pct   = p && p.total ? Math.round(p.aprobadas * 100 / p.total) : null;
      const color = pct != null && pct < 90 ? 'red' : 'green';
      return `
        <div class="bar-item">
          <div class="bar-info">
            <span class="bar-label">${nombre}</span>
            <span class="bar-pct ${color}">${pct != null ? pct + '%' : '—'}</span>
          </div>
          <div class="bar-track"><div class="bar-fill ${color}" style="width:${pct ?? 0}%"></div></div>
        </div>`;
    }).join('');
  } catch (err) {
    console.log('No se pudo cargar el resumen del día');
  }
}

// ── ALERTA DE HARDWARE ────────────────────────────────────────
async function cargarAlertaHardware() {
  try {
    const res = await fetch(`${API}/alerta_hardware`);
    const data = await res.json();
    const alerta = document.getElementById('alerta-hardware');
    const alertaTexto = document.getElementById('alerta-hardware-texto');
    if (!alerta || !alertaTexto) return;

    if (data.activa) {
      alertaTexto.innerHTML = `<strong>⚠ Alerta de hardware:</strong> ${data.mensaje}. Tipo: ${data.tipo}.`;
      alerta.style.display = 'flex';
    } else {
      alertaTexto.innerHTML = '';
      alerta.style.display = 'none';
    }
  } catch (err) {
    console.log('No se pudo cargar la alerta de hardware');
  }
}

// ── CARGAR REPORTES POR PIEZA ────────────────────────────────
async function cargarReportes() {
  const tbody = document.getElementById('reportes-table-body');
  if (!tbody) return;
  tbody.innerHTML = '<tr><td colspan="5" style="text-align:center;color:#9AA3B8;padding:16px">Cargando datos...</td></tr>';

  try {
    const res = await fetch(`${API}/inspecciones`);
    if (!res.ok) throw new Error('Error al cargar inspecciones');
    const data = await res.json();

    if (!Array.isArray(data) || data.length === 0) {
      tbody.innerHTML = '<tr><td colspan="5" style="text-align:center;color:#9AA3B8;padding:16px">No hay datos disponibles</td></tr>';
      return;
    }

    const agrupado = data.reduce((acc, insp) => {
      const pieza = insp.pieza || 'Sin tipo';
      if (!acc[pieza]) acc[pieza] = { pieza, total: 0, aprobadas: 0, rechazadas: 0 };
      acc[pieza].total += 1;
      if (insp.resultado === 'APROBADA') acc[pieza].aprobadas += 1;
      else acc[pieza].rechazadas += 1;
      return acc;
    }, {});

    const filas = Object.values(agrupado)
      .sort((a, b) => b.total - a.total)
      .map(item => {
        const tasa = item.total ? ((item.aprobadas / item.total) * 100).toFixed(1) : '0.0';
        return `
          <tr>
            <td>${item.pieza}</td>
            <td class="mono">${item.total}</td>
            <td class="mono">${item.aprobadas}</td>
            <td class="mono">${item.rechazadas}</td>
            <td class="mono">${tasa}%</td>
          </tr>`;
      })
      .join('');

    tbody.innerHTML = filas || '<tr><td colspan="5" style="text-align:center;color:#9AA3B8;padding:16px">No hay datos disponibles</td></tr>';
  } catch (err) {
    tbody.innerHTML = '<tr><td colspan="5" style="text-align:center;color:#9AA3B8;padding:16px">No se pudieron cargar los datos</td></tr>';
    console.log(err);
  }
}

// ── CARGAR PIEZAS DESDE EL BACKEND ──────────────────────────
async function cargarPiezas() {
  try {
    const res = await fetch(`${API}/piezas`);
    const data = await res.json();
    const tbody = document.querySelector('#page-piezas .data-table tbody');
    if (!tbody || data.length === 0) return;

    tbody.innerHTML = '';
    const arg = (v) => JSON.stringify(v ?? null).replace(/'/g, '&#39;');
    data.forEach(pieza => {
      const fila = document.createElement('tr');
      fila.dataset.pieza = pieza.nombre;
      const onclick = `editarPieza(${arg(pieza.id)}, ${arg(pieza.nombre)}, ${arg(pieza.norma)}, `
        + `${arg(pieza.alto_ref)}, ${arg(pieza.alto_tol)}, ${arg(pieza.ancho_ref)}, ${arg(pieza.ancho_tol)}, `
        + `${arg(pieza.largo_ref)}, ${arg(pieza.largo_tol)})`;
      fila.innerHTML = `
        <td>${pieza.nombre}</td>
        <td class="mono">${pieza.norma || '—'}</td>
        <td class="mono">${pieza.alto_ref ? pieza.alto_ref + ' mm' : '—'}</td>
        <td class="mono">${pieza.ancho_ref ? pieza.ancho_ref + ' mm' : '—'}</td>
        <td><button class="pill pend" style="cursor:pointer;border:none;font:inherit" onclick='${onclick}'>editar</button>
          <button class="pill ok" style="cursor:pointer;border:none;font:inherit" onclick='seleccionarPieza(${arg(pieza.nombre)})'>Seleccionar para este turno</button></td>
      `;
      tbody.appendChild(fila);
    });
    marcarFilaPiezaActiva();
  } catch (err) {
    console.log('No se pudieron cargar las piezas');
  }
}

// ── PIEZA ACTIVA DEL TURNO ──────────────────────────────────
let piezaActiva = null;

function mostrarPiezaActiva(data) {
  const badge = document.getElementById('pieza-activa-badge');
  if (!badge) return;
  if (!data || !data.pieza) {
    badge.textContent = 'Sin pieza seleccionada';
    badge.title = '';
    return;
  }
  badge.textContent = `Pieza: ${data.pieza}`;
  badge.title = `Alto ${fmtDim(data.alto_ref)} ± ${fmtDim(data.alto_tol, ' mm')} · `
    + `Ancho ${fmtDim(data.ancho_ref)} ± ${fmtDim(data.ancho_tol, ' mm')} · `
    + `Largo ${fmtDim(data.largo_ref)} ± ${fmtDim(data.largo_tol, ' mm')}`;
}

function marcarFilaPiezaActiva() {
  document.querySelectorAll('#page-piezas .data-table tbody tr').forEach(fila => {
    fila.classList.toggle('pieza-activa', piezaActiva != null && fila.dataset.pieza === piezaActiva);
  });
}

async function cargarPiezaActiva() {
  try {
    const res  = await fetch(`${API}/pieza_activa`);
    const data = await res.json();
    piezaActiva = data.pieza || null;
    mostrarPiezaActiva(data);
    marcarFilaPiezaActiva();
  } catch (err) {
    const badge = document.getElementById('pieza-activa-badge');
    if (badge) badge.textContent = 'Pieza: sin conexión';
    console.log('No se pudo cargar la pieza activa');
  }
}

async function seleccionarPieza(nombre) {
  try {
    const res = await fetch(`${API}/pieza_activa`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ pieza: nombre })
    });
    if (!res.ok) throw new Error('Error al seleccionar la pieza');
    await cargarPiezaActiva();
  } catch (err) {
    alert('❌ No se pudo seleccionar la pieza');
  }
}

// ── CARGAR SENSORES DESDE EL BACKEND ────────────────────────
function actualizarSensorPresencia(id, activo) {
  const dot   = document.getElementById(`${id}-dot`);
  const texto = document.getElementById(`${id}-text`);
  if (dot)   dot.classList.toggle('on', !!activo);
  if (texto) texto.textContent = activo ? 'Activado' : 'Libre';
}

function actualizarPuerta(cerrada) {
  const dot   = document.getElementById('puerta-dot');
  const texto = document.getElementById('puerta-text');
  if (dot) dot.classList.toggle('on', !!cerrada);
  if (texto) {
    texto.textContent = cerrada ? 'Cerrada' : 'Abierta';
    texto.style.color = cerrada ? 'var(--verde)' : 'var(--rojo)';
  }
}

async function cargarEstadoCiclo() {
  try {
    const res  = await fetch(`${API}/estado_ciclo`);
    const data = await res.json();
    document.getElementById('estado-ciclo-texto').textContent = data.estado;
  } catch (err) {
    console.log('No se pudo cargar el estado del ciclo');
  }
}

async function cargarSensores() {
  try {
    const res  = await fetch(`${API}/sensores`);
    const data = await res.json();
    actualizarSensorPresencia('fc-superior', data.final_carrera_superior);
    actualizarSensorPresencia('fc-inferior', data.final_carrera_inferior);
    actualizarPuerta(data.puerta_cerrada);
  } catch (err) {
    console.log('No se pudieron cargar los sensores');
  }

  try {
    const res  = await fetch(`${API}/plato`);
    const data = await res.json();
    document.getElementById('plato-estado').textContent  = data.girando ? 'Girando' : 'Detenido';
    document.getElementById('plato-angulo').textContent  = data.angulo_actual != null ? data.angulo_actual + '°' : '— °';
  } catch (err) {
    console.log('No se pudo cargar el estado del plato');
  }

  try {
    const res    = await fetch(`${API}/captura`);
    const data   = await res.json();
    const angulos = (data.capturas || []).map(c => c.angulo);
    document.getElementById('captura-cantidad').textContent = `${angulos.length} / 8`;
    document.getElementById('captura-angulos').textContent  = angulos.length ? angulos.map(a => a + '°').join(', ') : '—';
  } catch (err) {
    console.log('No se pudo cargar el estado de las capturas');
  }

  await cargarEstadoCiclo();
}

// ── CARGAR SERVOS DESDE EL BACKEND ──────────────────────────
async function cargarServos() {
  try {
    const res  = await fetch(`${API}/servos`);
    const data = await res.json();
    const actualizar = (id, activo) => {
      const dot   = document.getElementById(`${id}-dot`);
      const texto = document.getElementById(`${id}-text`);
      if (dot)   dot.classList.toggle('on', !!activo);
      if (texto) texto.textContent = activo ? 'Activo' : 'Inactivo';
    };
    actualizar('rotacion',  data.rotacion?.activo);
    actualizar('empujador', data.empujador?.activo);

    const posicion = data.plataforma?.posicion || 'centro';
    const definida = posicion === 'izquierda' || posicion === 'derecha';
    const dot   = document.getElementById('plataforma-dot');
    const texto = document.getElementById('plataforma-text');
    if (dot) {
      dot.classList.toggle('on', definida);
      dot.classList.toggle('neutral', !definida);
    }
    if (texto) texto.textContent = posicion.charAt(0).toUpperCase() + posicion.slice(1);
  } catch (err) {
    console.log('No se pudieron cargar los servos');
  }
}

// ── CARGAR ULTIMA INSPECCION EN VIVO ────────────────────────
async function cargarUltimaInspeccion() {
  try {
    const res  = await fetch(`${API}/inspecciones`);
    const data = await res.json();
    if (data.length === 0) return;

    const insp = data[0];
    document.getElementById('insp-tipo').textContent     = insp.pieza    || '—';
    document.getElementById('insp-numero-serie').textContent = insp.numero_serie || '—';
    document.getElementById('insp-alto').textContent     = fmtDim(insp.alto,  ' mm');
    document.getElementById('insp-ancho').textContent    = fmtDim(insp.ancho, ' mm');
    document.getElementById('insp-largo').textContent    = fmtDim(insp.largo, ' mm');
    document.getElementById('insp-operario').textContent = insp.operario || '—';

    const aprobada = insp.resultado === 'APROBADA';
    document.getElementById('insp-resultado-box').className       = aprobada ? 'result-box ok' : 'result-box fail';
    document.getElementById('insp-resultado-icon').textContent    = aprobada ? '✓' : '✗';
    document.getElementById('insp-resultado-titulo').textContent  = insp.resultado;
    // Medición parcial: listar solo las dimensiones que se midieron
    const medidas = ['alto', 'ancho', 'largo'].filter(dim => insp[dim] != null && insp[dim] !== '');
    document.getElementById('insp-resultado-sub').textContent     = medidas.length < 3
      ? `${aprobada ? 'Dentro' : 'Fuera'} de tolerancia (medido: ${medidas.join(', ') || '—'})`
      : aprobada
        ? 'Todas las dimensiones dentro de tolerancia'
        : 'Una o más dimensiones fuera de tolerancia';
    document.getElementById('insp-estado-etiqueta').textContent  = 'Última medición';

    // Norma de la pieza (viene en GET /piezas)
    try {
      const resPiezas = await fetch(`${API}/piezas`);
      const piezas    = await resPiezas.json();
      const pieza     = Array.isArray(piezas) ? piezas.find(p => p.nombre === insp.pieza) : null;
      document.getElementById('insp-norma').textContent = pieza?.norma || '—';
    } catch (err) {
      document.getElementById('insp-norma').textContent = '—';
    }

  } catch (err) {
    console.log('No se pudo cargar la última inspección');
  }
}

// ── INICIAR ──────────────────────────────────────────────────
cargarInspecciones();
cargarResumen();
cargarPiezas();
cargarPiezaActiva();
cargarSensores();
cargarUltimaInspeccion();
cargarHistorial();
cargarServos();
cargarAlertaHardware();
setInterval(cargarInspecciones,    5000);
setInterval(cargarResumen,         5000);
setInterval(cargarSensores,        2000);
setInterval(cargarUltimaInspeccion,3000);
setInterval(cargarHistorial,      10000);
setInterval(cargarServos,          2000);
setInterval(cargarAlertaHardware,  5000);

// ── GUARDAR PIEZA ──────────────────────────────────────
async function guardarPieza() {
  const idEditando = document.getElementById('pieza-id-editando').value;
  const datos = {
    nombre:    document.getElementById('pieza-nombre').value,
    norma:     document.getElementById('pieza-norma').value,
    alto_ref:  parseFloat(document.getElementById('pieza-alto-ref').value),
    alto_tol:  parseFloat(document.getElementById('pieza-alto-tol').value),
    ancho_ref: parseFloat(document.getElementById('pieza-ancho-ref').value),
    ancho_tol: parseFloat(document.getElementById('pieza-ancho-tol').value),
    largo_ref: parseFloat(document.getElementById('pieza-largo-ref').value),
    largo_tol: parseFloat(document.getElementById('pieza-largo-tol').value),
  };

  const url    = idEditando ? `${API}/piezas/${idEditando}` : `${API}/piezas`;
  const metodo = idEditando ? 'PUT' : 'POST';

  const respuesta = await fetch(url, {
    method: metodo,
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(datos)
  });

  if (respuesta.ok) {
    if (idEditando) {
      alert('✅ Pieza actualizada correctamente');
      toggleForm();
      cargarPiezas();
    } else {
      const resultado = await respuesta.json();
      generarQR(datos.nombre, datos.norma, resultado.id);
      setTimeout(() => {
        alert('✅ Pieza guardada correctamente');
        toggleForm();
      }, 500);
    }
  } else {
    alert('❌ Error al guardar la pieza');
  }
}

// ── EDITAR PIEZA EXISTENTE ───────────────────────────────
function editarPieza(id, nombre, norma, altoRef, altoTol, anchoRef, anchoTol, largoRef, largoTol) {
  document.getElementById('pieza-nombre').value    = nombre ?? '';
  document.getElementById('pieza-norma').value     = norma ?? '';
  document.getElementById('pieza-alto-ref').value  = altoRef ?? '';
  document.getElementById('pieza-alto-tol').value  = altoTol ?? '';
  document.getElementById('pieza-ancho-ref').value = anchoRef ?? '';
  document.getElementById('pieza-ancho-tol').value = anchoTol ?? '';
  document.getElementById('pieza-largo-ref').value = largoRef ?? '';
  document.getElementById('pieza-largo-tol').value = largoTol ?? '';
  document.getElementById('pieza-id-editando').value = id;
  document.getElementById('form-card-titulo').textContent = 'Editar pieza';
  document.getElementById('form-card').style.display = 'block';
}

// ── GENERAR QR ──────────────────────────────────────────
function generarQR(nombre, norma, id) {
  const contenedor = document.getElementById('qr-canvas');
  contenedor.innerHTML = '';
  new QRCode(contenedor, {
    text: `DIMENSIA|${id}|${nombre}|${norma}`,
    width: 80, height: 80,
  });
}

// ── LOGIN DE OPERARIOS ──────────────────────────────────
let operarioActual = null;

function iniciarSesion() {
  const nombre = document.getElementById('login-nombre').value.trim();
  const legajo = document.getElementById('login-legajo').value.trim();
  if (!nombre || !legajo) { alert('⚠️ Completá tu nombre y legajo para continuar'); return; }
  operarioActual = { nombre, legajo };
  fetch('http://127.0.0.1:5000/operario_activo', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ operario: nombre, legajo: legajo })
  });
  const badge = document.getElementById('operario-badge');
  badge.textContent  = `👤 ${nombre} — Legajo ${legajo}`;
  badge.style.display = 'block';
  document.getElementById('login-screen').style.display = 'none';
}

// ── EXPORTAR CSV ──────────────────────────────────────
async function exportarCSV(filtros = {}) {
  try {
    const params = new URLSearchParams();
    Object.entries(filtros).forEach(([k, v]) => { if (v) params.set(k, v); });
    const qs  = params.toString();
    const res = await fetch(`${API}/exportar${qs ? '?' + qs : ''}`);
    if (!res.ok) { alert('No hay inspecciones para exportar.'); return false; }
    const blob = await res.blob();
    const a    = document.createElement('a');
    a.href     = URL.createObjectURL(blob);
    a.download = 'inspecciones_dimensia.csv';
    a.click();
    return true;
  } catch (err) {
    alert('Error al conectar con el backend para exportar.');
    return false;
  }
}

// ── GENERAR REPORTE (Reportes) ────────────────────────────
function rangoPeriodo(periodo) {
  const hoy = new Date();
  const iso = d => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
  let desde = new Date(hoy);
  if (periodo === 'Esta semana') desde.setDate(hoy.getDate() - ((hoy.getDay() + 6) % 7)); // lunes
  else if (periodo === 'Este mes') desde = new Date(hoy.getFullYear(), hoy.getMonth(), 1);
  return { desde: iso(desde), hasta: iso(hoy) }; // "Turno actual" y "Hoy": el día de hoy
}

async function generarReporte(btn) {
  const formato = document.getElementById('reporte-formato').value;
  if (formato !== 'CSV') {
    alert('PDF no disponible desde el dashboard: se genera con generador.py desde la Raspberry');
    return;
  }
  const textoOriginal = btn.textContent;
  btn.textContent = 'Generando...';
  const ok = await exportarCSV({
    ...rangoPeriodo(document.getElementById('reporte-periodo').value),
    tipo: document.getElementById('reporte-tipo').value,
  });
  btn.textContent = ok ? 'Reporte generado ✓' : textoOriginal;
}

// ── CARGAR HISTORIAL DESDE EL BACKEND ───────────────────────
let historialData = [];

// Valores actuales de los filtros (estado = APROBADA/RECHAZADA, fechas = aaaa-mm-dd)
function filtrosHistorial() {
  const val = id => { const el = document.getElementById(id); return el ? el.value : ''; };
  return {
    tipo:   val('filtro-tipo'),
    estado: val('filtro-estado'),
    desde:  val('filtro-desde'),
    hasta:  val('filtro-hasta'),
  };
}

async function cargarHistorial() {
  try {
    const params = new URLSearchParams();
    Object.entries(filtrosHistorial()).forEach(([k, v]) => { if (v) params.set(k, v); });
    const qs   = params.toString();
    const res  = await fetch(`${API}/inspecciones${qs ? '?' + qs : ''}`);
    const data = await res.json();
    historialData = Array.isArray(data) ? data : [];
    filtrarHistorial();
  } catch (err) {
    console.log('No se pudo cargar el historial');
  }
}

// ── FILTRAR HISTORIAL POR N° DE SERIE (tiempo real, case-insensitive) ──
function filtrarHistorial() {
  const input   = document.getElementById('filtro-serie');
  const busqueda = input ? input.value.trim().toLowerCase() : '';

  // Los mismos filtros se aplican acá por si el backend ignora algún parámetro
  const { tipo, estado, desde, hasta } = filtrosHistorial();
  const data = historialData.filter(insp => {
    const dia = (insp.fecha || '').substring(0, 10);
    return (!busqueda || (insp.numero_serie || '').toLowerCase().includes(busqueda))
      && (!tipo   || insp.pieza === tipo)
      && (!estado || insp.resultado === estado)
      && (!desde  || (dia && dia >= desde))
      && (!hasta  || (dia && dia <= hasta));
  });

  renderHistorial(data);
}

function renderHistorial(data) {
  const tbody = document.getElementById('historial-table');
  if (!tbody) return;

  if (data.length === 0) {
    tbody.innerHTML = '<tr><td colspan="10" style="text-align:center;color:#9AA3B8;padding:16px">Sin inspecciones todavía</td></tr>';
  } else {
    tbody.innerHTML = '';
    data.forEach(insp => {
      const fila  = document.createElement('tr');
      const fecha = insp.fecha ? insp.fecha.replace('T', ' ').substring(0, 16) : '—';
      fila.innerHTML = `
        <td class="mono gray">#${insp.id}</td>
        <td>${insp.pieza || '—'}</td>
        <td class="mono">${insp.numero_serie || '—'}</td>
        <td class="mono">${fmtDim(insp.alto)}</td>
        <td class="mono">${fmtDim(insp.ancho)}</td>
        <td class="mono">${fmtDim(insp.largo)}</td>
        <td><span class="pill ${insp.resultado === 'APROBADA' ? 'ok' : 'fail'}">${insp.resultado}</span></td>
        <td>${insp.resultado === 'APROBADA' || insp.motivo_rechazo == null ? '—' : insp.motivo_rechazo}</td>
        <td class="gray small">${fecha}</td>
        <td><button class="btn-ghost" onclick="verCapturas(${insp.id})">Ver</button></td>
      `;
      tbody.appendChild(fila);
    });
  }

  const contador = document.querySelector('#page-historial .card-title');
  if (contador) contador.textContent = `${data.length} inspecciones encontradas`;
}

// ── CAPTURAS DE CÁMARA ───────────────────────────────
async function verCapturas(inspeccionId) {
  try {
    const res  = await fetch(`${API}/capturas/${inspeccionId}`);
    const data = await res.json();

    if (data.superior == null && data.lateral == null) {
      alert('Esta inspeccion no tiene capturas disponibles');
      return;
    }

    const superiorImg   = document.getElementById('captura-superior-img');
    const superiorPlaceholder = document.getElementById('captura-superior-placeholder');
    const lateralImg    = document.getElementById('captura-lateral-img');
    const lateralPlaceholder  = document.getElementById('captura-lateral-placeholder');

    if (data.superior) {
      superiorImg.src = `${API}${data.superior}`;
      superiorImg.style.display = 'block';
      superiorPlaceholder.style.display = 'none';
    } else {
      superiorImg.style.display = 'none';
      superiorPlaceholder.style.display = 'block';
    }

    if (data.lateral) {
      lateralImg.src = `${API}${data.lateral}`;
      lateralImg.style.display = 'block';
      lateralPlaceholder.style.display = 'none';
    } else {
      lateralImg.style.display = 'none';
      lateralPlaceholder.style.display = 'block';
    }

    document.getElementById('modal-capturas').style.display = 'flex';
  } catch (err) {
    console.log('No se pudieron cargar las capturas');
  }
}

function cerrarModalCapturas() {
  document.getElementById('modal-capturas').style.display = 'none';
}

// ── CALIBRACION ──────────────────────────────────────
async function cargarCalibracion() {
  const tbody = document.getElementById('calibracion-table');
  if (!tbody) return;

  tbody.innerHTML = '<tr><td colspan="5" style="text-align:center;color:#9AA3B8;padding:16px">Consultando backend...</td></tr>';

  try {
    let calibraciones = [];

    try {
      const res = await fetch(`${API}/calibraciones`);
      const data = await res.json();
      calibraciones = Array.isArray(data) ? data.slice(0, 5) : [];
    } catch (_) {
      const res = await fetch(`${API}/calibracion`);
      const data = await res.json();
      if (data && Object.keys(data).length > 0) calibraciones = [data];
    }

    if (calibraciones.length === 0) {
      tbody.innerHTML = '<tr><td colspan="5" style="text-align:center;color:#9AA3B8;padding:16px">Sin calibraciones registradas</td></tr>';
      return;
    }

    tbody.innerHTML = '';
    calibraciones.forEach(cal => {
      const fecha = cal.fecha ? cal.fecha.replace('T', ' ').substring(0, 19) : '—';
      const sup = cal.px_por_mm_superior;
      const lat = cal.px_por_mm_lateral;

      let consistenciaHTML = '—';
      if (sup != null && lat != null) {
        const diff = Math.abs(sup - lat);
        consistenciaHTML = diff < 0.5
          ? '<span class="pill ok">OK</span>'
          : '<span class="pill" style="background:#FEF3C7;color:#92400E">Revisar</span>';
      }

      let vigenciaHTML = '—';
      if (cal.fecha) {
        const horasDesde = (Date.now() - new Date(cal.fecha).getTime()) / 3600000;
        vigenciaHTML = horasDesde < 24
          ? '<span class="pill ok">Vigente</span>'
          : '<span class="pill fail">Vencida</span>';
      }

      const fila = document.createElement('tr');
      fila.innerHTML = `
        <td class="gray small">${fecha}</td>
        <td class="mono">${sup != null ? sup + ' px/mm' : '—'}</td>
        <td class="mono">${lat != null ? lat + ' px/mm' : '—'}</td>
        <td>${consistenciaHTML}</td>
        <td>${vigenciaHTML}</td>
      `;
      tbody.appendChild(fila);
    });
  } catch (err) {
    tbody.innerHTML = '<tr><td colspan="5" style="text-align:center;color:#9AA3B8;padding:16px">Error: no se pudo conectar con el backend</td></tr>';
  }
}
