# Verificación del sistema — DIMENSIA
# Chequea que todos los componentes estén listos antes de una presentación.
# Correr con: python3 raspberry/verificar_sistema.py

import requests
from config import URL_BACKEND
import os
import sys

_DIR = os.path.dirname(__file__)
_RUTA_CALIBRACION = os.path.join(_DIR, "calibracion.json")
_RUTA_REPORTES    = os.path.join(_DIR, "reportes")


def verificar_backend():
    """Comprueba que el servidor Flask esté levantado y respondiendo."""
    try:
        respuesta = requests.get(URL_BACKEND + "/", timeout=3)
        if respuesta.status_code == 200:
            print("[OK] Backend funcionando")
            return True
    except Exception:
        pass

    print("[ERROR] Backend no responde. Verificá que app.py esté corriendo.")
    return False


def verificar_piezas():
    """Comprueba que haya al menos una pieza cargada en la base de datos."""
    try:
        respuesta = requests.get(URL_BACKEND + "/piezas", timeout=3)
        piezas = respuesta.json()

        if len(piezas) > 0:
            print("[OK] Hay {} pieza(s) cargada(s) en la base de datos".format(len(piezas)))
            return True
    except Exception:
        pass

    print("[ERROR] No hay piezas cargadas. Corré inicializar_db.py primero.")
    return False


def verificar_calibracion():
    """
    Comprueba si existe el archivo de calibración.
    Es un aviso, no un error bloqueante — el sistema puede correr sin él
    pero las dimensiones van a salir como None.
    """
    if os.path.exists(_RUTA_CALIBRACION):
        print("[OK] Calibracion encontrada")
        return True

    print("[AVISO] No hay calibracion.json. Las dimensiones van a salir como None.")
    return False


def verificar_carpeta_reportes():
    """Comprueba que exista la carpeta de reportes; la crea si no existe."""
    os.makedirs(_RUTA_REPORTES, exist_ok=True)
    print("[OK] Carpeta de reportes lista")


if __name__ == "__main__":
    print("=" * 50)
    print("  Verificacion del sistema DIMENSIA")
    print("=" * 50)

    ok_backend     = verificar_backend()
    ok_piezas      = verificar_piezas()
    ok_calibracion = verificar_calibracion()
    verificar_carpeta_reportes()

    print("-" * 50)

    # La calibración faltante no bloquea — el sistema igual arranca
    if ok_backend and ok_piezas:
        print("Sistema listo para la demo.")
    else:
        print("Hay problemas que resolver antes de la demo.")
