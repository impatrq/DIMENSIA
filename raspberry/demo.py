# Script de demostración — DIMENSIA
# Simula una sesión completa de inspección sin hardware.
# Útil para presentaciones y pruebas del backend/dashboard.

import requests
import time
import random
import json
import os
import sys
from datetime import datetime

# Agregar el directorio actual al path para importar módulos del proyecto
sys.path.insert(0, os.path.dirname(__file__))
from database.db import BaseDatos
from reportes.generador import GeneradorReportes
from verificar_sistema import verificar_backend

from config import URL_BACKEND as _URL_BACKEND

import csv

_RUTA_PENDIENTES = os.path.join(os.path.dirname(__file__), "pendientes.jsonl")


def guardar_pendiente(payload):
    """Guarda una inspección que no se pudo enviar, para reintentar después."""
    with open(_RUTA_PENDIENTES, "a") as f:
        f.write(json.dumps(payload) + "\n")


def reintentar_pendientes():
    """Intenta reenviar las inspecciones guardadas localmente. Devuelve cuántas logró enviar."""
    if not os.path.exists(_RUTA_PENDIENTES):
        return 0

    with open(_RUTA_PENDIENTES, "r") as f:
        lineas = [linea.strip() for linea in f if linea.strip()]

    if not lineas:
        return 0

    enviados = 0
    no_enviados = []
    for linea in lineas:
        payload = json.loads(linea)
        try:
            respuesta = requests.post(_URL_BACKEND + "/inspeccion", json=payload, timeout=3)
            if respuesta.status_code == 200:
                enviados += 1
            else:
                no_enviados.append(linea)
        except Exception:
            no_enviados.append(linea)

    # Reescribir el archivo solo con los que siguen pendientes
    with open(_RUTA_PENDIENTES, "w") as f:
        for linea in no_enviados:
            f.write(linea + "\n")

    if enviados > 0:
        print("[BUFFER] Se reenviaron {} inspeccion(es) pendiente(s).".format(enviados))

    return enviados


def enviar_inspeccion(payload):
    """Envía una inspección al backend. Si falla, la guarda en el buffer local."""
    try:
        respuesta = requests.post(_URL_BACKEND + "/inspeccion", json=payload, timeout=3)
        if respuesta.status_code != 200:
            guardar_pendiente(payload)
            print("[BUFFER] El backend respondió con error, inspeccion guardada localmente.")
    except Exception:
        guardar_pendiente(payload)
        print("[BUFFER] No se pudo conectar al backend, inspeccion guardada localmente.")

DELAY_ENTRE_INSPECCIONES = 5  # segundos entre inspecciones para que el dashboard se vea fluido


def mostrar_bienvenida():
    """Imprime el banner de presentación del sistema al inicio de la demo."""
    print("=" * 50)
    print("        DIMENSIA")
    print("  Sistema de Inspeccion Dimensional Automatizada")
    print("  EET N°7 — Taller Regional Quilmes")
    print("  Especialidad Avionica")
    print("=" * 50)


def generar_numero_serie(n_inspeccion):
    """Genera un número de serie único con formato DIM-{AAAAMMDD}-{NNN}."""
    fecha = datetime.now().strftime("%Y%m%d")
    return "DIM-{}-{:03d}".format(fecha, n_inspeccion)


def actualizar_estado_dashboard(n_inspeccion, resultado):
    """
    Envía el estado actual del sistema a los endpoints del dashboard.
    Se llama después de cada inspección para que los widgets se actualicen.
    Todos los POSTs con timeout=1 para no bloquear la demo si el backend no responde.
    """
    # Sensores: los 3 detectaron la pieza en esta inspección
    try:
        requests.post(_URL_BACKEND + "/sensores",
                      json={"S1": True, "S2": True, "S3": True}, timeout=1)
    except Exception:
        pass

    # Plato: terminó la vuelta completa de 8 capturas
    try:
        requests.post(_URL_BACKEND + "/plato",
                      json={"girando": False, "angulo_actual": 0,
                            "capturas_completadas": 8}, timeout=1)
    except Exception:
        pass

    # Captura: total acumulado de fotos tomadas (8 por inspección)
    try:
        requests.post(_URL_BACKEND + "/captura",
                      json={"total": n_inspeccion * 8}, timeout=1)
    except Exception:
        pass

    # Servos: servo2 activo si aprobada, servo3 activo si rechazada
    if resultado == "APROBADA":
        estado_servos = {"servo1": "reposo", "servo2": "activo", "servo3": "reposo"}
    else:
        estado_servos = {"servo1": "reposo", "servo2": "reposo", "servo3": "activo"}

    try:
        requests.post(_URL_BACKEND + "/servos", json=estado_servos, timeout=1)
    except Exception:
        pass

