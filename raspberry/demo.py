# Script de demostración — DIMENSIA
# Simula una sesión completa de inspección sin hardware.
# Útil para presentaciones y pruebas del backend/dashboard.

import requests
import time
import random
import json
import os
import sys

# Agregar la carpeta database/ al path para poder importar BaseDatos
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "database"))
from db import BaseDatos

_URL_BACKEND = "http://localhost:5000"

# ─── Piezas de ejemplo ────────────────────────────────────────────────────────

PIEZAS = [
    {
        "nombre":    "Niple NPT 1/2\"",
        "norma":     "ASME B16.11",
        "largo_ref": 58,    "largo_tol": 1,
        "od_ref":    21.3,  "od_tol":    0.5,
        "id_ref":    None,  "id_tol":    None,
    },
    {
        "nombre":    "Union NPT 3/4\"",
        "norma":     "ASME B16.11",
        "largo_ref": 65,    "largo_tol": 1,
        "od_ref":    26.7,  "od_tol":    0.5,
        "id_ref":    None,  "id_tol":    None,
    },
    {
        "nombre":    "Brida DN25",
        "norma":     "DIN 2999",
        "largo_ref": 42,    "largo_tol": 1,
        "od_ref":    25.8,  "od_tol":    0.5,
        "id_ref":    None,  "id_tol":    None,
    },
]


def generar_medicion(pieza, forzar_rechazo=False):
    """
    Genera dimensiones simuladas para una pieza.
    - forzar_rechazo=False: valores dentro de tolerancia con variación de ±0.5mm
    - forzar_rechazo=True:  al menos una dimensión con desvío de 2 a 3mm
    """
    if not forzar_rechazo:
        # Variación pequeña dentro de tolerancia
        alto  = round(pieza["largo_ref"] + random.uniform(-0.5, 0.5), 1)
        ancho = round(pieza["od_ref"]    + random.uniform(-0.5, 0.5), 1)
        largo = round(pieza["largo_ref"] + random.uniform(-0.5, 0.5), 1)
    else:
        # Elegir al azar qué dimensión va a fallar (puede ser más de una)
        desvio = random.uniform(2.0, 3.0) * random.choice([-1, 1])
        alto  = round(pieza["largo_ref"] + (desvio if random.random() < 0.6 else random.uniform(-0.5, 0.5)), 1)
        ancho = round(pieza["od_ref"]    + (desvio if random.random() < 0.6 else random.uniform(-0.5, 0.5)), 1)
        largo = round(pieza["largo_ref"] + random.uniform(-0.5, 0.5), 1)

    return {"alto": alto, "ancho": ancho, "largo": largo}


def evaluar(dimensiones, pieza):
    """Compara las dimensiones contra tolerancias. Devuelve 'APROBADA' o 'RECHAZADA'."""
    def ok(valor, ref, tol):
        return (ref - tol) <= valor <= (ref + tol)

    alto_ok  = ok(dimensiones["alto"],  pieza["largo_ref"], pieza["largo_tol"])
    ancho_ok = ok(dimensiones["ancho"], pieza["od_ref"],    pieza["od_tol"])

    return "APROBADA" if (alto_ok and ancho_ok) else "RECHAZADA"


def simular_sesion(n_inspecciones=10):
    """
    Simula una sesión completa: elige una pieza, genera inspecciones,
    las envía al backend y muestra el resultado en tiempo real.
    """
    print("=" * 55)
    print("  DIMENSIA — Simulacion de sesion")
    print("=" * 55)

    # Elegir una pieza al azar para toda la sesión
    pieza = random.choice(PIEZAS)
    print("Pieza cargada: {} ({})".format(pieza["nombre"], pieza["norma"]))
    print("Referencia — largo: {}mm  OD: {}mm".format(pieza["largo_ref"], pieza["od_ref"]))
    print("-" * 55)

    aprobadas  = 0
    rechazadas = 0

    for i in range(1, n_inspecciones + 1):
        # 80% de probabilidad de pieza aprobada
        forzar_rechazo = random.random() < 0.20

        dimensiones = generar_medicion(pieza, forzar_rechazo)
        resultado   = evaluar(dimensiones, pieza)

        if resultado == "APROBADA":
            aprobadas += 1
        else:
            rechazadas += 1

        payload = {
            "pieza":     pieza["nombre"],
            "largo":     dimensiones["alto"],
            "od":        dimensiones["ancho"],
            "id":        None,
            "resultado": resultado,
            "operario":  "Demo",
            "legajo":    "000",
            "s1_raw":    None,
            "s2_raw":    None,
            "s2p_raw":   None,
            "s3_raw":    None,
            "s3p_raw":   None,
        }

        # Enviar al backend — si no está disponible, continuar igual
        try:
            requests.post(_URL_BACKEND + "/inspeccion", json=payload, timeout=3)
        except Exception:
            pass

        print("#{:02d}  {}  | alto:{:.1f}mm  ancho:{:.1f}mm  largo:{:.1f}mm".format(
            i, resultado,
            dimensiones["alto"], dimensiones["ancho"], dimensiones["largo"],
        ))

        time.sleep(1)

    # Resumen final
    tasa = round(rechazadas / n_inspecciones * 100)
    print("-" * 55)
    print("Total: {}  |  Aprobadas: {}  |  Rechazadas: {}  |  Tasa de rechazo: {}%".format(
        n_inspecciones, aprobadas, rechazadas, tasa,
    ))


if __name__ == "__main__":
    simular_sesion(10)
