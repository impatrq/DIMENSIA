# Programa principal — ESP32
# Lee los 3 sensores y manda las mediciones por Serial a la Raspberry Pi
# La lógica de tolerancias y el resultado (APROBADA/RECHAZADA) los decide la Raspberry Pi
# MicroPython

from machine import I2C, Pin
from time import sleep_ms
from multiplexor import Multiplexor
from vl53l4cd import VL53L4CD
from comunicacion import Comunicacion

# ─── Inicialización del hardware ──────────────────────────────────────────────

i2c = I2C(0, sda=Pin(21), scl=Pin(22), freq=400_000)
mux = Multiplexor(i2c)
sensores = [VL53L4CD(i2c) for _ in range(3)]

comunicacion = Comunicacion()

# ─── Setup: inicializar cada sensor en su canal ───────────────────────────────

print("Inicializando sensores...")

for canal in range(3):
    mux.seleccionar_canal(canal)
    sensores[canal].inicializar()
    mux.desactivar_todos()

print("Sensores listos. Enviando datos...")

# ─── Loop principal ───────────────────────────────────────────────────────────

while True:
    # Leer los 3 sensores de a uno, activando y desactivando el canal cada vez
    mediciones = {}
    for canal in range(3):
        mux.seleccionar_canal(canal)
        mediciones["s{}".format(canal)] = sensores[canal].leer_distancia()
        mux.desactivar_todos()

    # Enviar las mediciones crudas por Serial — la Raspberry Pi decide el resultado
    comunicacion.enviar_mediciones(mediciones)

    sleep_ms(500)
