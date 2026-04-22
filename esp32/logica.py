# Lógica de inspección dimensional
# Compara las mediciones de los 4 sensores contra referencias y tolerancias
# y decide si la pieza es APROBADA o RECHAZADA


class ResultadoInspeccion:
    """Contiene el resultado completo de una inspección."""

    def __init__(self, mediciones, aprobada, detalles):
        # Dict con las 4 distancias crudas: {"s0": 145, "s1": 203, ...}
        self.mediciones = mediciones
        # True si todos los sensores están dentro de tolerancia
        self.aprobada = aprobada
        # Dict con el análisis por sensor:
        # {"s0": {"valor": 145, "referencia": 150, "tolerancia": 2, "ok": False}, ...}
        self.detalles = detalles


class LogicaInspeccion:
    """
    Evalúa si una pieza cumple las dimensiones requeridas.
    Recibe referencias y tolerancias al construirse, luego evalúa mediciones.
    """

    def __init__(self, referencias):
        """
        referencias: dict con referencia y tolerancia por sensor, ejemplo:
        {
            "s0": {"referencia": 150, "tolerancia": 2},
            "s1": {"referencia": 200, "tolerancia": 2},
        }
        """
        self.referencias = referencias

    def evaluar(self, mediciones):
        """
        Compara cada medición contra su referencia ± tolerancia.
        Devuelve un objeto ResultadoInspeccion.
        """
        detalles = {}
        aprobada = True

        for sensor, valor in mediciones.items():
            ref = self.referencias[sensor]["referencia"]
            tol = self.referencias[sensor]["tolerancia"]

            # La pieza pasa si el valor cae dentro del rango [ref-tol, ref+tol]
            ok = (ref - tol) <= valor <= (ref + tol)

            detalles[sensor] = {
                "valor":       valor,
                "referencia":  ref,
                "tolerancia":  tol,
                "ok":          ok,
            }

            # Basta con que un sensor falle para rechazar la pieza
            if not ok:
                aprobada = False

        return ResultadoInspeccion(mediciones, aprobada, detalles)
