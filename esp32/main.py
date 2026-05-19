# Programa principal — ESP32
# Lee los 3 sensores (método XSHUT) y manda las mediciones por Serial a la Raspberry Pi
# La lógica de tolerancias y el resultado (APROBADA/RECHAZADA) los decide la Raspberry Pi
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

# inicializar_sensores() apaga todos, los enciende de a uno,
# les asigna su dirección y devuelve la lista lista para usar
sensores = gestor.inicializar_sensores()

print("Sensores listos. Enviando datos...")

# ─── Loop principal ───────────────────────────────────────────────────────────

while True:
    # Leer los 3 sensores — ahora todos están activos en el bus con distintas direcciones
    mediciones = {}
    for i, sensor in enumerate(sensores):
        mediciones["s{}".format(i)] = sensor.leer_distancia()

    # Enviar las mediciones crudas por Serial — la Raspberry Pi decide el resultado
    comunicacion.enviar_mediciones(mediciones)

    sleep_ms(500)