_RUTA_REPORTE = os.path.join(os.path.dirname(__file__), "reportes", "demo_reporte.pdf")


# ─── Piezas de ejemplo ────────────────────────────────────────────────────────

PIEZAS = [
    {
        "nombre":    "Niple NPT 1/2\"",
        "norma":     "ASME B16.11",
        "largo_ref": 58,    "largo_tol": 1,
        "od_ref":    21.3,  "od_tol":    0.5,
        "id_ref":    None,  "id_tol":    None,
    },
    {
        "nombre":    "Union NPT 3/4\"",
        "norma":     "ASME B16.11",
        "largo_ref": 65,    "largo_tol": 1,
        "od_ref":    26.7,  "od_tol":    0.5,
        "id_ref":    None,  "id_tol":    None,
    },
    {
        "nombre":    "Brida DN25",
        "norma":     "DIN 2999",
        "largo_ref": 42,    "largo_tol": 1,
        "od_ref":    25.8,  "od_tol":    0.5,
        "id_ref":    None,  "id_tol":    None,
    },
]


def generar_medicion(pieza, forzar_rechazo=False):
    """
    Genera dimensiones simuladas para una pieza.
    - forzar_rechazo=False: valores dentro de tolerancia con variación de ±0.5mm
    - forzar_rechazo=True:  al menos una dimensión con desvío de 2 a 3mm
    """
    if not forzar_rechazo:
        alto  = round(pieza["largo_ref"] + random.uniform(-0.5, 0.5), 1)
        ancho = round(pieza["od_ref"]    + random.uniform(-0.5, 0.5), 1)
        largo = round(pieza["largo_ref"] + random.uniform(-0.5, 0.5), 1)
    else:
        # Elegir al azar qué dimensión va a fallar
        desvio = random.uniform(2.0, 3.0) * random.choice([-1, 1])
        alto  = round(pieza["largo_ref"] + (desvio if random.random() < 0.6 else random.uniform(-0.5, 0.5)), 1)
        ancho = round(pieza["od_ref"]    + (desvio if random.random() < 0.6 else random.uniform(-0.5, 0.5)), 1)
        largo = round(pieza["largo_ref"] + random.uniform(-0.5, 0.5), 1)

    return {"alto": alto, "ancho": ancho, "largo": largo}


def generar_secuencia(n_inspecciones):
    """
    Genera la lista de resultados para la sesión.
    True = aprobada, False = rechazada (se pasará como forzar_rechazo invertido).
    Los 3 rechazos quedan siempre centrados sin importar cuántas inspecciones se pidan.
    """
    medio = n_inspecciones // 2
    secuencia = [True] * n_inspecciones
    # Marcar las 3 posiciones centrales como rechazadas
    for pos in [medio - 1, medio, medio + 1]:
        if 0 <= pos < n_inspecciones:
            secuencia[pos] = False
    return secuencia


def evaluar(dimensiones, pieza):
    """Compara las dimensiones contra tolerancias. Devuelve 'APROBADA' o 'RECHAZADA'."""
    def ok(valor, ref, tol):
        return (ref - tol) <= valor <= (ref + tol)

    alto_ok  = ok(dimensiones["alto"],  pieza["largo_ref"], pieza["largo_tol"])
    ancho_ok = ok(dimensiones["ancho"], pieza["od_ref"],    pieza["od_tol"])

    return "APROBADA" if (alto_ok and ancho_ok) else "RECHAZADA"


