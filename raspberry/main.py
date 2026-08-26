# Puente principal — Raspberry Pi 4
# Lee el QR de la pieza, recibe el evento de la ESP32, dispara el ciclo de
# captura con las dos cámaras, consolida medidas y manda el resultado al backend Flask
# Requiere: pip install pyserial requests opencv-python numpy

import sys
import os
import json
import threading
import time
import requests

from receptor_serial import ReceptorSerial
from camaras import GestorCamaras
from procesamiento import ProcesadorImagenes

# Agregar la carpeta database/ al path para poder importar BaseDatos
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "database"))
from db import BaseDatos

_URL_BACKEND      = "http://localhost:5000/inspeccion"
_RUTA_CALIBRACION = os.path.join(os.path.dirname(__file__), "calibracion.json")
_ANGULOS          = [0, 45, 90, 135, 180, 225, 270, 315]

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
    """
    if not os.path.exists(_RUTA_CALIBRACION):
        print("AVISO: calibracion.json no encontrado. Las dimensiones no se calcularán.")
        return None

    with open(_RUTA_CALIBRACION, "r") as f:
        return json.load(f)


def obtener_operario():
    """
    Consulta al backend cuál es el operario que inició sesión.
    Si el backend no responde, devuelve un valor por defecto sin romper el loop.
    """
    try:
        respuesta = requests.get("http://localhost:5000/operario_activo", timeout=2)
        return respuesta.json()
    except Exception:
        return {"operario": "Sin identificar", "legajo": ""}


def ejecutar_ciclo_inspeccion(pieza, camaras, procesador):
    """
    Ciclo completo de inspección por visión:
    1. Gira el plato a cada ángulo (8 posiciones de 45° en 45°)
    2. Captura imagen con las dos cámaras
    3. Procesa las imágenes para extraer dimensiones
    4. Promedia las medidas de las 8 capturas
    5. Evalúa contra tolerancias y devuelve el resultado
    """
    acum_diametro = []
    acum_largo    = []
    acum_alto     = []

    for angulo in _ANGULOS:
        # Indicar al backend (que controla el motor) que gire al siguiente ángulo
        try:
            requests.post("http://localhost:5000/angulo", json={"angulo": angulo}, timeout=3)
        except Exception:
            print("Aviso: no se pudo enviar ángulo {} al backend.".format(angulo))

        # Esperar a que el plato giratorio se estabilice
        time.sleep(1)

        # Capturar con las dos cámaras
        capturas = camaras.capturar(angulo)

        # Procesar las imágenes y obtener dimensiones para este ángulo
        medidas = procesador.procesar_ciclo_completo(capturas)

        # Acumular solo si el procesamiento devolvió valores válidos
        if medidas["diametro_exterior_mm"] is not None:
            acum_diametro.append(medidas["diametro_exterior_mm"])
        if medidas["largo_mm"] is not None:
            acum_largo.append(medidas["largo_mm"])
        if medidas["alto_mm"] is not None:
            acum_alto.append(medidas["alto_mm"])

        print("  Ángulo {}° → OD: {}mm  largo: {}mm  alto: {}mm".format(
            angulo,
            medidas["diametro_exterior_mm"],
            medidas["largo_mm"],
            medidas["alto_mm"],
        ))

    # Calcular el promedio de cada medida a partir de las 8 capturas
    od_prom    = round(sum(acum_diametro) / len(acum_diametro), 1) if acum_diametro else None
    largo_prom = round(sum(acum_largo)    / len(acum_largo),    1) if acum_largo    else None
    alto_prom  = round(sum(acum_alto)     / len(acum_alto),     1) if acum_alto     else None

    # Evaluar las medidas promedio contra las tolerancias de la pieza
    def dentro_de_tolerancia(valor, ref, tol):
        if valor is None:
            return False
        return (ref - tol) <= valor <= (ref + tol)

    od_ok    = dentro_de_tolerancia(od_prom,    pieza["od_ref"],    pieza["od_tol"])
    largo_ok = dentro_de_tolerancia(largo_prom, pieza["largo_ref"], pieza["largo_tol"])

    resultado = "APROBADA" if (od_ok and largo_ok) else "RECHAZADA"

    return {
        "diametro_exterior_mm": od_prom,
        "largo_mm":             largo_prom,
        "alto_mm":              alto_prom,
        "resultado":            resultado,
    }


def main():
    db         = BaseDatos()
    receptor   = ReceptorSerial()
    camaras    = GestorCamaras()
    procesador = ProcesadorImagenes()

    # Cargar la calibración de sensores al arrancar
    calibracion = cargar_calibracion()

    # El hilo del QR corre como daemon para que muera solo cuando termina el programa
    hilo_qr = threading.Thread(target=leer_qr_loop, args=(db,), daemon=True)
    hilo_qr.start()

    print("Sistema listo. Esperando QR y evento de pieza...\n")

    try:
        while True:
            datos = receptor.leer_siguiente()

            if datos is None:
                continue

            # Ignorar cualquier mensaje que no sea el evento de pieza lista
            if datos.get("evento") != "pieza_lista":
                continue

            # Sin pieza escaneada no tiene sentido iniciar la inspección
            if pieza_actual is None:
                print("Esperando QR...")
                continue

            print("Pieza lista detectada. Iniciando ciclo de inspección...")
            print("Pieza: {} | {}".format(
                pieza_actual["nombre"], pieza_actual["norma"]
            ))

            # Ejecutar el ciclo completo de captura y procesamiento
            resultado_ciclo = ejecutar_ciclo_inspeccion(pieza_actual, camaras, procesador)

            operario_data = obtener_operario()

            payload = {
                "pieza":     pieza_actual["nombre"],
                "largo":     resultado_ciclo["largo_mm"],
                "od":        resultado_ciclo["diametro_exterior_mm"],
                "id":        None,
                "resultado": resultado_ciclo["resultado"],
                "operario":  operario_data["operario"],
                "legajo":    operario_data["legajo"],
                "s1_raw":    None,
                "s2_raw":    None,
                "s2p_raw":   None,
                "s3_raw":    None,
                "s3p_raw":   None,
            }

            try:
                requests.post(_URL_BACKEND, json=payload, timeout=3)
            except requests.exceptions.RequestException as e:
                print("Error al enviar al backend: {}".format(e))
                continue

            print("Enviado: {} | OD:{}mm largo:{}mm alto:{}mm | operario: {}".format(
                resultado_ciclo["resultado"],
                resultado_ciclo["diametro_exterior_mm"],
                resultado_ciclo["largo_mm"],
                resultado_ciclo["alto_mm"],
                operario_data["operario"],
            ))

    except KeyboardInterrupt:
        print("\nInterrumpido por el usuario.")
    finally:
        receptor.cerrar()
        camaras.cerrar()
        db.cerrar()


if __name__ == "__main__":
    main()
