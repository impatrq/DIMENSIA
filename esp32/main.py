# Programa principal — ESP32
# Lee los 5 sensores (método XSHUT) y manda las lecturas brutas por Serial
# La Raspberry Pi calcula las dimensiones reales y decide el resultado
# MicroPython

from machine import I2C, Pin
from time import sleep_ms
import urandom
from multiplexor import GestorSensores
from comunicacion import Comunicacion

# Cambiar a False para usar los sensores reales en producción
MODO_SIMULACION = True

# ─── Inicialización del hardware ──────────────────────────────────────────────

i2c = I2C(0, sda=Pin(21), scl=Pin(22), freq=400_000)
gestor = GestorSensores(i2c)
comunicacion = Comunicacion()

# ─── Setup ────────────────────────────────────────────────────────────────────

if MODO_SIMULACION:
    print("MODO SIMULACION ACTIVO")
else:
    # inicializar_sensores() devuelve un dict: {"s1": sensor, "s2": ..., ...}
    print("Inicializando sensores...")
    sensores = gestor.inicializar_sensores()
    print("Sensores reales activos")


def generar_lecturas_simuladas():
    """
    Genera lecturas aleatorias dentro de rangos realistas para cada sensor.
    Útil para probar el sistema completo sin hardware conectado.
    """
    def aleatorio(minimo, maximo):
        # urandom.getrandbits(8) devuelve un entero entre 0 y 255
        # Se escala al rango deseado con módulo y se suma el mínimo
        return minimo + (urandom.getrandbits(8) % (maximo - minimo + 1))

    return {
        "s1":  aleatorio(150, 210),  # sensor de alto
        "s2":  aleatorio(55,  75),   # sensor ancho izquierdo
        "s2p": aleatorio(55,  75),   # sensor ancho derecho
        "s3":  aleatorio(75,  95),   # sensor largo frontal
        "s3p": aleatorio(75,  95),   # sensor largo posterior
    }


# ─── Loop principal ───────────────────────────────────────────────────────────

while True:
    if MODO_SIMULACION:
        # Generar lecturas simuladas en lugar de leer los sensores físicos
        mediciones = generar_lecturas_simuladas()
    else:
        # Leer los 5 sensores reales — todos activos en el bus con distintas direcciones
        mediciones = {}
        for nombre, sensor in sensores.items():
            mediciones[nombre] = sensor.leer_distancia()

    # Enviar las lecturas por Serial — misma ruta tanto en simulación como en real
    comunicacion.enviar_mediciones(mediciones)

    sleep_ms(500)
