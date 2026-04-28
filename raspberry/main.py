# Puente Serial → Backend — Raspberry Pi 4
# Lee los JSON de la ESP32 por Serial USB y los reenvía al backend Flask via HTTP POST
# Requiere: pip install pyserial requests

import requests
from receptor_serial import ReceptorSerial

_URL_BACKEND = "http://localhost:5000/inspeccion"


def main():
    receptor = ReceptorSerial()
    print("Puente activo. Esperando datos de la ESP32...\n")

    try:
        while True:
            datos = receptor.leer_siguiente()

            # leer_siguiente devuelve None si la línea no era JSON válido
            if datos is None:
                continue

            mediciones = datos.get("mediciones", {})

            # Armar el dict con los campos que espera el backend Flask
            payload = {
                "pieza":     "Sin identificar",
                "largo":     mediciones.get("s0"),
                "od":        mediciones.get("s1"),
                "id":        mediciones.get("s2"),
                "resultado": "APROBADA" if datos.get("aprobada") else "RECHAZADA",
            }

            # Enviar al backend y manejar errores de red sin romper el loop
            try:
                requests.post(_URL_BACKEND, json=payload, timeout=3)
            except requests.exceptions.RequestException as e:
                print("Error al enviar al backend: {}".format(e))
                continue

            print("Enviado: {} | largo:{}mm od:{}mm id:{}mm".format(
                payload["resultado"],
                payload["largo"],
                payload["od"],
                payload["id"],
            ))

    except KeyboardInterrupt:
        print("\nInterrumpido por el usuario.")
    finally:
        receptor.cerrar()


if __name__ == "__main__":
    main()
