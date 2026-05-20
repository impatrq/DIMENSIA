# Comunicación Serial USB con la Raspberry Pi
# Envía las mediciones crudas de los sensores como JSON por el puerto Serial
# En MicroPython, print() escribe directamente al Serial USB (REPL/UART0)

import json
from time import ticks_ms


class Comunicacion:
    """Serializa y envía mediciones a la Raspberry Pi."""

    def enviar_mediciones(self, mediciones):
        """
        Recibe el dict con las 5 lecturas brutas (s1, s2, s2p, s3, s3p),
        le agrega el timestamp y lo manda por Serial como una línea JSON.
        La Raspberry Pi lee línea por línea y parsea cada JSON recibido.
        """
        datos = dict(mediciones)
        datos["timestamp"] = ticks_ms()  # ms desde que arrancó la ESP32

        print(json.dumps(datos))
