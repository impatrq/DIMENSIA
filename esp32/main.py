# Programa principal — ESP32
# Lee los 5 sensores (método XSHUT) y manda las lecturas brutas por Serial
# La Raspberry Pi calcula las dimensiones reales y decide el resultado
# MicroPython

from time import sleep_ms
from urandom import randint
from comunicacion import Comunicacion

MODO_SIMULACION = True

# ─── Inicialización del hardware (solo si hay sensores reales) ────────────────

if not MODO_SIMULACION:
    from machine import I2C, Pin
    from multiplexor import GestorSensores

    i2c    = I2C(0, sda=Pin(21), scl=Pin(22), freq=400_000)
    gestor = GestorSensores(i2c)

    print("Inicializando sensores...")
    # inicializar_sensores() devuelve un dict: {"s1": sensor, "s2": ..., ...}
    sensores = gestor.inicializar_sensores()
    print("5 sensores listos. Enviando datos...")

comunicacion = Comunicacion()


def generar_lecturas_simuladas():
    """Genera lecturas aleatorias dentro de rangos realistas para la demo."""
    return {
        "s1":  randint(208, 216),  # alto
        "s2":  randint(67, 72),    # ancho izquierdo
        "s2p": randint(67, 72),    # ancho derecho
        "s3":  randint(78, 83),    # largo frontal
        "s3p": randint(78, 83),    # largo posterior
    }


# ─── Loop principal ───────────────────────────────────────────────────────────

print("Modo simulacion: {}".format(MODO_SIMULACION))

while True:
    if MODO_SIMULACION:
        mediciones = generar_lecturas_simuladas()
    else:
        # Leer los 5 sensores — todos activos en el bus con distintas direcciones
        mediciones = {}
        for nombre, sensor in sensores.items():
            mediciones[nombre] = sensor.leer_distancia()

    # Enviar las 5 lecturas brutas por Serial — la Raspberry Pi decide el resultado
    comunicacion.enviar_mediciones(mediciones)

    sleep_ms(500)
