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
#
# Lectura no bloqueante:
#   Se usa select.poll sobre sys.stdin para esperar el primer PASO sin bloquear,
#   lo que permite reenviar ARRIBA cada INTERVALO_REENVIO_ARRIBA_MS hasta que
#   llegue. Es el mecanismo más simple disponible en MicroPython 1.x para leer
#   stdin con timeout. Los pasos siguientes (dentro del ciclo) usan readline()
#   bloqueante porque la Raspberry responde rápido a PASO.

import select
import time
import sys

# ── Parámetros del simulador ─────────────────────────────────────────────────

# Pausa antes del primer ARRIBA (simula tiempo de elevador subiendo)
PAUSA_ANTES_ARRIBA_SEG = 2

# Cada cuánto se reenvía ARRIBA si la Raspberry no respondió todavía (ms)
INTERVALO_REENVIO_ARRIBA_MS = 2000

# Pausa entre recibir PASO y responder PASO_OK (simula giro del plato)
PAUSA_PASO_OK_SEG = 0.5

# Número de pasos que espera el simulador antes de terminar si no llega FIN
MAX_PASOS_ESPERADOS = 16


# ── Helpers de serial ─────────────────────────────────────────────────────────

def _enviar(mensaje):
    """Envía una línea al RPi por stdout (serial)."""
    sys.stdout.write(mensaje + "\n")


def _leer_linea():
    """Lee una línea bloqueante de stdin. Devuelve el string sin espacios extremos."""
    return sys.stdin.readline().strip()


# ── Ciclo del simulador ───────────────────────────────────────────────────────

def correr():
    """
    Bucle principal: repite ciclos de inspección indefinidamente.

    Fase ARRIBA:
      Envía ARRIBA y lo reenvía cada INTERVALO_REENVIO_ARRIBA_MS hasta recibir
      el primer PASO. Usa select.poll con timeout de 100 ms para no bloquear
      en readline() y poder verificar el intervalo de reenvío.
      La Raspberry ignora los ARRIBA duplicados: reset_input_buffer() al inicio
      de cada ciclo limpia la cola, y _esperar_arriba() descarta todo lo que no
      sea 'ARRIBA'.

    Fase pasos:
      Usa readline() bloqueante porque la Raspberry responde PASO_OK rápido.
    """
    # Configurar lectura no bloqueante en stdin para la fase ARRIBA.
    poller = select.poll()
    poller.register(sys.stdin, select.POLLIN)

    ciclo = 0

    while True:
        ciclo += 1
        print("--- Ciclo {} ---".format(ciclo))

        # Simular el tiempo que tarda el elevador en subir
        print("Elevando pieza... ({} s)".format(PAUSA_ANTES_ARRIBA_SEG))
        time.sleep(PAUSA_ANTES_ARRIBA_SEG)

        # ── Fase ARRIBA: enviar y reenviar hasta recibir el primer PASO ──────
        _enviar("ARRIBA")
        t_ultimo_arriba = time.ticks_ms()
        print("Enviado: ARRIBA")

        pasos_recibidos = 0
        primer_paso_recibido = False

        while not primer_paso_recibido:
            # poll() con timeout de 100 ms: devuelve [] si no hay datos
            if poller.poll(100):
                linea = sys.stdin.readline().strip()
                if linea == "PASO":
                    primer_paso_recibido = True
                    pasos_recibidos = 1
                    print("Recibido PASO (1/{})".format(MAX_PASOS_ESPERADOS))
                    time.sleep(PAUSA_PASO_OK_SEG)
                    _enviar("PASO_OK")
                    print("Enviado: PASO_OK")
                # cualquier otra línea (FIN de ciclo anterior, debug) se ignora
            else:
                # Sin datos: comprobar si hay que reenviar ARRIBA
                transcurrido = time.ticks_diff(time.ticks_ms(), t_ultimo_arriba)
                if transcurrido >= INTERVALO_REENVIO_ARRIBA_MS:
                    _enviar("ARRIBA")
                    t_ultimo_arriba = time.ticks_ms()
                    print("Reenviado: ARRIBA")

        # ── Fase pasos: readline() bloqueante para los pasos restantes ────────
        while pasos_recibidos < MAX_PASOS_ESPERADOS:
            linea = _leer_linea()

            if not linea:
                # Línea vacía: timeout de readline, seguir esperando
                continue

            if linea == "PASO":
                pasos_recibidos += 1
                print("Recibido PASO ({}/{})".format(pasos_recibidos, MAX_PASOS_ESPERADOS))
                time.sleep(PAUSA_PASO_OK_SEG)
                _enviar("PASO_OK")
                print("Enviado: PASO_OK")

            elif linea.startswith("FIN"):
                resultado = linea[len("FIN"):].strip()
                print("Recibido FIN — resultado: {}".format(resultado))
                print("Ciclo {} finalizado.\n".format(ciclo))
                break

            else:
                print("Comando desconocido: '{}'".format(linea))

        else:
            # Se alcanzó el límite de pasos sin FIN: posible desincronía
            _enviar("ERROR maximo de pasos alcanzado sin FIN")
            print("[ERROR] No llegó FIN después de {} pasos.".format(MAX_PASOS_ESPERADOS))


# Si se ejecuta como script principal
if __name__ == "__main__":
    correr()
