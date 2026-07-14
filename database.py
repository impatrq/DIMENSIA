import sqlite3
from datetime import datetime, timezone, timedelta

DB = 'dimensia.db'

TZ_ARG = timezone(timedelta(hours=-3))

def fecha_arg():
    return datetime.now(TZ_ARG).strftime('%Y-%m-%d %H:%M:%S')

# ── INICIALIZAR BASE DE DATOS ────────────────────────
def init_db():
    conn = sqlite3.connect(DB)
    c = conn.cursor()

    # Tabla de tipos de piezas
    c.execute('''
        CREATE TABLE IF NOT EXISTS piezas (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre     TEXT NOT NULL,
            norma      TEXT,
            alto_ref   REAL,
            alto_tol   REAL,
            ancho_ref  REAL,
            ancho_tol  REAL,
            largo_ref  REAL,
            largo_tol  REAL
        )
    ''')

    # Tabla de inspecciones
    c.execute('''
        CREATE TABLE IF NOT EXISTS inspecciones (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            pieza        TEXT NOT NULL,
            numero_serie TEXT,
            alto         REAL,
            ancho        REAL,
            largo        REAL,
            resultado    TEXT,
            fecha        TIMESTAMP,
            operario     TEXT,
            legajo       TEXT,
            lectura_s2p  REAL,
            lectura_s3p  REAL
        )
    ''')

    # Tabla de calibracion de camaras (factor px/mm)
    c.execute('''
        CREATE TABLE IF NOT EXISTS calibracion (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            px_por_mm_superior  REAL,
            px_por_mm_lateral   REAL,
            fecha            TIMESTAMP
        )
    ''')

    # Cargar piezas de ejemplo si la tabla esta vacia
    c.execute('SELECT COUNT(*) FROM piezas')
    if c.fetchone()[0] == 0:
        piezas_ejemplo = [
            ('Niple NPT 1/2"', 'ASME B16.11', 21.3, 0.5, 26.7, 0.5, 58.0, 1.0),
            ('Union NPT 3/4"', 'ASME B16.11', 26.7, 0.5, 33.4, 0.5, 65.0, 1.0),
            ('Brida DN25',     'DIN 2999',    12.0, 0.5, 115.0, 1.0, 42.0, 1.0),
            ('Codo 90 1/2"',  'ASME B16.11', 21.3, 0.5, 26.7, 0.5, 38.0, 1.0),
        ]
        c.executemany(
            'INSERT INTO piezas (nombre, norma, alto_ref, alto_tol, ancho_ref, ancho_tol, largo_ref, largo_tol) VALUES (?,?,?,?,?,?,?,?)',
            piezas_ejemplo
        )

    conn.commit()
    conn.close()

# ── GUARDAR INSPECCION ───────────────────────────────
def guardar_inspeccion(datos):
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute('''
        INSERT INTO inspecciones
          (pieza, numero_serie, alto, ancho, largo, resultado, fecha, operario, legajo, lectura_s2p, lectura_s3p)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        datos.get('pieza'),
        datos.get('numero_serie'),
        datos.get('alto'),
        datos.get('ancho'),
        datos.get('largo'),
        datos.get('resultado'),
        fecha_arg(),
        datos.get('operario'),
        datos.get('legajo'),
        datos.get('lectura_s2p'),
        datos.get('lectura_s3p')
    ))
    conn.commit()
    conn.close()

# ── OBTENER INSPECCIONES ─────────────────────────────
def obtener_inspecciones():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute('SELECT * FROM inspecciones ORDER BY fecha DESC LIMIT 50')
    filas = [dict(f) for f in c.fetchall()]
    conn.close()
    return filas

# ── GUARDAR PIEZA ────────────────────────────────────
def guardar_pieza(datos):
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute('''
        INSERT INTO piezas (nombre, norma, alto_ref, alto_tol, ancho_ref, ancho_tol, largo_ref, largo_tol)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        datos.get('nombre'),
        datos.get('norma'),
        datos.get('alto_ref'),
        datos.get('alto_tol'),
        datos.get('ancho_ref'),
        datos.get('ancho_tol'),
        datos.get('largo_ref'),
        datos.get('largo_tol')
    ))
    conn.commit()
    ultimo_id = c.lastrowid
    conn.close()
    return ultimo_id

# ── OBTENER PIEZAS ───────────────────────────────────
def obtener_piezas():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute('SELECT * FROM piezas ORDER BY nombre')
    filas = [dict(f) for f in c.fetchall()]
    conn.close()
    return filas

# ── GUARDAR CALIBRACION ──────────────────────────────
def guardar_calibracion(datos):
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute('''
        INSERT INTO calibracion (px_por_mm_superior, px_por_mm_lateral, fecha)
        VALUES (?, ?, ?)
    ''', (
        datos.get('px_por_mm_superior'),
        datos.get('px_por_mm_lateral'),
        fecha_arg()
    ))
    conn.commit()
    fila = c.execute('SELECT fecha FROM calibracion WHERE id = ?', (c.lastrowid,)).fetchone()
    conn.close()
    return fila[0] if fila else None

# ── OBTENER ULTIMA CALIBRACION ───────────────────────
def obtener_calibracion():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute('SELECT * FROM calibracion ORDER BY fecha DESC LIMIT 1')
    fila = c.fetchone()
    conn.close()
    return dict(fila) if fila else {}

# ── OBTENER ULTIMAS 5 CALIBRACIONES ─────────────────
def obtener_calibraciones():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute('SELECT id, px_por_mm_superior, px_por_mm_lateral, fecha FROM calibracion ORDER BY fecha DESC LIMIT 5')
    filas = [dict(f) for f in c.fetchall()]
    conn.close()
    return filas
