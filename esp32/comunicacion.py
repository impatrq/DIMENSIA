# Comunicación Serial USB con la Raspberry Pi
# Envía el resultado de cada inspección como JSON por el puerto Serial
# En MicroPython, print() escribe directamente al Serial USB (REPL/UART0)

import json
from time import ticks_ms


class Comunicacion:
    """Serializa y envía resultados de inspección a la Raspberry Pi."""

    def enviar_resultado(self, resultado):
        """
        Convierte un ResultadoInspeccion a JSON y lo envía por Serial.
        La Raspberry Pi lee línea por línea y parsea cada JSON recibido.
        """
        datos = {
            "aprobada":   resultado.aprobada,
            "mediciones": resultado.mediciones,
            "detalles":   resultado.detalles,
            "timestamp":  ticks_ms(),   # ms desde que arrancó la ESP32
        }

        # print() en MicroPython escribe al Serial USB — la Raspberry Pi lo lee
        print(json.dumps(datos))
