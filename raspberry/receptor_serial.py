# Receptor Serial USB — Raspberry Pi 4
# Lee los JSON que manda la ESP32 por el puerto Serial y los procesa
# Requiere: pip install pyserial

import serial
import json


class ReceptorSerial:
    """Lee resultados de inspección enviados por la ESP32 via Serial USB."""

    def __init__(self, puerto="/dev/ttyUSB0", baudrate=115200):
        try:
            self.conexion = serial.Serial(puerto, baudrate, timeout=5)
            print("Serial abierto en {} a {} baud".format(puerto, baudrate))
        except serial.SerialException as e:
            raise Exception(
                "No se pudo abrir el puerto {}. "
                "¿Está conectada la ESP32? Error: {}".format(puerto, e)
            )

    def leer_siguiente(self):
        """
        Espera y lee la próxima línea del Serial.
        Devuelve el dict del JSON o None si la línea no era JSON válido.
        """
        try:
            linea = self.conexion.readline().decode("utf-8").strip()
        except serial.SerialException as e:
            raise Exception("Error de conexión Serial: {}".format(e))

        if not linea:
            return None

        try:
            return json.loads(linea)
        except ValueError:
            # La ESP32 a veces manda líneas de debug que no son JSON — las ignoramos
            return None

    def cerrar(self):
        """Cierra el puerto Serial limpiamente."""
        self.conexion.close()
        print("Puerto Serial cerrado.")


# ─── Programa de prueba ───────────────────────────────────────────────────────

if __name__ == "__main__":
    receptor = ReceptorSerial()

    print("Escuchando ESP32. Presioná Ctrl+C para salir.\n")

    try:
        while True:
            datos = receptor.leer_siguiente()

            # leer_siguiente devuelve None si la línea no era JSON
            if datos is None:
                continue

            # Imprimir las 5 lecturas brutas y el timestamp.
            # La ESP32 ya no evalúa tolerancias — solo manda los valores crudos.
            # La evaluación la hace main.py en la Raspberry Pi.
            print("s1={} s2={} s2p={} s3={} s3p={}  (t={}ms)".format(
                datos.get("s1"), datos.get("s2"), datos.get("s2p"),
                datos.get("s3"), datos.get("s3p"), datos.get("timestamp")
            ))

    except KeyboardInterrupt:
        print("\nInterrumpido por el usuario.")
    finally:
        receptor.cerrar()
