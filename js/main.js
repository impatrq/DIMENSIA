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
        <td class="mono">${insp.od ? insp.od.toFixed(2) : '—'}</td>
        <td class="mono">${insp.id_med ? insp.id_med.toFixed(2) : '—'}</td>
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

// ── INICIAR ──────────────────────────────────────────────────
cargarInspecciones();
cargarPiezas();
setInterval(cargarInspecciones, 5000);
