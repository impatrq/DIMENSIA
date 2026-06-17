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
}

// ── FORMULARIO NUEVA PIEZA ───────────────────────────────────
function toggleForm() {
  const form = document.getElementById('form-card');
  form.style.display = form.style.display === 'none' ? 'block' : 'none';
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
        <td class="mono">${insp.alto ? insp.alto.toFixed(1) : '—'}</td>
        <td class="mono">${insp.ancho ? insp.ancho.toFixed(1) : '—'}</td>
        <td class="mono">${insp.largo ? insp.largo.toFixed(1) : '—'}</td>
        <td><span class="pill ${insp.resultado === 'APROBADA' ? 'ok' : 'fail'}">${insp.resultado}</span></td>
      `;
      tabla.appendChild(fila);
    });

    const total = data.length;
    const aprobadas = data.filter(i => i.resultado === 'APROBADA').length;
    const rechazadas = total - aprobadas;
    document.querySelector('.metric-value.blue').textContent = total;
    document.querySelector('.metric-value.green').textContent = aprobadas;
    document.querySelector('.metric-value.red').textContent = rechazadas;

  } catch (err) {
    console.log('Backend no disponible, mostrando datos de ejemplo');
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
    data.forEach(pieza => {
      const fila = document.createElement('tr');
      fila.innerHTML = `
        <td>${pieza.nombre}</td>
        <td class="mono">${pieza.norma || '—'}</td>
        <td class="mono">${pieza.od_ref ? pieza.od_ref + ' mm' : '—'}</td>
        <td class="mono">${pieza.id_ref ? pieza.id_ref + ' mm' : '—'}</td>
        <td><span class="pill pend" style="cursor:pointer">editar</span></td>
      `;
      tbody.appendChild(fila);
    });
  } catch (err) {
    console.log('No se pudieron cargar las piezas');
  }
}

// ── CARGAR SENSORES DESDE EL BACKEND ────────────────────────
function actualizarSensorPresencia(id, presente) {
  const dot   = document.getElementById(`${id}-dot`);
  const texto = document.getElementById(`${id}-text`);
  if (dot)   dot.classList.toggle('on', !!presente);
  if (texto) texto.textContent = presente ? 'Detectado' : 'Libre';
}

async function cargarSensores() {
  try {
    const res  = await fetch(`${API}/sensores`);
    const data = await res.json();
    actualizarSensorPresencia('sensor-s1', data.S1);
    actualizarSensorPresencia('sensor-s2', data.S2);
    actualizarSensorPresencia('sensor-s3', data.S3);
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
    actualizar('servo1', data.servo1?.activo);
    actualizar('servo2', data.servo2?.activo);
    actualizar('servo3', data.servo3?.activo);
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
    document.getElementById('insp-norma').textContent    = '—';
    document.getElementById('insp-alto').textContent     = insp.alto     ? insp.alto.toFixed(1)  + ' mm' : '— mm';
    document.getElementById('insp-ancho').textContent    = insp.ancho    ? insp.ancho.toFixed(1) + ' mm' : '— mm';
    document.getElementById('insp-largo').textContent    = insp.largo    ? insp.largo.toFixed(1) + ' mm' : '— mm';
    document.getElementById('insp-operario').textContent = insp.operario || '—';

    const aprobada = insp.resultado === 'APROBADA';
    document.getElementById('insp-resultado-box').className       = aprobada ? 'result-box ok' : 'result-box fail';
    document.getElementById('insp-resultado-icon').textContent    = aprobada ? '✓' : '✗';
    document.getElementById('insp-resultado-titulo').textContent  = insp.resultado;
    document.getElementById('insp-resultado-sub').textContent     = aprobada
      ? 'Todas las dimensiones dentro de tolerancia'
      : 'Una o más dimensiones fuera de tolerancia';

  } catch (err) {
    console.log('No se pudo cargar la última inspección');
  }
}

// ── INICIAR ──────────────────────────────────────────────────
cargarInspecciones();
cargarPiezas();
cargarSensores();
cargarUltimaInspeccion();
cargarHistorial();
cargarServos();
setInterval(cargarInspecciones,    5000);
setInterval(cargarSensores,        2000);
setInterval(cargarUltimaInspeccion,3000);
setInterval(cargarHistorial,      10000);
setInterval(cargarServos,          2000);

// ── GUARDAR PIEZA ──────────────────────────────────────
async function guardarPieza() {
  const datos = {
    nombre:    document.getElementById('pieza-nombre').value,
    norma:     document.getElementById('pieza-norma').value,
    od_ref:    parseFloat(document.getElementById('pieza-od-ref').value),
    od_tol:    parseFloat(document.getElementById('pieza-od-tol').value),
    id_ref:    parseFloat(document.getElementById('pieza-id-ref').value),
    id_tol:    parseFloat(document.getElementById('pieza-id-tol').value),
    largo_ref: parseFloat(document.getElementById('pieza-largo-ref').value),
    largo_tol: parseFloat(document.getElementById('pieza-largo-tol').value),
  };

  const respuesta = await fetch('http://127.0.0.1:5000/piezas', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(datos)
  });

  if (respuesta.ok) {
    const resultado = await respuesta.json();
    generarQR(datos.nombre, datos.norma, resultado.id);
    setTimeout(() => {
      alert('✅ Pieza guardada correctamente');
      toggleForm();
    }, 500);
  } else {
    alert('❌ Error al guardar la pieza');
  }
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
async function exportarCSV() {
  try {
    const res  = await fetch(`${API}/inspecciones`);
    const data = await res.json();
    if (data.length === 0) { alert('No hay inspecciones para exportar.'); return; }

    const encabezado = ['#', 'Pieza', 'Alto (mm)', 'Ancho (mm)', 'Largo (mm)', 'Estado', 'Operario', 'Fecha'];
    const filas = data.map(i => [
      i.id, i.pieza || '—',
      i.alto  ? i.alto.toFixed(1)  : '—',
      i.ancho ? i.ancho.toFixed(1) : '—',
      i.largo ? i.largo.toFixed(1) : '—',
      i.resultado || '—', i.operario || '—', i.fecha || '—'
    ]);

    const csv  = [encabezado, ...filas].map(f => f.join(',')).join('\n');
    const blob = new Blob([csv], { type: 'text/csv' });
    const a    = document.createElement('a');
    a.href     = URL.createObjectURL(blob);
    a.download = 'inspecciones_dimensia.csv';
    a.click();
  } catch (err) {
    alert('Error al conectar con el backend para exportar.');
  }
}

// ── CARGAR HISTORIAL DESDE EL BACKEND ───────────────────────
async function cargarHistorial() {
  try {
    const res   = await fetch(`${API}/inspecciones`);
    const data  = await res.json();
    const tbody = document.getElementById('historial-table');
    if (!tbody) return;

    if (data.length === 0) {
      tbody.innerHTML = '<tr><td colspan="7" style="text-align:center;color:#9AA3B8;padding:16px">Sin inspecciones todavía</td></tr>';
      return;
    }

    tbody.innerHTML = '';
    data.forEach(insp => {
      const fila  = document.createElement('tr');
      const fecha = insp.fecha ? insp.fecha.replace('T', ' ').substring(0, 16) : '—';
      fila.innerHTML = `
        <td class="mono gray">#${insp.id}</td>
        <td>${insp.pieza || '—'}</td>
        <td class="mono">${insp.alto  ? insp.alto.toFixed(1)  : '—'}</td>
        <td class="mono">${insp.ancho ? insp.ancho.toFixed(1) : '—'}</td>
        <td class="mono">${insp.largo ? insp.largo.toFixed(1) : '—'}</td>
        <td><span class="pill ${insp.resultado === 'APROBADA' ? 'ok' : 'fail'}">${insp.resultado}</span></td>
        <td class="gray small">${fecha}</td>
      `;
      tbody.appendChild(fila);
    });

    const contador = document.querySelector('#page-historial .card-title');
    if (contador) contador.textContent = `${data.length} inspecciones encontradas`;

  } catch (err) {
    console.log('No se pudo cargar el historial');
  }
}

// ── CALIBRACION ──────────────────────────────────────
async function verCalibracion() {
  const estado     = document.getElementById('calib-estado');
  const resultados = document.getElementById('calib-resultados');
  const factorSup  = document.getElementById('calib-factor-superior');
  const factorLat  = document.getElementById('calib-factor-lateral');
  const fecha      = document.getElementById('calib-fecha');

  estado.textContent = 'Consultando backend...';
  resultados.style.display = 'none';

  try {
    const res  = await fetch(`${API}/calibracion`);
    const data = await res.json();

    if (!data || Object.keys(data).length === 0) {
      estado.textContent = 'Sin calibracion registrada aun.';
      return;
    }

    estado.textContent = '';
    if (factorSup) factorSup.textContent = data.factor_superior != null ? data.factor_superior + ' px/mm' : '—';
    if (factorLat) factorLat.textContent = data.factor_lateral  != null ? data.factor_lateral  + ' px/mm' : '—';
    if (fecha)     fecha.textContent     = data.fecha ?? '—';
    resultados.style.display = 'block';

  } catch (err) {
    estado.textContent = 'Error: no se pudo conectar con el backend.';
  }
}
