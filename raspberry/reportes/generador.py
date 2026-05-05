# Generador de reportes — Raspberry Pi 4
# Exporta las inspecciones guardadas en SQLite a CSV y PDF
# Requiere: pip install reportlab

import csv
import os
import sys
from datetime import datetime

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet

# Agregar el directorio padre al path para poder importar desde database/
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from database.db import BaseDatos


class GeneradorReportes:
    """Exporta inspecciones de la base de datos a CSV y PDF."""

    def __init__(self, db):
        self.db = db

    def exportar_csv(self, ruta, cantidad=500):
        """
        Exporta las últimas N inspecciones a un archivo CSV.
        Devuelve la cantidad de filas exportadas.
        """
        filas = self.db.obtener_ultimas(cantidad)

        with open(ruta, "w", newline="", encoding="utf-8") as archivo:
            escritor = csv.writer(archivo)

            # Encabezado de columnas
            escritor.writerow(["id", "fecha", "hora", "resultado", "largo(s0)", "od(s1)", "id_inner(s2)"])

            for fila in filas:
                escritor.writerow([
                    fila["id"],
                    fila["fecha"],
                    fila["hora"],
                    "APROBADA" if fila["aprobada"] else "RECHAZADA",
                    fila["s0"],
                    fila["s1"],
                    fila["s2"],
                ])

        return len(filas)

    def exportar_pdf(self, ruta, cantidad=500):
        """
        Exporta las últimas N inspecciones a un PDF con tabla y resumen.
        Devuelve la cantidad de filas exportadas.
        """
        filas = self.db.obtener_ultimas(cantidad)
        ahora = datetime.now().strftime("%d/%m/%Y %H:%M:%S")

        estilos = getSampleStyleSheet()
        elementos = []

        # Título y subtítulo
        elementos.append(Paragraph("DIMENSIA - Reporte de Inspecciones", estilos["Title"]))
        elementos.append(Paragraph("Generado el {}".format(ahora), estilos["Normal"]))
        elementos.append(Spacer(1, 0.5 * cm))

        # Encabezado de la tabla
        encabezado = ["N", "Fecha", "Hora", "Resultado", "Largo", "OD", "ID"]
        datos_tabla = [encabezado]

        aprobadas = 0
        for fila in filas:
            resultado = "APROBADA" if fila["aprobada"] else "RECHAZADA"
            if fila["aprobada"]:
                aprobadas += 1
            datos_tabla.append([
                fila["id"],
                fila["fecha"],
                fila["hora"],
                resultado,
                "{} mm".format(fila["s0"]),
                "{} mm".format(fila["s1"]),
                "{} mm".format(fila["s2"]),
            ])

        # Crear y estilizar la tabla
        tabla = Table(datos_tabla, colWidths=[1.2*cm, 3*cm, 2.5*cm, 3*cm, 2.5*cm, 2.5*cm, 2.5*cm])
        tabla.setStyle(TableStyle([
            # Encabezado con fondo oscuro
            ("BACKGROUND",   (0, 0), (-1, 0), colors.HexColor("#2c3e50")),
            ("TEXTCOLOR",    (0, 0), (-1, 0), colors.white),
            ("FONTNAME",     (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE",     (0, 0), (-1, 0), 9),
            # Filas de datos
            ("FONTSIZE",     (0, 1), (-1, -1), 8),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f2f2f2")]),
            # Colorear la columna de resultado
            ("GRID",         (0, 0), (-1, -1), 0.5, colors.HexColor("#cccccc")),
            ("ALIGN",        (0, 0), (-1, -1), "CENTER"),
            ("VALIGN",       (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING",   (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING",(0, 0), (-1, -1), 4),
        ]))
        elementos.append(tabla)

        # Resumen al final
        rechazadas = len(filas) - aprobadas
        elementos.append(Spacer(1, 0.7 * cm))
        elementos.append(Paragraph(
            "Total: {}  |  Aprobadas: {}  |  Rechazadas: {}".format(
                len(filas), aprobadas, rechazadas
            ),
            estilos["Normal"]
        ))

        # Generar el PDF
        doc = SimpleDocTemplate(ruta, pagesize=A4,
                                leftMargin=2*cm, rightMargin=2*cm,
                                topMargin=2*cm, bottomMargin=2*cm)
        doc.build(elementos)

        return len(filas)


# ─── Prueba rápida ────────────────────────────────────────────────────────────

if __name__ == "__main__":
    db = BaseDatos()
    gen = GeneradorReportes(db)

    ruta_csv = "/tmp/reporte_prueba.csv"
    ruta_pdf = "/tmp/reporte_prueba.pdf"

    filas_csv = gen.exportar_csv(ruta_csv)
    print("CSV exportado: {} filas → {}".format(filas_csv, ruta_csv))

    filas_pdf = gen.exportar_pdf(ruta_pdf)
    print("PDF exportado: {} filas → {}".format(filas_pdf, ruta_pdf))

    db.cerrar()
