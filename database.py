import sqlite3

DB = 'dimensia.db'

# ── INICIALIZAR BASE DE DATOS ────────────────────────
def init_db():
    conn = sqlite3.connect(DB)
    c = conn.cursor()

    # Tabla de tipos de piezas
    c.execute('''
        CREATE TABLE IF NOT EXISTS piezas (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre    TEXT NOT NULL,
            norma     TEXT,
            od_ref    REAL,
            od_tol    REAL,
            id_ref    REAL,
            id_tol    REAL,
            largo_ref REAL,
            largo_tol REAL
        )
    ''')

    # Tabla de inspecciones
    c.execute('''
        CREATE TABLE IF NOT EXISTS inspecciones (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            pieza       TEXT NOT NULL,
            alto        REAL,
            ancho       REAL,
            largo       REAL,
            resultado   TEXT,
            fecha       TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            operario    TEXT,
            legajo      TEXT,
            lectura_s2p REAL,
            lectura_s3p REAL
        )
    ''')

    # Tabla de calibracion de camaras (factor px/mm)
    c.execute('''
        CREATE TABLE IF NOT EXISTS calibracion (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            factor_superior  REAL,
            factor_lateral   REAL,
            fecha            TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Cargar piezas de ejemplo si la tabla esta vacia
    c.execute('SELECT COUNT(*) FROM piezas')
    if c.fetchone()[0] == 0:
        piezas_ejemplo = [
            ('Niple NPT 1/2"', 'ASME B16.11', 21.3, 0.5, 14.0, 0.5, 58.0, 1.0),
            ('Union NPT 3/4"', 'ASME B16.11', 26.7, 0.5, 18.0, 0.5, 65.0, 1.0),
            ('Brida DN25',     'DIN 2999',    25.8, 0.5, None, None, 42.0, 1.0),
            ('Codo 90 1/2"',  'ASME B16.11', 21.3, 0.5, None, None, 38.0, 1.0),
        ]
        c.executemany(
            'INSERT INTO piezas (nombre, norma, od_ref, od_tol, id_ref, id_tol, largo_ref, largo_tol) VALUES (?,?,?,?,?,?,?,?)',
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
          (pieza, alto, ancho, largo, resultado, operario, legajo, lectura_s2p, lectura_s3p)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        datos.get('pieza'),
        datos.get('alto'),
        datos.get('ancho'),
        datos.get('largo'),
        datos.get('resultado'),
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
        INSERT INTO piezas (nombre, norma, od_ref, od_tol, id_ref, id_tol, largo_ref, largo_tol)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        datos.get('nombre'),
        datos.get('norma'),
        datos.get('od_ref'),
        datos.get('od_tol'),
        datos.get('id_ref'),
        datos.get('id_tol'),
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
        INSERT INTO calibracion (factor_superior, factor_lateral)
        VALUES (?, ?)
    ''', (
        datos.get('factor_superior'),
        datos.get('factor_lateral')
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
