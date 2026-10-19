# Programa principal — ESP32 DIMENSIA
# Orquesta el ciclo completo de inspección:
# botón → elevador sube → 8 giros con captura → clasificación → elevador baja
# MicroPython

import sys
import json
from machine import Pin
from time import sleep_ms

from elevador import Elevador
from servo_plato import ServoPlato
from servo_brazo import ServoBrazo
from servo_paleta import ServoPaleta
from comunicacion import Comunicacion
from pines import PIN_BOTON

# ─── Inicialización del hardware ──────────────────────────────────────────────

boton    = Pin(PIN_BOTON, Pin.IN, Pin.PULL_UP)
elevador = Elevador()
plato    = ServoPlato()
brazo    = ServoBrazo()
paleta   = ServoPaleta()
com      = Comunicacion()

print("Sistema DIMENSIA listo. Esperando botón...")


def leer_comando():
    """
    Espera una línea de texto por Serial (enviada por la Raspberry Pi) y la
    parsea como JSON. Repite hasta recibir un JSON válido.
    En MicroPython, sys.stdin.readline() lee desde el mismo UART0/USB
    que usa print() para enviar — es el canal bidireccional de comunicación.
    """
    while True:
        linea = sys.stdin.readline().strip()
        if not linea:
            continue
        try:
            return json.loads(linea)
        except ValueError:
            # Ignorar líneas que no sean JSON válido (puede haber basura al inicio)
            continue


def ciclo_inspeccion():
    """
    Ejecuta un ciclo completo de inspección:
    1. Subir el elevador
    2. Notificar a la Raspberry Pi que la pieza está en posición
    3. Ejecutar 8 giros del plato a pedido de la Raspberry Pi
    4. Recibir el resultado final
    5. Clasificar la pieza y bajar el elevador
    """

    # ── Paso 1: subir el elevador ──────────────────────────────────────────────
    print("Subiendo elevador...")
    llego = elevador.subir()

    if not llego:
        # El elevador no alcanzó el final de carrera superior antes del timeout
        print(json.dumps({"evento": "error_elevador", "detalle": "timeout al subir"}))
        return  # volver al loop principal, esperar el botón de nuevo

    # ── Paso 2: notificar que la pieza está en posición de medición ───────────
    print(json.dumps({"evento": "listo_para_medir"}))

    # ── Paso 3: loop de 8 giros comandados por la Raspberry Pi ───────────────
    # La Raspi manda {"comando": "girar"} una vez por captura.
    # El tiempo de giro está definido en TIEMPO_PASO_45_MS dentro de servo_plato.py:
    # es la fuente única de verdad para ese parámetro, no raspberry/main.py.
    # Si el comando trae "tiempo_ms", se ignora — la ESP32 decide el tiempo de giro.

    # Pausa después del giro y antes de confirmar, para que el plato se asiente
    # y las cámaras no capturen mientras aún hay vibración.
    # PROVISIONAL: ajustar con la cámara real conectada.
    PAUSA_ASENTAMIENTO_MS = 1000

    for _ in range(8):
        cmd = leer_comando()

        if cmd.get("comando") == "girar":
            plato.girar_paso("horario")
            sleep_ms(PAUSA_ASENTAMIENTO_MS)
            print(json.dumps({"evento": "giro_completado"}))
        else:
            # Comando inesperado — ignorar y seguir esperando
            continue

    # ── Paso 4: esperar el resultado de la clasificación ─────────────────────
    # La Raspberry Pi manda {"resultado": "APROBADA"} o {"resultado": "RECHAZADA"}
    # después de procesar todas las capturas.
    while True:
        cmd = leer_comando()
        resultado = cmd.get("resultado")
        if resultado in ("APROBADA", "RECHAZADA"):
            break
        # Si llega cualquier otra cosa, seguir esperando

    # ── Paso 5: clasificar la pieza y bajar el elevador ──────────────────────
    # Primero inclinar la paleta hacia la rama correcta, después empujar la pieza.
    paleta.posicionar(resultado)
    sleep_ms(300)   # dar tiempo a la paleta para llegar a la posición
    brazo.empujar()

    elevador.bajar()
    print(json.dumps({"evento": "ciclo_completado", "resultado": resultado}))


# ─── Loop principal ───────────────────────────────────────────────────────────

while True:
    # Esperar que el operario presione el botón de inicio.
    # El pin lee LOW cuando el botón está presionado (pull-up activo en HIGH).
    if boton.value() == 0:
        sleep_ms(50)   # anti-rebote: confirmar que sigue presionado
        if boton.value() == 0:
            ciclo_inspeccion()

    sleep_ms(20)   # pequeña pausa para no saturar el CPU en el loop de espera
