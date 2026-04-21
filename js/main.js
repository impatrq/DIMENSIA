// ── NAVEGACIÓN ──────────────────────────────────────────────
function showPage(id, el) {
  // Ocultar todas las páginas
  document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
  // Desactivar todos los nav items
  document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
  // Mostrar la página seleccionada
  const page = document.getElementById('page-' + id);
  if (page) page.classList.add('active');
  // Activar el nav item
  if (el) el.classList.add('active');
  // Actualizar el título
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

// ── FECHA Y HORA EN TOPBAR ───────────────────────────────────
function updateDate() {
  const now = new Date();
  const opciones = { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' };
  const fecha = now.toLocaleDateString('es-AR', opciones);
  const hora  = now.toLocaleTimeString('es-AR', { hour: '2-digit', minute: '2-digit' });
  const el = document.getElementById('page-date');
  if (el) el.textContent = `${fecha} — ${hora}`;
}
updateDate();
setInterval(updateDate, 60000);

// ── SIMULACIÓN DE DATOS EN VIVO (solo para demo) ─────────────
const piezas = [
  { nombre: 'Niple NPT 1/2"', od: 21.34, id: 14.02, ok: true },
  { nombre: 'Union NPT 3/4"', od: 26.71, id: 18.01, ok: true },
  { nombre: 'Brida DN25',     od: 26.10, id: null,  ok: false },
  { nombre: 'Codo 90° 1/2"', od: 21.35, id: null,  ok: true },
];

let contador = 247;

function agregarFilaTabla() {
  const p = piezas[Math.floor(Math.random() * piezas.length)];
  const tabla = document.getElementById('live-table');
  if (!tabla) return;

  contador++;
  const fila = document.createElement('tr');
  fila.innerHTML = `
    <td>${p.nombre}</td>
    <td class="mono">${p.od.toFixed(2)}</td>
    <td class="mono">${p.id ? p.id.toFixed(2) : '—'}</td>
    <td><span class="pill ${p.ok ? 'ok' : 'fail'}">${p.ok ? 'Aprobada' : 'Rechazada'}</span></td>
  `;
  fila.style.opacity = '0';
  fila.style.transition = 'opacity 0.3s';
  tabla.insertBefore(fila, tabla.firstChild);
  setTimeout(() => fila.style.opacity = '1', 10);

  // Mantener solo 5 filas
  while (tabla.rows.length > 5) {
    tabla.deleteRow(tabla.rows.length - 1);
  }
}

// Agregar una nueva fila cada 4 segundos (simulación)
setInterval(agregarFilaTabla, 4000);
