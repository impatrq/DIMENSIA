# Gestión de 5 sensores VL53L4CD mediante el método XSHUT
# Cada sensor tiene un pin XSHUT: LOW = apagado, HIGH = encendido.
# Al arrancar se apagan todos, se encienden de a uno y se les asigna
# una dirección I2C única para que convivan en el mismo bus.

from machine import Pin
from time import sleep_ms
from vl53l4cd import VL53L4CD

# Registro del VL53L4CD para cambiar su dirección I2C
_REG_DIRECCION_I2C = 0x0001

# Configuración de los 5 sensores: nombre lógico, pin XSHUT y dirección I2C definitiva.
# El sensor arranca siempre en 0x29 (default), se le cambia antes de encender el siguiente.
_SENSORES_CONFIG = [
    {"nombre": "s1",  "gpio": 17, "direccion": 0x30},  # alto
    {"nombre": "s2",  "gpio": 27, "direccion": 0x31},  # ancho izquierdo
    {"nombre": "s2p", "gpio": 22, "direccion": 0x32},  # ancho derecho
    {"nombre": "s3",  "gpio": 23, "direccion": 0x33},  # largo frontal
    {"nombre": "s3p", "gpio": 24, "direccion": 0x34},  # largo posterior
]


class GestorSensores:
    """
    Inicializa los 5 sensores VL53L4CD usando el método XSHUT.
    Cada sensor recibe una dirección I2C única antes de que se encienda el siguiente.
    """

    def __init__(self, i2c):
        self.i2c = i2c
        # Configurar los 5 pines XSHUT como salidas digitales
        self.pines_xshut = [
            Pin(cfg["gpio"], Pin.OUT) for cfg in _SENSORES_CONFIG
        ]

    def inicializar_sensores(self):
        """
        Secuencia de inicialización XSHUT:
        1. Apagar todos los sensores (todos los XSHUT en LOW)
        2. Para cada sensor: encenderlo → asignarle dirección → inicializarlo
        3. Devolver dict con los 5 sensores listos:
           {"s1": <VL53L4CD>, "s2": ..., "s2p": ..., "s3": ..., "s3p": ...}
        """
        # Paso 1 — Apagar todos para empezar desde cero
        for pin in self.pines_xshut:
            pin.value(0)
        sleep_ms(10)

        sensores = {}

        for i, cfg in enumerate(_SENSORES_CONFIG):
            # Encender solo este sensor — aparece en el bus en la dirección default 0x29
            self.pines_xshut[i].value(1)
            sleep_ms(10)  # Esperar a que el sensor esté listo en I2C

            # Cambiarle la dirección para que no colisione con los siguientes
            self._cambiar_direccion(0x29, cfg["direccion"])

            # Crear la instancia con su dirección definitiva e inicializarla
            sensor = VL53L4CD(self.i2c, cfg["direccion"])
            sensor.inicializar()
            sensores[cfg["nombre"]] = sensor

            print("Sensor {} listo en I2C 0x{:02X}".format(cfg["nombre"], cfg["direccion"]))

        return sensores

    def _cambiar_direccion(self, direccion_actual, direccion_nueva):
        """
        Cambia la dirección I2C del sensor que responde en direccion_actual.
        El VL53L4CD espera la nueva dirección shifteada un bit a la izquierda.
        """
        reg_alto = (_REG_DIRECCION_I2C >> 8) & 0xFF
        reg_bajo = _REG_DIRECCION_I2C & 0xFF
        self.i2c.writeto(direccion_actual, bytes([reg_alto, reg_bajo, direccion_nueva << 1]))
        sleep_ms(5)
