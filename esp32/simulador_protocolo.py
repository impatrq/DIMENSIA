# Simulador del protocolo Serial para ESP32 — DIMENSIA
# Corre en MicroPython en la ESP32 (sin pines, sin hardware).
# Simula el lado ESP32 del protocolo de inspección:
#   ESP32 -> RPi: ARRIBA | PASO_OK | ERROR <detalle>
#   RPi -> ESP32: PASO | FIN APROBADA | FIN RECHAZADA
#
# Uso (en REPL de MicroPython o como main.py de prueba):
#   import simulador_protocolo
#   simulador_protocolo.correr()
#
# O copiar como main.py en la ESP32 para que corra al arrancar.

import time
import sys

# ── Parámetros del simulador ─────────────────────────────────────────────────

# Pausa antes de enviar ARRIBA (simula tiempo de elevador subiendo)
PAUSA_ANTES_ARRIBA_SEG = 2

# Pausa entre recibir PASO y responder PASO_OK (simula giro del plato)
PAUSA_PASO_OK_SEG = 0.5

# Número de pasos que espera el simulador antes de terminar si no llega FIN
# (sólo para detectar desincronía; en operación normal llega FIN del RPi)
MAX_PASOS_ESPERADOS = 16


# ── Helpers de serial ─────────────────────────────────────────────────────────

def _leer_linea():
    """
    Lee una línea del stdin (puerto serial en MicroPython).
    Devuelve el string sin salto de línea ni espacios extremos.
    """
    linea = sys.stdin.readline()
    return linea.strip()


def _enviar(mensaje):
    """Envía una línea al RPi por stdout (serial)."""
    sys.stdout.write(mensaje + "\n")


# ── Ciclo del simulador ───────────────────────────────────────────────────────

def correr():
    """
    Bucle principal: repite ciclos de inspección indefinidamente.
    Cada ciclo:
      1. Pausa y envía ARRIBA.
      2. Espera PASO, responde PASO_OK, repite hasta recibir FIN.
      3. Imprime el resultado recibido en FIN.
    """
    ciclo = 0

    while True:
        ciclo += 1
        print("--- Ciclo {} ---".format(ciclo))

        # Simular el tiempo que tarda el elevador en subir
        print("Elevando pieza... ({} s)".format(PAUSA_ANTES_ARRIBA_SEG))
        time.sleep(PAUSA_ANTES_ARRIBA_SEG)

        _enviar("ARRIBA")
        print("Enviado: ARRIBA")

        pasos_recibidos = 0

        while pasos_recibidos < MAX_PASOS_ESPERADOS:
            linea = _leer_linea()

            if not linea:
                # Línea vacía: timeout de readline, seguir esperando
                continue

            if linea == "PASO":
                pasos_recibidos += 1
                print("Recibido PASO ({}/{})".format(pasos_recibidos, MAX_PASOS_ESPERADOS))

                # Simular el tiempo de giro del plato
                time.sleep(PAUSA_PASO_OK_SEG)

                _enviar("PASO_OK")
                print("Enviado: PASO_OK")

            elif linea.startswith("FIN"):
                resultado = linea[len("FIN"):].strip()
                print("Recibido FIN — resultado: {}".format(resultado))
                print("Ciclo {} finalizado.\n".format(ciclo))
                break

            else:
                # Comando desconocido (no debería llegar si el RPi sigue el protocolo)
                print("Comando desconocido: '{}'".format(linea))

        else:
            # Se alcanzó el límite de pasos sin FIN: posible desincronía
            _enviar("ERROR maximo de pasos alcanzado sin FIN")
            print("[ERROR] No llegó FIN después de {} pasos.".format(MAX_PASOS_ESPERADOS))


# Si se ejecuta como script principal
if __name__ == "__main__":
    correr()
