# Gestión de sensores VL53L4CD mediante el método XSHUT
# En lugar del multiplexor TCA9548A, cada sensor tiene un pin XSHUT:
#   - XSHUT en LOW  → sensor apagado (no responde en I2C)
#   - XSHUT en HIGH → sensor encendido
# Al arrancar se apagan todos, se encienden de a uno y se les asigna
# una dirección I2C única para que convivan en el mismo bus.

from machine import Pin
from time import sleep_ms
from vl53l4cd import VL53L4CD

# Registro del VL53L4CD para cambiar su dirección I2C
_REG_DIRECCION_I2C = 0x0001

# Configuración de cada sensor: pin XSHUT y dirección I2C definitiva
_SENSORES_CONFIG = [
    {"gpio": 25, "direccion": 0x30},  # sensor 0 — largo
    {"gpio": 26, "direccion": 0x31},  # sensor 1 — OD (diámetro exterior)
    {"gpio": 27, "direccion": 0x29},  # sensor 2 — ID (diámetro interior), queda en default
]


class GestorSensores:
    """
    Inicializa los 3 sensores VL53L4CD usando el método XSHUT.
    Cada sensor recibe una dirección I2C única antes de arrancar.
    """

    def __init__(self, i2c):
        self.i2c = i2c
        # Configurar los 3 pines XSHUT como salidas digitales
        self.pines_xshut = [
            Pin(cfg["gpio"], Pin.OUT) for cfg in _SENSORES_CONFIG
        ]

    def inicializar_sensores(self):
        """
        Secuencia de inicialización XSHUT:
        1. Apagar todos los sensores (XSHUT = LOW)
        2. Para cada sensor: encenderlo, asignarle su dirección, avanzar
        3. Devolver lista de 3 instancias VL53L4CD listas para usar

        Es importante hacerlo de a uno: mientras un sensor está en LOW
        no ocupa el bus, así el siguiente puede recibir su dirección
        sin colisionar.
        """
        # Paso 1 — Apagar todos los sensores bajando XSHUT a LOW
        for pin in self.pines_xshut:
            pin.value(0)
        sleep_ms(10)  # Esperar a que todos queden completamente apagados

        sensores = []

        for i, cfg in enumerate(_SENSORES_CONFIG):
            # Paso 2a — Encender solo este sensor subiendo su XSHUT a HIGH
            self.pines_xshut[i].value(1)
            sleep_ms(10)  # Esperar a que el sensor arranque y esté listo en I2C

            # El sensor acaba de encender y está en la dirección default 0x29.
            # Si NO es el último sensor, le cambiamos la dirección ahora
            # para que no colisione cuando encendamos el siguiente.
            if cfg["direccion"] != 0x29:
                self._cambiar_direccion(0x29, cfg["direccion"])

            # Paso 2b — Crear la instancia del sensor con su dirección final
            sensor = VL53L4CD(self.i2c, cfg["direccion"])
            sensor.inicializar()
            sensores.append(sensor)

            print("Sensor {} listo en I2C 0x{:02X}".format(i, cfg["direccion"]))

        return sensores

    def _cambiar_direccion(self, direccion_actual, direccion_nueva):
        """
        Cambia la dirección I2C del sensor que está en direccion_actual.
        El VL53L4CD espera la nueva dirección shifteada un bit a la izquierda.
        """
        reg_alto = (_REG_DIRECCION_I2C >> 8) & 0xFF
        reg_bajo = _REG_DIRECCION_I2C & 0xFF
        self.i2c.writeto(direccion_actual, bytes([reg_alto, reg_bajo, direccion_nueva << 1]))
        sleep_ms(5)  # Dar tiempo al sensor para aplicar el cambio