def simular_sesion(n_inspecciones=10, operario="Demo"):
    """
    Simula una sesión completa: elige una pieza, genera inspecciones,
    las envía al backend, muestra resultados y genera un reporte PDF al final.
    """
    print("=" * 55)
    print("  DIMENSIA — Simulacion de sesion")
    print("=" * 55)

    # Reintentar inspecciones que quedaron pendientes de sesiones anteriores
    reintentar_pendientes()

    # Verificar que el backend esté disponible antes de arrancar
    if not verificar_backend():
        print("[ERROR] El backend no responde en {}".format(_URL_BACKEND))
        print("Verificá que app.py esté corriendo antes de iniciar la demo.")
        return

    # Registrar el momento de inicio para calcular la duración al final
    inicio = time.time()
    print("Inicio de sesion: {}".format(datetime.now().strftime("%H:%M:%S")))
    print("Operario: {}".format(operario))

    # Elegir una pieza al azar para toda la sesión
    pieza = random.choice(PIEZAS)
    print("Pieza cargada: {} ({})".format(pieza["nombre"], pieza["norma"]))
    print("Referencia — largo: {}mm  OD: {}mm".format(pieza["largo_ref"], pieza["od_ref"]))
    print("-" * 55)

    aprobadas  = 0
    rechazadas = 0

    # Secuencia dinámica: los 3 rechazos siempre quedan centrados en la sesión
    secuencia     = generar_secuencia(n_inspecciones)
    primer_rechazo = secuencia.index(False)  # índice del primer rechazo de la racha

    for i in range(1, n_inspecciones + 1):
        forzar_rechazo = not secuencia[i - 1]  # False en secuencia → forzar rechazo

        # Avisar antes de la racha para que el presentador esté atento al dashboard
        if (i - 1) == primer_rechazo:
            print(">>> A partir de aca se simulan 3 rechazos seguidos para mostrar la alerta del dashboard <<<")

        dimensiones   = generar_medicion(pieza, forzar_rechazo)
        resultado     = evaluar(dimensiones, pieza)
        numero_serie  = generar_numero_serie(i)

        if resultado == "APROBADA":
            aprobadas += 1
        else:
            rechazadas += 1

        payload = {
            "pieza":         pieza["nombre"],
            "alto":          dimensiones["alto"],
            "ancho":         dimensiones["ancho"],
            "largo":         dimensiones["largo"],
            "resultado":     resultado,
            "operario":      operario,
            "legajo":        "0000",
            "numero_serie":  numero_serie,
        }

        # Enviar al backend — si falla, se guarda en el buffer local para reintentar despues
        enviar_inspeccion(payload)
        
        # Imprimir encabezado con número de inspección, resultado y número de serie
        print("#{:02d}  {} | {} | {}".format(i, resultado, pieza["nombre"], numero_serie))

        # Imprimir detalle de cada dimensión con referencia, diferencia y estado
        for nombre_dim, valor, ref, tol in [
            ("largo", dimensiones["alto"],  pieza["largo_ref"], pieza["largo_tol"]),
            ("od",    dimensiones["ancho"], pieza["od_ref"],     pieza["od_tol"]),
        ]:
            diferencia = round(valor - ref, 1)
            signo      = "+" if diferencia >= 0 else ""
            dentro     = (ref - tol) <= valor <= (ref + tol)
            estado     = "ok" if dentro else "FUERA DE TOLERANCIA"

            print("  {:<6} {:.1f}mm  (ref: {:.1f} ± {:.1f}mm)  → {}{}mm  {}".format(
                nombre_dim + ":", valor, ref, tol, signo, diferencia, estado
            ))

        # Actualizar los widgets del dashboard con el estado de esta inspección
        actualizar_estado_dashboard(i, resultado)

        # Pausa entre inspecciones — no aplicar después de la última
        if i < n_inspecciones:
            print("Esperando {}s...".format(DELAY_ENTRE_INSPECCIONES))
            time.sleep(DELAY_ENTRE_INSPECCIONES)

        # Línea divisora entre inspecciones
        print("─" * 50)

    # Resumen final
    tasa         = round(rechazadas / n_inspecciones * 100)
    tiempo_total = round(time.time() - inicio, 1)
    print("-" * 55)
    print("Fin de sesion:   {}".format(datetime.now().strftime("%H:%M:%S")))
    print("Total: {}  |  Aprobadas: {}  |  Rechazadas: {}  |  Tasa de rechazo: {}%  |  Tiempo: {} segundos".format(
        n_inspecciones, aprobadas, rechazadas, tasa, tiempo_total,
    ))

    # Generar reporte PDF con las últimas N inspecciones de la base de datos
    try:
        db  = BaseDatos()
        gen = GeneradorReportes(db)
        gen.exportar_pdf(_RUTA_REPORTE, cantidad=n_inspecciones)
        print("Reporte PDF generado: {}".format(_RUTA_REPORTE))
        db.cerrar()
    except Exception as e:
        print("Error al generar el reporte PDF: {}".format(e))


def limpiar_inspecciones_demo(db):
    """
    Borra de la tabla inspecciones todas las filas generadas por la demo.
    Se identifican por el campo operario = 'Demo'.
    """
    cursor = db.conexion.execute(
        "DELETE FROM inspecciones WHERE operario = 'Demo'"
    )
    db.conexion.commit()
    print("{} inspección(es) de demo borrada(s).".format(cursor.rowcount))


if __name__ == "__main__":
    mostrar_bienvenida()

    # --reset limpia los datos de demos anteriores antes de correr una sesión nueva
    if "--reset" in sys.argv:
        db = BaseDatos()
        limpiar_inspecciones_demo(db)
        db.cerrar()

    # Leer --operario "Nombre Apellido" si se pasa como argumento
    operario = "Demo"
    if "--operario" in sys.argv:
        idx = sys.argv.index("--operario")
        if idx + 1 < len(sys.argv):
            operario = sys.argv[idx + 1]

    simular_sesion(10, operario=operario)
