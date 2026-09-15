# Calibración interactiva del servo del plato — DIMENSIA
# Script standalone para la ESP32. Correr directamente por REPL o
# copiarlo como main.py temporalmente para ejecutarlo al arrancar.
# Objetivo: encontrar el tiempo_ms que hace girar el plato exactamente 45°
# (un octavo de vuelta), que es el paso entre cada captura del ciclo de inspección.
# MicroPython

from servo_plato import ServoPlato


def calibrar_interactivo():
    """
    Guía paso a paso para encontrar el tiempo de giro de 45°.
    El operario prueba distintos valores hasta que el plato avance exactamente
    un octavo de vuelta, y al final se imprime el valor a copiar en main.py.
    """
    plato = ServoPlato()

    print("=== Calibracion del servo del plato ===")
    print("Marca con cinta un punto de referencia en el plato")
    print("y otro fijo en la base, alineados.")
    print("Vas a probar distintos tiempos hasta que el plato")
    print("gire exactamente 45 grados (un octavo de vuelta).")
    print("")

    tiempo_ms = 500  # punto de partida razonable para la mayoría de los servos

    while True:
        print("Tiempo actual: {}ms".format(tiempo_ms))
        entrada = input(
            "Presiona ENTER para probar este tiempo, "
            "'+' para aumentar 50ms, '-' para disminuir 50ms, "
            "'ok' si el giro fue exacto, 'q' para salir sin guardar: "
        ).strip()

        if entrada == "+":
            tiempo_ms += 50

        elif entrada == "-":
            # No bajar de 50ms — valores muy bajos pueden dañar el servo
            tiempo_ms = max(50, tiempo_ms - 50)

        elif entrada == "":
            # ENTER: ejecutar el giro con el tiempo actual para observarlo
            plato.girar_tiempo("horario", tiempo_ms)

        elif entrada == "ok":
            print("")
            print("Valor calibrado: TIEMPO_GIRO_MS = {}".format(tiempo_ms))
            print("Copia este valor a raspberry/main.py")
            break

        elif entrada == "q":
            print("Calibracion cancelada.")
            break


if __name__ == "__main__":
    calibrar_interactivo()
