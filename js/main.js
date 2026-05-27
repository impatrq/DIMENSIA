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
      tabla.innerHTML = '<tr><td colspan="4" style="text-align:center;color:#9AA3B8;padding:16px">Sin inspecciones todavía</td></tr>';
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

    // Actualizar métricas
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
async function cargarSensores() {
  try {
    const res = await fetch(`${API}/sensores`);
    const data = await res.json();

    document.getElementById('sensor-s1').textContent  = data.S1  !== null ? data.S1  + ' mm' : '— mm';
    document.getElementById('sensor-s2').textContent  = data.S2  !== null ? data.S2  + ' mm' : '— mm';
    document.getElementById('sensor-s2p').textContent = data.S2p !== null ? data.S2p + ' mm' : '— mm';
    document.getElementById('sensor-s3').textContent  = data.S3  !== null ? data.S3  + ' mm' : '— mm';
    document.getElementById('sensor-s3p').textContent = data.S3p !== null ? data.S3p + ' mm' : '— mm';

    const resCalib = await fetch(`${API}/calibracion`);
    const calib = await resCalib.json();

    if (calib.ref_s1 && data.S1 !== null) {
      const alto = (calib.ref_s1 - data.S1).toFixed(1);
      document.getElementById('dim-alto').textContent = alto + ' mm';
    }
    if (calib.d_s2_s2p && data.S2 !== null && data.S2p !== null) {
      const ancho = (calib.d_s2_s2p - data.S2 - data.S2p).toFixed(1);
      document.getElementById('dim-ancho').textContent = ancho + ' mm';
    }
    if (calib.d_s3_s3p && data.S3 !== null && data.S3p !== null) {
      const largo = (calib.d_s3_s3p - data.S3 - data.S3p).toFixed(1);
      document.getElementById('dim-largo').textContent = largo + ' mm';
    }

    const alerta = document.getElementById('sensor-alerta');
    const algunNull = Object.values(data).some(v => v === null);
    alerta.style.display = algunNull ? 'block' : 'none';

  } catch (err) {
    console.log('No se pudieron cargar los sensores');
  }
}

// ── INICIAR ──────────────────────────────────────────────────
cargarInspecciones();
cargarPiezas();
cargarSensores();
setInterval(cargarInspecciones, 5000);
setInterval(cargarSensores, 2000);

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
    const idPieza = resultado.id;
    generarQR(datos.nombre, datos.norma, idPieza);
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
  const texto = `DIMENSIA|${id}|${nombre}|${norma}`;
  new QRCode(contenedor, {
    text: texto,
    width: 80,
    height: 80,
  });
}

// ── LOGIN DE OPERARIOS ──────────────────────────────────
let operarioActual = null;

function iniciarSesion() {
  const nombre = document.getElementById('login-nombre').value.trim();
  const legajo = document.getElementById('login-legajo').value.trim();

  if (!nombre || !legajo) {
    alert('⚠️ Completá tu nombre y legajo para continuar');
    return;
  }

  operarioActual = { nombre, legajo };

  fetch('http://127.0.0.1:5000/operario_activo', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ operario: nombre, legajo: legajo })
  });

  const badge = document.getElementById('operario-badge');
  badge.textContent = `👤 ${nombre} — Legajo ${legajo}`;
  badge.style.display = 'block';
  document.getElementById('login-screen').style.display = 'none';
}

// ── EXPORTAR CSV ──────────────────────────────────────
function exportarCSV() {
  const encabezado = ['#', 'Pieza', 'Alto (mm)', 'Ancho (mm)', 'Largo (mm)', 'Estado', 'Fecha y Hora'];
  const datos = [
    ['247', 'Niple NPT 1/2"', '21.3', '21.3', '58.2', 'Aprobada', 'Hoy 14:32'],
    ['246', 'Brida DN25',     '25.8', '25.8', '42.1', 'Rechazada','Hoy 14:31'],
    ['245', 'Union NPT 3/4"', '26.7', '26.7', '65.0', 'Aprobada', 'Hoy 14:29'],
    ['244', 'Niple NPT 1/2"', '21.3', '21.3', '57.9', 'Aprobada', 'Hoy 14:28'],
    ['243', 'Codo 90° 1/2"',  '21.3', '21.3', '38.5', 'Aprobada', 'Hoy 14:26'],
    ['242', 'Brida DN25',     '25.8', '25.8', '41.9', 'Rechazada','Hoy 14:24'],
  ];

  const csv = [encabezado, ...datos].map(f => f.join(',')).join('\n');
  const blob = new Blob([csv], { type: 'text/csv' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = 'inspecciones_dimensia.csv';
  a.click();
}

// ── CALIBRACION ──────────────────────────────────────
async function iniciarCalibracion() {
  const estado = document.getElementById('calib-estado');
  const resultados = document.getElementById('calib-resultados');
  const valores = document.getElementById('calib-valores');

  estado.textContent = 'Conectando con el backend...';
  resultados.style.display = 'none';

  try {
    const res = await fetch(`${API}/calibracion`, { method: 'POST' });
    const data = await res.json();

    estado.textContent = '';
    valores.textContent =
      `REF_S1: ${data.REF_S1} mm  |  ` +
      `D_S2_S2p: ${data.D_S2_S2p} mm  |  ` +
      `D_S3_S3p: ${data.D_S3_S3p} mm`;
    resultados.style.display = 'block';

  } catch (err) {
    estado.textContent = 'Error: no se pudo conectar con el backend.';
  }
}
