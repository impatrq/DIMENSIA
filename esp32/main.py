# Programa principal — ESP32
# Lee los 5 sensores (método XSHUT) y manda las lecturas brutas por Serial
# La Raspberry Pi calcula las dimensiones reales y decide el resultado
# MicroPython

from machine import I2C, Pin
from time import sleep_ms
from multiplexor import GestorSensores
from comunicacion import Comunicacion

# ─── Inicialización del hardware ──────────────────────────────────────────────

i2c = I2C(0, sda=Pin(21), scl=Pin(22), freq=400_000)
gestor = GestorSensores(i2c)
comunicacion = Comunicacion()

# ─── Setup: encender sensores de a uno y asignarles dirección I2C ─────────────

print("Inicializando sensores...")

# inicializar_sensores() devuelve un dict: {"s1": sensor, "s2": ..., ...}
sensores = gestor.inicializar_sensores()

print("5 sensores listos. Enviando datos...")

# ─── Loop principal ───────────────────────────────────────────────────────────

while True:
    # Leer los 5 sensores — todos activos en el bus con distintas direcciones
    mediciones = {}
    for nombre, sensor in sensores.items():
        mediciones[nombre] = sensor.leer_distancia()

    # Enviar las 5 lecturas brutas por Serial — la Raspberry Pi decide el resultado
    comunicacion.enviar_mediciones(mediciones)

    sleep_ms(500)
