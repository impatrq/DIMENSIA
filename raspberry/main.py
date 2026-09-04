# Puente principal — Raspberry Pi 4
# Espera el evento de la ESP32 por Serial, ejecuta el ciclo de captura
# con las dos cámaras, consolida medidas y manda el resultado al backend Flask.
# La pieza se selecciona en la pantalla táctil antes del ciclo; ya no hay QR.
# Requiere: pip install pyserial requests opencv-python numpy

import sys
import os
import json
import time
import requests

from receptor_serial import ReceptorSerial
from camaras import GestorCamaras
from procesamiento import ProcesadorImagenes

# Agregar la carpeta database/ al path para poder importar BaseDatos
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "database"))
from db import BaseDatos

_URL_BACKEND = "http://localhost:5000"

# Tiempo de giro que la Raspberry Pi le ordena a la ESP32 por cada ángulo.
# Valor de ejemplo — calibrar con el hardware real usando servo_plato.calibrar_paso().
TIEMPO_GIRO_MS = 500


def _enviar_serial(receptor, datos):
    """
    Escribe un dict como JSON en el puerto Serial hacia la ESP32.
    Usa la conexión subyacente del ReceptorSerial para no duplicar el objeto.
    """
    linea = (json.dumps(datos) + "\n").encode("utf-8")
    receptor.conexion.write(linea)


def obtener_operario():
    """
    Consulta al backend cuál es el operario que inició sesión.
    Si el backend no responde, devuelve un valor por defecto sin romper el loop.
    """
    try:
        respuesta = requests.get(_URL_BACKEND + "/operario_activo", timeout=2)
        return respuesta.json()
    except Exception:
        return {"operario": "Sin identificar", "legajo": ""}


def obtener_pieza_activa():
    """
    Consulta al backend la pieza que el operario seleccionó en la pantalla táctil.
    Devuelve el dict de la pieza o None si no hay ninguna seleccionada.
    """
    try:
        respuesta = requests.get(_URL_BACKEND + "/pieza_activa", timeout=2)
        datos = respuesta.json()
        # El endpoint devuelve {} si no hay pieza seleccionada
        return datos if datos else None
    except Exception:
        return None


def ejecutar_ciclo_inspeccion(pieza, camaras, procesador, receptor):
    """
    Ciclo completo de inspección por visión:
    1. Para cada uno de los 8 ángulos:
       - Manda comando de giro a la ESP32 por Serial
       - Espera confirmación de la ESP32 por Serial
       - Captura imágenes con las dos cámaras
       - Procesa las imágenes para extraer dimensiones
    2. Promedia las medidas de las 8 capturas
    3. Evalúa contra tolerancias
    4. Manda el resultado final a la ESP32 por Serial
    5. Devuelve el dict con medidas y resultado
    """
    acum_diametro = []
    acum_largo    = []
    acum_alto     = []

    for n_angulo in range(8):
        angulo_grados = n_angulo * 45

        # Mandar comando de giro a la ESP32 por Serial
        _enviar_serial(receptor, {"comando": "girar", "tiempo_ms": TIEMPO_GIRO_MS})

        # Esperar la confirmación antes de capturar — el plato tiene que estar quieto
        while True:
            confirmacion = receptor.leer_siguiente()
            if confirmacion is None:
                continue
            if confirmacion.get("evento") == "giro_completado":
                break

        # Capturar con las dos cámaras ahora que el plato está en posición
        capturas = camaras.capturar(angulo_grados)

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
            angulo_grados,
            medidas["diametro_exterior_mm"],
            medidas["largo_mm"],
            medidas["alto_mm"],
        ))

        # Notificar al dashboard el progreso del plato (informativo, no bloquea)
        try:
            requests.post(_URL_BACKEND + "/plato", timeout=1, json={
                "girando": False,
                "angulo_actual": angulo_grados,
                "capturas_completadas": n_angulo + 1,
            })
        except Exception:
            pass

        try:
            requests.post(_URL_BACKEND + "/captura", timeout=1, json={
                "total": n_angulo + 1,
            })
        except Exception:
            pass

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

    # Mandar el resultado a la ESP32 para que clasifique la pieza (paleta + brazo)
    _enviar_serial(receptor, {"resultado": resultado})

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

    print("Sistema listo. Esperando señal de la ESP32...\n")

    try:
        while True:
            datos = receptor.leer_siguiente()

            if datos is None:
                continue

            # Esperar el evento que indica que la pieza está en posición de medición.
            # Lo dispara la ESP32 cuando el elevador llega arriba.
            if datos.get("evento") != "listo_para_medir":
                continue

            # Leer la pieza que el operario seleccionó en la pantalla táctil
            pieza = obtener_pieza_activa()
            if pieza is None:
                print("Sin pieza seleccionada en la pantalla. Esperando...")
                continue

            print("Pieza lista. Iniciando ciclo de inspección...")
            print("Pieza: {} | {}".format(pieza.get("nombre", "?"), pieza.get("norma", "?")))

            # Ejecutar el ciclo completo de captura, procesamiento y clasificación
            resultado_ciclo = ejecutar_ciclo_inspeccion(pieza, camaras, procesador, receptor)

            operario_data = obtener_operario()

            payload = {
                "pieza":     pieza["nombre"],
                "largo":     resultado_ciclo["largo_mm"],
                "od":        resultado_ciclo["diametro_exterior_mm"],
                "id":        None,
                "resultado": resultado_ciclo["resultado"],
                "operario":  operario_data["operario"],
                "legajo":    operario_data["legajo"],
            }

            try:
                requests.post(_URL_BACKEND + "/inspeccion", json=payload, timeout=3)
            except requests.exceptions.RequestException as e:
                print("Error al enviar al backend: {}".format(e))

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
