# Puente principal — Raspberry Pi 4
# Lee el QR de la pieza y las mediciones de la ESP32,
# evalúa tolerancias y manda el resultado al backend Flask
# Requiere: pip install pyserial requests

import sys
import os
import json
import threading
import requests

from receptor_serial import ReceptorSerial

# Agregar la carpeta database/ al path para poder importar BaseDatos
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "database"))
from db import BaseDatos

_URL_BACKEND        = "http://localhost:5000/inspeccion"
_RUTA_CALIBRACION   = os.path.join(os.path.dirname(__file__), "calibracion.json")

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


def cargar_calibracion():
    """
    Lee raspberry/calibracion.json con los valores de referencia del banco de medición.
    Devuelve el dict de calibración o None si el archivo no existe.
    Ejemplo de contenido:
        {"REF_S1": 200, "D_S2_S2p": 150, "D_S3_S3p": 180}
    """
    if not os.path.exists(_RUTA_CALIBRACION):
        print("AVISO: calibracion.json no encontrado. Las dimensiones no se calcularán.")
        return None

    with open(_RUTA_CALIBRACION, "r") as f:
        return json.load(f)


def calcular_dimensiones(lecturas, calibracion):
    """
    Aplica las fórmulas diferenciales para obtener las dimensiones reales de la pieza.
    Las lecturas son distancias brutas en mm desde cada sensor hasta la pieza.

    Fórmulas:
      alto  = REF_S1   - s1          (distancia desde arriba)
      ancho = D_S2_S2p - s2 - s2p    (espacio libre entre sensor izq. y der.)
      largo = D_S3_S3p - s3 - s3p    (espacio libre entre sensor frontal y posterior)
    """
    alto  = round(calibracion["REF_S1"]    - lecturas["s1"], 1)
    ancho = round(calibracion["D_S2_S2p"]  - lecturas["s2"] - lecturas["s2p"], 1)
    largo = round(calibracion["D_S3_S3p"]  - lecturas["s3"] - lecturas["s3p"], 1)

    return {"alto": alto, "ancho": ancho, "largo": largo}


def evaluar_mediciones(dimensiones, pieza):
    """
    Compara las dimensiones calculadas contra las referencias de la pieza.
    Devuelve "APROBADA" o "RECHAZADA".
    El diámetro interior (id_ref) no se evalúa por ahora — el sistema
    diferencial de 5 sensores no lo mide todavía.
    """
    def dentro_de_tolerancia(valor, referencia, tolerancia):
        return (referencia - tolerancia) <= valor <= (referencia + tolerancia)

    # alto → largo de la pieza (sensor S1 mide desde arriba)
    alto_ok = dentro_de_tolerancia(
        dimensiones["alto"], pieza["largo_ref"], pieza["largo_tol"]
    )
    # ancho → diámetro exterior (sensores S2 y S2p miden de costado)
    ancho_ok = dentro_de_tolerancia(
        dimensiones["ancho"], pieza["od_ref"], pieza["od_tol"]
    )

    return "APROBADA" if (alto_ok and ancho_ok) else "RECHAZADA"


def main():
    db = BaseDatos()
    receptor = ReceptorSerial()

    # Cargar la calibración del banco de medición al arrancar
    calibracion = cargar_calibracion()

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

            # Extraer las 5 lecturas brutas del JSON de la ESP32
            lecturas = {
                "s1":  datos.get("s1"),
                "s2":  datos.get("s2"),
                "s2p": datos.get("s2p"),
                "s3":  datos.get("s3"),
                "s3p": datos.get("s3p"),
            }

            # Enviar lecturas brutas al dashboard — falla silenciosamente si el backend no está
            try:
                requests.post("http://localhost:5000/sensores", json={
                    "S1":  lecturas["s1"],
                    "S2":  lecturas["s2"],
                    "S2p": lecturas["s2p"],
                    "S3":  lecturas["s3"],
                    "S3p": lecturas["s3p"],
                }, timeout=1)
            except Exception:
                pass

            # Calcular dimensiones reales si hay calibración disponible
            if calibracion is not None:
                dimensiones = calcular_dimensiones(lecturas, calibracion)
                resultado = evaluar_mediciones(dimensiones, pieza_actual)
            else:
                print("AVISO: sin calibración, no se puede evaluar.")
                dimensiones = {"alto": None, "ancho": None, "largo": None}
                resultado = "RECHAZADA"

            payload = {
                "pieza":     pieza_actual["nombre"],
                "largo":     dimensiones["alto"],
                "od":        dimensiones["ancho"],
                "id":        None,
                "resultado": resultado,
                "s1_raw":    lecturas["s1"],
                "s2_raw":    lecturas["s2"],
                "s2p_raw":   lecturas["s2p"],
                "s3_raw":    lecturas["s3"],
                "s3p_raw":   lecturas["s3p"],
            }

            try:
                requests.post(_URL_BACKEND, json=payload, timeout=3)
            except requests.exceptions.RequestException as e:
                print("Error al enviar al backend: {}".format(e))
                continue

            print("Enviado: {} | alto:{}mm ancho:{}mm | {}".format(
                pieza_actual["nombre"],
                dimensiones["alto"],
                dimensiones["ancho"],
                resultado,
            ))

    except KeyboardInterrupt:
        print("\nInterrumpido por el usuario.")
    finally:
        receptor.cerrar()
        db.cerrar()


if __name__ == "__main__":
    main()
