"""
Exportación a PDF (fpdf2), Excel (openpyxl) y CSV. Lo usan el plan de
acción de controles (HU15), el plan de remediación (HU17) y los
reportes periódicos (HU21).
"""

import csv
import io

from django.http import HttpResponse
from django.utils import timezone
from fpdf import FPDF
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill

TIPOS = {
    "pdf": "application/pdf",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "csv": "text/csv; charset=utf-8",
}

# Las fuentes base de PDF solo cubren Latin-1 (sí incluye á, é, ñ, °).
_REEMPLAZOS = str.maketrans(
    {"—": "-", "–": "-", "…": "...", "“": '"', "”": '"', "‘": "'", "’": "'", "≥": ">=", "≤": "<=",
     "→": "->", "•": "-", "✓": "OK", "«": '"', "»": '"', " ": " "}
)


def _celda(valor, prefijos=("=", "+", "-", "@")):
    """
    Evita la "inyección de fórmulas" en CSV/Excel: un título de hallazgo
    que empiece con = + - @ se abriría como fórmula en la hoja de
    cálculo. Se antepone un apóstrofo para que quede como texto. (Un "-"
    solo, que usamos como "sin dato", no es fórmula y se deja igual.)
    """
    if isinstance(valor, str) and len(valor) > 1 and valor[0] in prefijos:
        return "'" + valor
    return valor


def _t(valor):
    texto = "" if valor is None else str(valor)
    return texto.translate(_REEMPLAZOS).encode("latin-1", "replace").decode("latin-1")


class _PDF(FPDF):
    titulo_doc = "Centinela Salud"

    def header(self):
        self.set_font("Helvetica", "B", 9)
        self.set_text_color(90, 107, 140)
        self.cell(0, 6, _t(f"Centinela Salud · {self.titulo_doc}"), new_x="LMARGIN", new_y="NEXT")
        self.set_draw_color(207, 217, 236)
        self.line(10, 16, 200, 16)
        self.ln(4)

    def footer(self):
        self.set_y(-12)
        self.set_font("Helvetica", "", 8)
        self.set_text_color(120, 120, 120)
        self.cell(0, 6, _t(f"Generado el {timezone.localtime():%d/%m/%Y %H:%M} · página {self.page_no()}"), align="C")


def pdf_bytes(titulo, bloques):
    """
    bloques: lista de tuplas
      ("titulo", texto) · ("subtitulo", texto) · ("parrafo", texto)
      ("tabla", columnas, filas, anchos_relativos | None) · ("salto",)
      ("semaforo", color_rgb, texto)
    """
    pdf = _PDF(orientation="P", unit="mm", format="A4")
    pdf.titulo_doc = titulo
    pdf.set_auto_page_break(True, margin=15)
    pdf.add_page()
    pdf.set_text_color(15, 27, 51)
    for bloque in bloques:
        tipo = bloque[0]
        if tipo == "titulo":
            pdf.set_font("Helvetica", "B", 16)
            pdf.multi_cell(0, 8, _t(bloque[1]), new_x="LMARGIN", new_y="NEXT")
            pdf.ln(2)
        elif tipo == "subtitulo":
            pdf.ln(2)
            pdf.set_font("Helvetica", "B", 12)
            pdf.multi_cell(0, 7, _t(bloque[1]), new_x="LMARGIN", new_y="NEXT")
        elif tipo == "parrafo":
            pdf.set_font("Helvetica", "", 10)
            pdf.multi_cell(0, 5.5, _t(bloque[1]), new_x="LMARGIN", new_y="NEXT")
            pdf.ln(1)
        elif tipo == "semaforo":
            r, g, b = bloque[1]
            pdf.set_fill_color(r, g, b)
            pdf.set_text_color(255, 255, 255)
            pdf.set_font("Helvetica", "B", 12)
            pdf.multi_cell(0, 9, _t(bloque[2]), fill=True, align="C", new_x="LMARGIN", new_y="NEXT")
            pdf.set_text_color(15, 27, 51)
            pdf.ln(2)
        elif tipo == "tabla":
            _, columnas, filas, anchos = bloque
            pdf.set_font("Helvetica", "", 8.5)
            with pdf.table(col_widths=anchos, text_align="LEFT", line_height=4.8, first_row_as_headings=True) as tabla:
                fila = tabla.row()
                for c in columnas:
                    fila.cell(_t(c))
                for datos in filas:
                    fila = tabla.row()
                    for valor in datos:
                        fila.cell(_t(valor))
            pdf.ln(2)
        elif tipo == "salto":
            pdf.add_page()
    return bytes(pdf.output())


PROHIBIDOS_HOJA = set("[]:*?/\\")


def xlsx_bytes(hojas):
    """hojas: lista de (titulo, columnas, filas)."""
    libro = Workbook()
    libro.remove(libro.active)
    for titulo, columnas, filas in hojas:
        limpio = "".join(c for c in titulo if c not in PROHIBIDOS_HOJA)[:31].strip() or "Hoja"
        hoja = libro.create_sheet(title=limpio)
        hoja.append(list(columnas))
        for celda in hoja[1]:
            celda.font = Font(bold=True, color="FFFFFF")
            celda.fill = PatternFill("solid", fgColor="0E74C9")
            celda.alignment = Alignment(vertical="center", wrap_text=True)
        for fila in filas:
            hoja.append(["" if v is None else _celda(v, ("=",)) for v in fila])
        for i, columna in enumerate(columnas, start=1):
            largo = max([len(str(columna))] + [len(str(f[i - 1])) for f in filas if i - 1 < len(f)] or [10])
            hoja.column_dimensions[hoja.cell(row=1, column=i).column_letter].width = min(60, max(10, largo + 2))
        hoja.freeze_panes = "A2"
    buffer = io.BytesIO()
    libro.save(buffer)
    return buffer.getvalue()


def csv_bytes(columnas, filas):
    buffer = io.StringIO()
    escritor = csv.writer(buffer)
    escritor.writerow(columnas)
    escritor.writerows([[_celda(v) for v in fila] for fila in filas])
    return ("﻿" + buffer.getvalue()).encode("utf-8")


def respuesta_archivo(contenido, nombre, formato):
    resp = HttpResponse(contenido, content_type=TIPOS[formato])
    resp["Content-Disposition"] = f'attachment; filename="{nombre}"'
    return resp


def exportar_tabla(nombre_base, titulo, columnas, filas, formato, anchos=None, intro=""):
    """Atajo para exportar una sola tabla en el formato pedido (?formato=pdf|xlsx|csv)."""
    fecha = timezone.localdate().isoformat()
    if formato == "pdf":
        bloques = [("titulo", titulo)]
        if intro:
            bloques.append(("parrafo", intro))
        bloques.append(("tabla", columnas, filas, anchos))
        return respuesta_archivo(pdf_bytes(titulo, bloques), f"{nombre_base}_{fecha}.pdf", "pdf")
    if formato == "xlsx":
        return respuesta_archivo(xlsx_bytes([(titulo, columnas, filas)]), f"{nombre_base}_{fecha}.xlsx", "xlsx")
    return respuesta_archivo(csv_bytes(columnas, filas), f"{nombre_base}_{fecha}.csv", "csv")
