# Puente principal — Raspberry Pi 4
# Lee el QR de la pieza y las mediciones de la ESP32,
# evalúa tolerancias y manda el resultado al backend Flask
# Requiere: pip install pyserial requests

import sys
import os
import threading
import requests

from receptor_serial import ReceptorSerial

# Agregar la carpeta database/ al path para poder importar BaseDatos
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "database"))
from db import BaseDatos

_URL_BACKEND = "http://localhost:5000/inspeccion"

# Pieza actualmente cargada por el lector QR.
# Es None si todavía no se escaneó ninguna.
pieza_actual = None


def leer_qr_loop(db):
    """
    Corre en un hilo separado. Escucha el lector QR USB,
    que se comporta como un teclado y manda texto + Enter.
    Cuando detecta un QR válido de DIMENSIA, carga la pieza desde la DB.
    """
    global pieza_actual

    while True:
        try:
            linea = input().strip()
        except EOFError:
            # Puede pasar si stdin se cierra; simplemente ignorar
            continue

        if not linea.startswith("DIMENSIA|"):
            continue

        # Formato esperado: DIMENSIA|{id}|{nombre}|{norma}
        partes = linea.split("|")
        if len(partes) < 2:
            print("QR inválido: {}".format(linea))
            continue

        id_pieza = partes[1]

        cursor = db.conexion.execute(
            "SELECT * FROM piezas WHERE id = ?", (id_pieza,)
        )
        fila = cursor.fetchone()

        if fila is None:
            print("Pieza no encontrada en DB: {}".format(id_pieza))
            pieza_actual = None
        else:
            pieza_actual = dict(fila)
            print('Pieza cargada: {} ({})'.format(
                pieza_actual.get("nombre", "?"),
                pieza_actual.get("norma", "?"),
            ))


def evaluar_mediciones(mediciones, pieza):
    """
    Compara las mediciones de los 3 sensores contra las referencias
    y tolerancias de la pieza. Devuelve "APROBADA" o "RECHAZADA".
    Si id_ref es None, se omite la comparación de diámetro interior
    (aplica a piezas sin agujero como bridas y codos).
    """
    def dentro_de_tolerancia(valor, referencia, tolerancia):
        return (referencia - tolerancia) <= valor <= (referencia + tolerancia)

    largo_ok = dentro_de_tolerancia(
        mediciones["s0"], pieza["largo_ref"], pieza["largo_tol"]
    )
    od_ok = dentro_de_tolerancia(
        mediciones["s1"], pieza["od_ref"], pieza["od_tol"]
    )

    # El diámetro interior es opcional — si no tiene referencia, se ignora
    if pieza["id_ref"] is not None:
        id_ok = dentro_de_tolerancia(
            mediciones["s2"], pieza["id_ref"], pieza["id_tol"]
        )
    else:
        id_ok = True

    return "APROBADA" if (largo_ok and od_ok and id_ok) else "RECHAZADA"


def main():
    db = BaseDatos()
    receptor = ReceptorSerial()

    # El hilo del QR corre como daemon para que muera solo cuando termina el programa
    hilo_qr = threading.Thread(target=leer_qr_loop, args=(db,), daemon=True)
    hilo_qr.start()

    print("Sistema listo. Esperando QR y mediciones...\n")

    try:
        while True:
            datos = receptor.leer_siguiente()

            if datos is None:
                continue

            # Sin pieza escaneada no tiene sentido evaluar ni guardar nada
            if pieza_actual is None:
                print("Esperando QR...")
                continue

            mediciones = {
                "s0": datos.get("s0"),
                "s1": datos.get("s1"),
                "s2": datos.get("s2"),
            }

            resultado = evaluar_mediciones(mediciones, pieza_actual)

            payload = {
                "pieza":     pieza_actual["nombre"],
                "largo":     mediciones["s0"],
                "od":        mediciones["s1"],
                "id":        mediciones["s2"],
                "resultado": resultado,
            }

            try:
                requests.post(_URL_BACKEND, json=payload, timeout=3)
            except requests.exceptions.RequestException as e:
                print("Error al enviar al backend: {}".format(e))
                continue

            print("Enviado: {} | largo:{}mm od:{}mm id:{}mm | {}".format(
                pieza_actual["nombre"],
                mediciones["s0"],
                mediciones["s1"],
                mediciones["s2"],
                resultado,
            ))

    except KeyboardInterrupt:
        print("\nInterrumpido por el usuario.")
    finally:
        receptor.cerrar()
        db.cerrar()


if __name__ == "__main__":
    main()
