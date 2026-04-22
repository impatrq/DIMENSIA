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
        """Crea la tabla inspecciones si todavía no existe."""
        self.conexion.execute("""
            CREATE TABLE IF NOT EXISTS inspecciones (
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                fecha     TEXT,
                hora      TEXT,
                aprobada  INTEGER,
                s0        REAL,
                s1        REAL,
                s2        REAL,
                s3        REAL,
                timestamp INTEGER
            )
        """)
        self.conexion.commit()

    def guardar_inspeccion(self, datos):
        """
        Recibe el dict JSON de la ESP32 y guarda una fila en la tabla.
        La fecha y hora las genera la Raspberry Pi al momento de recibir el dato.
        """
        ahora = datetime.now()
        mediciones = datos.get("mediciones", {})

        self.conexion.execute("""
            INSERT INTO inspecciones
                (fecha, hora, aprobada, s0, s1, s2, s3, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            ahora.strftime("%Y-%m-%d"),
            ahora.strftime("%H:%M:%S"),
            1 if datos.get("aprobada") else 0,
            mediciones.get("s0"),
            mediciones.get("s1"),
            mediciones.get("s2"),
            mediciones.get("s3"),
            datos.get("timestamp"),
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

    # Insertar 3 filas de ejemplo
    ejemplos = [
        {
            "aprobada": True,
            "mediciones": {"s0": 150, "s1": 200, "s2": 100, "s3": 300},
            "timestamp": 12000,
        },
        {
            "aprobada": False,
            "mediciones": {"s0": 148, "s1": 201, "s2": 99, "s3": 312},
            "timestamp": 12500,
        },
        {
            "aprobada": True,
            "mediciones": {"s0": 151, "s1": 199, "s2": 101, "s3": 299},
            "timestamp": 13000,
        },
    ]

    for datos in ejemplos:
        db.guardar_inspeccion(datos)

    print("3 inspecciones guardadas. Últimas filas:\n")

    for fila in db.obtener_ultimas():
        estado = "APROBADA" if fila["aprobada"] else "RECHAZADA"
        print("{} {} {} | s0:{} s1:{} s2:{} s3:{} | ts:{}".format(
            fila["id"], fila["fecha"], fila["hora"],
            fila["s0"], fila["s1"], fila["s2"], fila["s3"],
            fila["timestamp"],
        ))

    db.cerrar()
