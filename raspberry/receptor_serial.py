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

            # Armar la parte de mediciones: "s0:148mm s1:201mm ..."
            mediciones = datos.get("mediciones", {})
            lecturas = " ".join(
                "{}:{}mm".format(s, v) for s, v in sorted(mediciones.items())
            )

            aprobada = datos.get("aprobada", False)

            if aprobada:
                print("APROBADA | {}".format(lecturas))
            else:
                # Detectar cuáles sensores fallaron desde el campo detalles
                detalles = datos.get("detalles", {})
                fallidos = [s for s, d in sorted(detalles.items()) if not d.get("ok")]
                print("RECHAZADA | {} (fallo: {})".format(lecturas, ", ".join(fallidos)))

    except KeyboardInterrupt:
        print("\nInterrumpido por el usuario.")
    finally:
        receptor.cerrar()
