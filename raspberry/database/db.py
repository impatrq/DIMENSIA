# Base de datos SQLite — Raspberry Pi 4
# Guarda cada inspección recibida de la ESP32

import sqlite3
import os
from datetime import datetime

# Ruta de la base de datos, relativa a este archivo
_RUTA_DB = os.path.join(os.path.dirname(__file__), "dimensia.db")


class BaseDatos:
    """Maneja la conexión y las operaciones sobre la base de datos SQLite."""

    def __init__(self):
        self.conexion = sqlite3.connect(_RUTA_DB)
        # Devolver filas como diccionarios en lugar de tuplas
        self.conexion.row_factory = sqlite3.Row
        self.crear_tablas()

    def crear_tablas(self):
        """Crea las tablas inspecciones y calibracion si todavía no existen."""
        self.conexion.execute("""
            CREATE TABLE IF NOT EXISTS inspecciones (
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                fecha     TEXT,
                hora      TEXT,
                aprobada  INTEGER,
                alto      REAL,     -- dimensión calculada: altura de la pieza
                ancho     REAL,     -- dimensión calculada: diámetro exterior
                largo     REAL,     -- dimensión calculada: largo de la pieza
                s1_raw    REAL,     -- lectura bruta sensor alto
                s2_raw    REAL,     -- lectura bruta sensor ancho izquierdo
                s2p_raw   REAL,     -- lectura bruta sensor ancho derecho
                s3_raw    REAL,     -- lectura bruta sensor largo frontal
                s3p_raw   REAL,     -- lectura bruta sensor largo posterior
                timestamp INTEGER
            )
        """)
        self.conexion.execute("""
            CREATE TABLE IF NOT EXISTS calibracion (
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                fecha     TEXT,
                hora      TEXT,
                ref_s1    REAL,     -- distancia de referencia sensor alto (banco vacío)
                d_s2_s2p  REAL,     -- suma de referencia sensores ancho (banco vacío)
                d_s3_s3p  REAL      -- suma de referencia sensores largo (banco vacío)
            )
        """)
        self.conexion.commit()

    def guardar_inspeccion(self, datos):
        """
        Recibe el payload del backend y guarda una fila en la tabla.
        La fecha y hora las genera la Raspberry Pi al momento de recibir el dato.
        """
        ahora = datetime.now()

        self.conexion.execute("""
            INSERT INTO inspecciones
                (fecha, hora, aprobada, alto, ancho, largo,
                 s1_raw, s2_raw, s2p_raw, s3_raw, s3p_raw, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            ahora.strftime("%Y-%m-%d"),
            ahora.strftime("%H:%M:%S"),
            1 if datos.get("aprobada") else 0,
            datos.get("alto"),
            datos.get("ancho"),
            datos.get("largo"),
            datos.get("s1_raw"),
            datos.get("s2_raw"),
            datos.get("s2p_raw"),
            datos.get("s3_raw"),
            datos.get("s3p_raw"),
            datos.get("timestamp"),
        ))
        self.conexion.commit()

    def guardar_calibracion(self, calibracion):
        """
        Guarda una fila en la tabla calibracion con los valores del banco vacío.
        Recibe el dict {"REF_S1": ..., "D_S2_S2p": ..., "D_S3_S3p": ...}.
        """
        ahora = datetime.now()

        self.conexion.execute("""
            INSERT INTO calibracion (fecha, hora, ref_s1, d_s2_s2p, d_s3_s3p)
            VALUES (?, ?, ?, ?, ?)
        """, (
            ahora.strftime("%Y-%m-%d"),
            ahora.strftime("%H:%M:%S"),
            calibracion.get("REF_S1"),
            calibracion.get("D_S2_S2p"),
            calibracion.get("D_S3_S3p"),
        ))
        self.conexion.commit()

    def obtener_ultimas(self, cantidad=50):
        """Devuelve las últimas N inspecciones, de más nueva a más vieja."""
        cursor = self.conexion.execute("""
            SELECT * FROM inspecciones
            ORDER BY id DESC
            LIMIT ?
        """, (cantidad,))
        return [dict(fila) for fila in cursor.fetchall()]

    def cerrar(self):
        """Cierra la conexión a la base de datos."""
        self.conexion.close()


# ─── Prueba rápida ────────────────────────────────────────────────────────────

if __name__ == "__main__":
    db = BaseDatos()

    # Insertar una calibración de ejemplo
    db.guardar_calibracion({"REF_S1": 198.3, "D_S2_S2p": 149.7, "D_S3_S3p": 181.2})
    print("Calibración guardada.")

    # Insertar 3 inspecciones de ejemplo con los nuevos campos
    ejemplos = [
        {
            "aprobada": True,
            "alto": 48.5, "ancho": 25.1, "largo": 60.0,
            "s1_raw": 149, "s2_raw": 62, "s2p_raw": 62, "s3_raw": 60, "s3p_raw": 61,
            "timestamp": 12000,
        },
        {
            "aprobada": False,
            "alto": 51.2, "ancho": 24.8, "largo": 63.4,
            "s1_raw": 147, "s2_raw": 63, "s2p_raw": 62, "s3_raw": 58, "s3p_raw": 60,
            "timestamp": 12500,
        },
        {
            "aprobada": True,
            "alto": 49.0, "ancho": 25.0, "largo": 60.3,
            "s1_raw": 149, "s2_raw": 62, "s2p_raw": 63, "s3_raw": 61, "s3p_raw": 60,
            "timestamp": 13000,
        },
    ]

    for datos in ejemplos:
        db.guardar_inspeccion(datos)

    print("3 inspecciones guardadas. Últimas filas:\n")

    for fila in db.obtener_ultimas():
        estado = "APROBADA" if fila["aprobada"] else "RECHAZADA"
        print("{} {} {} | {} | alto:{} ancho:{} largo:{} | ts:{}".format(
            fila["id"], fila["fecha"], fila["hora"], estado,
            fila["alto"], fila["ancho"], fila["largo"],
            fila["timestamp"],
        ))

    db.cerrar()
