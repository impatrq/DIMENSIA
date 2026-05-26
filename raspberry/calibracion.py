# Rutina de calibración del sistema DIMENSIA
# Se corre UNA SOLA VEZ al montar el equipo, con la cinta vacía y sin piezas.
# Mide las distancias de referencia del banco vacío para que las fórmulas
# diferenciales puedan calcular correctamente las dimensiones de las piezas.

import json
import os
from receptor_serial import ReceptorSerial

_RUTA_CALIBRACION = os.path.join(os.path.dirname(__file__), "calibracion.json")
_MUESTRAS = 10


def calibrar(receptor):
    """
    Guía al operario a través de la calibración del banco vacío.
    Lee 10 muestras de la ESP32, promedia y guarda los valores en calibracion.json.

    Valores que se calibran:
      REF_S1   — distancia desde el sensor S1 (alto) hasta la cinta vacía.
                 Con una pieza: alto = REF_S1 - s1
      D_S2_S2p — suma de distancias S2 + S2p con el banco vacío.
                 Representa el ancho total del canal sin pieza.
                 Con una pieza: ancho = D_S2_S2p - s2 - s2p
      D_S3_S3p — suma de distancias S3 + S3p con el banco vacío.
                 Representa el largo total del canal sin pieza.
                 Con una pieza: largo = D_S3_S3p - s3 - s3p
    """
    print("=" * 50)
    print("  CALIBRACIÓN DEL SISTEMA DIMENSIA")
    print("=" * 50)
    print("Asegurate que la cinta esté VACÍA y los sensores libres")
    input("Presioná ENTER cuando esté listo...")
    print("\nRecolectando {} muestras...".format(_MUESTRAS))

    # Acumuladores para el promedio
    acumuladores = {"s1": 0, "s2": 0, "s2p": 0, "s3": 0, "s3p": 0}
    muestras_leidas = 0

    while muestras_leidas < _MUESTRAS:
        datos = receptor.leer_siguiente()

        # Ignorar líneas no válidas (debug prints de la ESP32, etc.)
        if datos is None:
            continue

        for clave in acumuladores:
            acumuladores[clave] += datos.get(clave, 0)

        muestras_leidas += 1
        print("  Muestra {}/{} — s1:{} s2:{} s2p:{} s3:{} s3p:{}".format(
            muestras_leidas, _MUESTRAS,
            datos.get("s1"), datos.get("s2"), datos.get("s2p"),
            datos.get("s3"), datos.get("s3p"),
        ))

    # Calcular promedios — D_S2_S2p y D_S3_S3p son sumas de a pares
    ref_s1    = round(acumuladores["s1"] / _MUESTRAS, 1)
    d_s2_s2p  = round((acumuladores["s2"] + acumuladores["s2p"]) / _MUESTRAS, 1)
    d_s3_s3p  = round((acumuladores["s3"] + acumuladores["s3p"]) / _MUESTRAS, 1)

    calibracion = {
        "REF_S1":   ref_s1,
        "D_S2_S2p": d_s2_s2p,
        "D_S3_S3p": d_s3_s3p,
    }

    # Guardar en calibracion.json
    with open(_RUTA_CALIBRACION, "w") as f:
        json.dump(calibracion, f, indent=2)

    print("\nCalibración guardada en calibracion.json:")
    print("  REF_S1   = {} mm  (referencia de alto)".format(ref_s1))
    print("  D_S2_S2p = {} mm  (referencia de ancho)".format(d_s2_s2p))
    print("  D_S3_S3p = {} mm  (referencia de largo)".format(d_s3_s3p))
    print("\nListo. El sistema está calibrado.")

    return calibracion


if __name__ == "__main__":
    receptor = ReceptorSerial()
    try:
        calibrar(receptor)
    finally:
        receptor.cerrar()
