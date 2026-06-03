# Inicialización de la base de datos — DIMENSIA
# Carga las piezas de ejemplo la primera vez que se configura el sistema.
# Si ya hay datos en la tabla piezas, no hace nada.

import sys
import os

# Agregar la carpeta database/ al path para poder importar BaseDatos
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "database"))
from db import BaseDatos

# ─── Piezas de ejemplo ────────────────────────────────────────────────────────

PIEZAS_EJEMPLO = [
    {
        "nombre":    "Niple NPT 1/2\"",
        "norma":     "ASME B16.11",
        "od_ref":    21.3,  "od_tol":    0.5,
        "id_ref":    None,  "id_tol":    None,
        "largo_ref": 58.0,  "largo_tol": 1.0,
    },
    {
        "nombre":    "Union NPT 3/4\"",
        "norma":     "ASME B16.11",
        "od_ref":    26.7,  "od_tol":    0.5,
        "id_ref":    None,  "id_tol":    None,
        "largo_ref": 65.0,  "largo_tol": 1.0,
    },
    {
        "nombre":    "Brida DN25",
        "norma":     "DIN 2999",
        "od_ref":    25.8,  "od_tol":    0.5,
        "id_ref":    None,  "id_tol":    None,
        "largo_ref": 42.0,  "largo_tol": 1.0,
    },
    {
        "nombre":    "Codo 90 1/2\"",
        "norma":     "ASME B16.11",
        "od_ref":    21.3,  "od_tol":    0.5,
        "id_ref":    None,  "id_tol":    None,
        "largo_ref": 38.0,  "largo_tol": 1.0,
    },
]


def inicializar(db):
    """
    Verifica si ya hay piezas cargadas.
    Si hay, no hace nada. Si no hay, inserta las piezas de ejemplo.
    """
    cursor = db.conexion.execute("SELECT COUNT(*) FROM piezas")
    cantidad_existente = cursor.fetchone()[0]

    if cantidad_existente > 0:
        print("La base de datos ya tiene {} pieza(s). No se cargaron nuevos datos.".format(
            cantidad_existente
        ))
        return

    # Insertar todas las piezas de ejemplo
    for pieza in PIEZAS_EJEMPLO:
        db.conexion.execute("""
            INSERT INTO piezas (nombre, norma, od_ref, od_tol, id_ref, id_tol, largo_ref, largo_tol)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            pieza["nombre"],
            pieza["norma"],
            pieza["od_ref"],
            pieza["od_tol"],
            pieza["id_ref"],
            pieza["id_tol"],
            pieza["largo_ref"],
            pieza["largo_tol"],
        ))
    db.conexion.commit()

    print("{} piezas cargadas en la base de datos:".format(len(PIEZAS_EJEMPLO)))
    for pieza in PIEZAS_EJEMPLO:
        print("  - {} ({})".format(pieza["nombre"], pieza["norma"]))


if __name__ == "__main__":
    db = BaseDatos()
    inicializar(db)
    db.cerrar()
    print("Listo. Podés arrancar el sistema.")
