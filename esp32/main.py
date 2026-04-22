# Programa principal — ESP32
# Paso 4: leer sensores, evaluar tolerancias y enviar resultado por Serial JSON
# MicroPython

from machine import I2C, Pin
from time import sleep_ms
from multiplexor import Multiplexor
from vl53l4cd import VL53L4CD
from logica import LogicaInspeccion
from comunicacion import Comunicacion

# ─── Inicialización del hardware ──────────────────────────────────────────────

i2c = I2C(0, sda=Pin(21), scl=Pin(22), freq=400_000)
mux = Multiplexor(i2c)
sensores = [VL53L4CD(i2c) for _ in range(4)]

# ─── Valores de referencia y tolerancias (en mm) ─────────────────────────────

logica = LogicaInspeccion({
    "s0": {"referencia": 150, "tolerancia": 2},
    "s1": {"referencia": 200, "tolerancia": 2},
    "s2": {"referencia": 100, "tolerancia": 2},
    "s3": {"referencia": 300, "tolerancia": 2},
})

comunicacion = Comunicacion()

# ─── Setup: inicializar cada sensor en su canal ───────────────────────────────

print("Inicializando sensores...")

for canal in range(4):
    mux.seleccionar_canal(canal)
    sensores[canal].inicializar()
    mux.desactivar_todos()

print("Sensores listos. Enviando datos...")

# ─── Loop principal ───────────────────────────────────────────────────────────

while True:
    # Leer los 4 sensores de a uno
    mediciones = {}
    for canal in range(4):
        mux.seleccionar_canal(canal)
        mediciones["s{}".format(canal)] = sensores[canal].leer_distancia()
        mux.desactivar_todos()

    # Evaluar tolerancias
    resultado = logica.evaluar(mediciones)

    # Enviar JSON por Serial a la Raspberry Pi
    comunicacion.enviar_resultado(resultado)

    # Solo imprimir en consola si hay un rechazo, para facilitar el debug
    if not resultado.aprobada:
        fallidos = [s for s, d in resultado.detalles.items() if not d["ok"]]
        print("RECHAZADA: {}".format(", ".join(fallidos)))

    sleep_ms(500)
