"""
Sección de reportes (Reto Cifrado de Información Sensible en PCs).

Lee la tabla equipos_raw que cargó la App 1 en PostgreSQL, aplica los filtros
de país y sistema operativo, y genera un reporte escrito en PDF con formato
institucional (sin gráficas).

- leer_equipos():         trae la tabla de PostgreSQL
- opciones_filtros(df):   listas de países y sistemas operativos para los filtros
- generar_reporte_pdf():  regresa el PDF en bytes, listo para descargarse

El dashboard (App 2) solo tiene que llamar a estas funciones con los filtros elegidos.
Logo: guardar el archivo oficial en reportes/assets/logo_femsa.png
"""
import io
import os
import re
import matplotlib.pyplot as plt
from datetime import datetime
from pathlib import Path

import pandas as pd
import psycopg2
from reportlab import rl_config
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.pdfgen import canvas as rl_canvas
from reportlab.platypus import (Image, KeepTogether, PageBreak, Paragraph, SimpleDocTemplate,
                                Spacer, Table, TableStyle)

try:  # en la compu de desarrollo la contraseña está en el .env; en Docker la pone Docker
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parent.parent / ".env")
except ImportError:
    pass

rl_config.invariant = 1  # mismo contenido = mismo PDF (determinista)

SIN_PAIS = "Sin país asignado"

MENSAJES = {
    "TPM not used for protection of OS volume, but is required by policy": "Cifrado sin TPM (lo exige la política)",
    "Fixed Drive not encrypted": "Disco secundario sin cifrar",
    "Encryption method of OS Volume is different than that set by policy": "Método de cifrado distinto a la política",
}


# ---------------------------------------------------------------- lectura

def leer_equipos():
    """Trae la tabla equipos_raw que cargó la App 1."""
    conn = psycopg2.connect(
        user=os.getenv("DB_USER", "postgres"),
        password=os.getenv("DB_PASSWORD"),
        host=os.getenv("DB_HOST", "localhost"),
        port=os.getenv("DB_PORT", "5432"),
        dbname=os.getenv("DB_NAME", "discos_duros"),
    )
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM equipos_raw ORDER BY equipo_id;")
            columnas = [d[0] for d in cur.description]
            filas = cur.fetchall()
    finally:
        conn.close()
    df = pd.DataFrame(filas, columns=columnas)
    return df.apply(lambda col: col.fillna("").astype(str).str.strip())


# ---------------------------------------------------------------- cálculos

def _inactivo(banda):
    """True si la banda de recencia es de más de 90 días (ej. '91-180 días', '>180 días')."""
    numero = re.search(r"\d+", banda or "")
    if not numero:
        return False
    return banda.strip().startswith(">") or int(numero.group()) >= 91


def _motivos(fila):
    motivos = []
    if not fila["en_mdm_b"]:
        motivos.append("No reporta al MDM")
    if fila["no_cifrado_b"]:
        motivos.append("No cifrado")
    elif fila["en_mdm_b"] and not fila["cifrado_b"]:
        motivos.append("Sin dato de cifrado")
    if fila["tecnologia_cifrado"] in MENSAJES:
        motivos.append(MENSAJES[fila["tecnologia_cifrado"]])
    if fila["inactivo_b"]:
        motivos.append("Más de 90 días sin iniciar sesión")
    if fila["sistema_operativo"] == "Windows" and not fila["en_ad_b"]:
        motivos.append("No está en el Directorio Activo")
    return motivos


def preparar(df):
    """Agrega las columnas que usa el reporte (no modifica la tabla original)."""
    t = df.copy()
    t["pais_reporte"] = t["pais"].replace({"No disponible": SIN_PAIS, "": SIN_PAIS})
    t["en_mdm_b"] = t["en_mdm"].eq("Sí")
    t["en_ad_b"] = t["en_ad"].eq("Sí")
    t["cifrado_b"] = t["estado_cifrado"].eq("Encrypted")
    t["no_cifrado_b"] = t["estado_cifrado"].eq("Not encrypted")
    t["inactivo_b"] = t["banda_recencia"].apply(_inactivo)
    t["motivos"] = t.apply(_motivos, axis=1)
    return t


def opciones_filtros(df):
    """Listas de países y sistemas operativos para los filtros."""
    t = preparar(df)
    return sorted(t["pais_reporte"].unique()), sorted(t["sistema_operativo"].unique())


def filtrar(t, paises=None, sistemas=None):
    """Aplica los filtros a una tabla ya preparada. Lista vacía o None = todos."""
    if paises:
        t = t[t["pais_reporte"].isin(paises)]
    if sistemas:
        t = t[t["sistema_operativo"].isin(sistemas)]
    return t


def _pct(parte, total):
    return f"{parte / total * 100:.1f}%" if total else "0%"


def _cuenta(n, singular, plural):
    return f"{n:,} {singular if n == 1 else plural}"


def _numeros(t):
    en_mdm = int(t["en_mdm_b"].sum())
    return {
        "total": len(t),
        "en_mdm": en_mdm,
        "cifrados": int((t["en_mdm_b"] & t["cifrado_b"]).sum()),
        "no_cifrados": int(t["no_cifrado_b"].sum()),
        "sin_evidencia": int((~t["cifrado_b"] & ~t["no_cifrado_b"]).sum()),
        "inactivos": int(t["inactivo_b"].sum()),
        "con_desv": int(t["motivos"].map(len).gt(0).sum()),
    }


def _parrafo_grupo(t):
    """Texto con los resultados de un grupo de equipos (todos, un país o un SO)."""
    n = _numeros(t)
    texto = (f"Se analizaron {_cuenta(n['total'], 'equipo', 'equipos')}. "
             f"{n['en_mdm']:,} ({_pct(n['en_mdm'], n['total'])}) reportan al MDM y "
             f"{n['total'] - n['en_mdm']:,} no lo hacen. ")
    if n["en_mdm"]:
        texto += (f"Dentro del MDM, {n['cifrados']:,} equipos están cifrados, lo que equivale a "
                  f"{_pct(n['cifrados'], n['en_mdm'])} de los equipos gestionados. ")
    texto += (f"{_cuenta(n['no_cifrados'], 'equipo está', 'equipos están')} sin cifrar y "
              f"{_cuenta(n['sin_evidencia'], 'equipo no tiene', 'equipos no tienen')} evidencia de cifrado. "
              f"{_cuenta(n['inactivos'], 'equipo lleva', 'equipos llevan')} más de 90 días sin iniciar sesión. "
              f"En total, {_cuenta(n['con_desv'], 'equipo presenta', 'equipos presentan')} al menos una desviación.")
    return texto


# ---------------------------------------------------------------- diseño

ROJO = colors.HexColor("#D52B1E")       # rojo institucional
ROJO_CLARO = colors.HexColor("#FBE9E7")
OSCURO = colors.HexColor("#2B2B2B")
GRIS = colors.HexColor("#6E6E6E")
GRIS_LINEA = colors.HexColor("#D0D0D0")
GRIS_CLARO = colors.HexColor("#F4F4F4")
BLANCO = colors.white

LOGO = Path(__file__).resolve().parent / "assets" / "logo_femsa.png"
ANCHO_UTIL = 17.6 * cm

MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto",
         "septiembre", "octubre", "noviembre", "diciembre"]


def _fecha_larga(fecha):
    return f"{fecha.day} de {MESES[fecha.month - 1]} de {fecha.year}"


class _CanvasNumerado(rl_canvas.Canvas):
    """Dibuja encabezado y pie en cada hoja, con 'Página X de Y'."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._paginas = []

    def showPage(self):
        self._paginas.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        total = len(self._paginas)
        for estado in self._paginas:
            self.__dict__.update(estado)
            self._dibujar_marco(total)
            super().showPage()
        super().save()

    def _dibujar_marco(self, total):
        ancho, alto = letter
        self.saveState()
        # franja roja superior
        self.setFillColor(ROJO)
        self.rect(0, alto - 0.35 * cm, ancho, 0.35 * cm, stroke=0, fill=1)
        # logo a la izquierda
        if LOGO.exists():
            self.drawImage(str(LOGO), 2 * cm, alto - 2.25 * cm, width=4 * cm, height=1.4 * cm,
                           preserveAspectRatio=True, anchor="sw", mask="auto")
        else:
            self.setFillColor(OSCURO)
            self.setFont("Helvetica-Bold", 11)
            self.drawString(2 * cm, alto - 1.75 * cm, "Auditoría Interna")
        # área a la derecha
        self.setFillColor(OSCURO)
        self.setFont("Helvetica-Bold", 8.5)
        self.drawRightString(ancho - 2 * cm, alto - 1.35 * cm, "AUDITORÍA INTERNA")
        self.setFillColor(GRIS)
        self.setFont("Helvetica", 8)
        self.drawRightString(ancho - 2 * cm, alto - 1.75 * cm, "Monitoreo de cifrado de equipos de cómputo")
        # línea bajo el encabezado
        self.setStrokeColor(GRIS_LINEA)
        self.setLineWidth(0.6)
        self.line(2 * cm, alto - 2.55 * cm, ancho - 2 * cm, alto - 2.55 * cm)
        # pie de página
        self.setStrokeColor(ROJO)
        self.setLineWidth(1)
        self.line(2 * cm, 1.6 * cm, ancho - 2 * cm, 1.6 * cm)
        self.setFillColor(GRIS)
        self.setFont("Helvetica", 7.5)
        self.drawString(2 * cm, 1.1 * cm, "Documento confidencial. Uso interno de Auditoría.")
        self.drawRightString(ancho - 2 * cm, 1.1 * cm, f"Página {self._pageNumber} de {total}")
        self.restoreState()


def _estilos():
    base = getSampleStyleSheet()["Normal"]
    e = {}
    e["normal"] = ParagraphStyle("normal", parent=base, fontName="Helvetica", fontSize=9.8,
                                 leading=14.5, alignment=4, textColor=OSCURO, spaceAfter=7)
    e["titulo"] = ParagraphStyle("titulo", parent=base, fontName="Helvetica-Bold", fontSize=19,
                                 leading=23, textColor=ROJO, spaceBefore=2, spaceAfter=3)
    e["subtitulo"] = ParagraphStyle("subtitulo", parent=base, fontName="Helvetica", fontSize=11,
                                    leading=14, textColor=GRIS, spaceAfter=12)
    e["seccion"] = ParagraphStyle("seccion", parent=base, fontName="Helvetica-Bold", fontSize=12,
                                  leading=15, textColor=OSCURO)
    e["grupo"] = ParagraphStyle("grupo", parent=base, fontName="Helvetica-Bold", fontSize=10,
                                leading=13, textColor=ROJO, spaceBefore=6, spaceAfter=2)
    e["ficha_etq"] = ParagraphStyle("ficha_etq", parent=base, fontName="Helvetica-Bold", fontSize=8,
                                    leading=10, textColor=GRIS)
    e["ficha_val"] = ParagraphStyle("ficha_val", parent=base, fontName="Helvetica", fontSize=9,
                                    leading=11, textColor=OSCURO)
    e["kpi_num"] = ParagraphStyle("kpi_num", parent=base, fontName="Helvetica-Bold", fontSize=18,
                                  leading=21, textColor=ROJO, alignment=1)
    e["kpi_etq"] = ParagraphStyle("kpi_etq", parent=base, fontName="Helvetica", fontSize=7.8,
                                  leading=9.5, textColor=GRIS, alignment=1)
    e["barra"] = ParagraphStyle("barra", parent=base, fontName="Helvetica-Bold", fontSize=8.5,
                                leading=10, textColor=BLANCO, alignment=1)
    e["celda"] = ParagraphStyle("celda", parent=base, fontName="Helvetica", fontSize=8,
                                leading=10, textColor=OSCURO)
    e["celda_der"] = ParagraphStyle("celda_der", parent=e["celda"], alignment=2)
    e["celda_enc"] = ParagraphStyle("celda_enc", parent=e["celda"], fontName="Helvetica-Bold")
    e["celda_enc_der"] = ParagraphStyle("celda_enc_der", parent=e["celda_enc"], alignment=2)
    e["nota"] = ParagraphStyle("nota", parent=base, fontName="Helvetica-Oblique", fontSize=7.8,
                               leading=10, textColor=GRIS, spaceBefore=4)
    return e


def _seccion(numero, texto, e):
    """Título de sección: número rojo, texto oscuro y línea roja debajo."""
    t = Table([[Paragraph(f'<font color="#D52B1E">{numero}</font>&nbsp;&nbsp;{texto}', e["seccion"])]],
              colWidths=[ANCHO_UTIL])
    t.setStyle(TableStyle([
        ("LINEBELOW", (0, 0), (-1, -1), 1.2, ROJO),
        ("LEFTPADDING", (0, 0), (-1, -1), 0), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    return [Spacer(1, 10), t, Spacer(1, 8)]


def _ficha(fecha, texto_paises, texto_so, total, e):
    """Recuadro gris con los datos del reporte y borde rojo a la izquierda."""
    datos = [("FECHA", _fecha_larga(fecha)), ("PAÍSES", texto_paises),
             ("SISTEMAS OPERATIVOS", texto_so), ("EQUIPOS INCLUIDOS", f"{total:,}")]
    celdas = [[Paragraph(etq, e["ficha_etq"]) for etq, _ in datos],
              [Paragraph(val, e["ficha_val"]) for _, val in datos]]
    t = Table(celdas, colWidths=[3.6 * cm, 5.6 * cm, 4.6 * cm, 3.8 * cm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), GRIS_CLARO),
        ("LINEBEFORE", (0, 0), (0, -1), 3, ROJO),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, 0), 7), ("BOTTOMPADDING", (0, -1), (-1, -1), 7),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
    ]))
    return t


def _tarjetas(n, e):
    """Fila de cuatro indicadores principales."""
    datos = [(f"{n['total']:,}", "Equipos analizados"),
             (_pct(n["en_mdm"], n["total"]), "Reportan al MDM"),
             (_pct(n["cifrados"], n["en_mdm"]), "Cifrados dentro del MDM"),
             (f"{n['con_desv']:,}", "Equipos con desviación")]
    fila = [[Paragraph(num, e["kpi_num"]), ] for num, _ in datos]
    celdas = [[Paragraph(num, e["kpi_num"]) for num, _ in datos],
              [Paragraph(etq, e["kpi_etq"]) for _, etq in datos]]
    ancho = ANCHO_UTIL / 4
    t = Table(celdas, colWidths=[ancho] * 4)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), BLANCO),
        ("BOX", (0, 0), (-1, -1), 0.6, GRIS_LINEA),
        ("LINEBEFORE", (1, 0), (-1, -1), 0.6, GRIS_LINEA),
        ("LINEABOVE", (0, 0), (-1, 0), 2.5, ROJO),
        ("TOPPADDING", (0, 0), (-1, 0), 9), ("BOTTOMPADDING", (0, -1), (-1, -1), 9),
    ]))
    return t


def _tabla(filas, anchos, e, titulo=None, total=False):
    """Tabla con barra oscura de título, encabezado gris y renglones alternados."""
    cuerpo = []
    estilo = []
    inicio = 0
    if titulo:
        cuerpo.append([Paragraph(titulo.upper(), e["barra"])] + [""] * (len(anchos) - 1))
        estilo += [("SPAN", (0, 0), (-1, 0)), ("BACKGROUND", (0, 0), (-1, 0), OSCURO)]
        inicio = 1
    cuerpo += filas
    enc = inicio
    estilo += [
        ("BACKGROUND", (0, enc), (-1, enc), GRIS_CLARO),
        ("LINEBELOW", (0, enc), (-1, enc), 0.8, OSCURO),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]
    ultimo = len(cuerpo) - (1 if total else 0)
    for i in range(enc + 1, ultimo):
        if (i - enc) % 2 == 0:
            estilo.append(("BACKGROUND", (0, i), (-1, i), GRIS_CLARO))
        estilo.append(("LINEBELOW", (0, i), (-1, i), 0.3, GRIS_LINEA))
    if total:
        estilo += [("BACKGROUND", (0, -1), (-1, -1), ROJO_CLARO),
                   ("LINEABOVE", (0, -1), (-1, -1), 0.8, ROJO)]
    t = Table(cuerpo, colWidths=anchos, repeatRows=enc + 1)
    t.setStyle(TableStyle(estilo))
    return t


def _fila_resumen(nombre, t, e, negrita=False):
    n = _numeros(t)
    izq, der = (e["celda_enc"], e["celda_enc_der"]) if negrita else (e["celda"], e["celda_der"])
    valores = [f"{n['total']:,}", _pct(n["en_mdm"], n["total"]), _pct(n["cifrados"], n["en_mdm"]),
               f"{n['no_cifrados']:,}", f"{n['inactivos']:,}", f"{n['con_desv']:,}"]
    return [Paragraph(nombre, izq)] + [Paragraph(v, der) for v in valores]


# ---------------------------------------------------------------- PDF

def generar_reporte_pdf(df, paises=None, sistemas=None, fecha=None):
    """
    df: tabla equipos_raw (de leer_equipos()).
    paises / sistemas: lo que eligió el usuario. Vacío o None = todos.
    fecha: datetime a mostrar (por ejemplo, la fecha de la carga). Por defecto, hoy.
    Regresa el PDF en bytes.
    """
    fecha = fecha or datetime.now()
    t = filtrar(preparar(df), paises, sistemas)
    if t.empty:
        raise ValueError("No hay equipos con los filtros elegidos.")

    e = _estilos()
    n = _numeros(t)
    texto_paises = ", ".join(paises) if paises else "Todos"
    texto_so = ", ".join(sistemas) if sistemas else "Todos"
    tipo = f"Reporte de {paises[0]}" if paises and len(paises) == 1 else "Reporte general"

    h = [Paragraph("Reporte de Cifrado de Equipos de Cómputo", e["titulo"]),
         Paragraph(tipo, e["subtitulo"]),
         _ficha(fecha, texto_paises, texto_so, n["total"], e),
         Spacer(1, 12),
         _tarjetas(n, e)]

    # 1. Alcance
    h += _seccion("1.", "Alcance y criterios", e)
    h.append(Paragraph(
        "Este reporte presenta el estado de cifrado de los equipos de cómputo incluidos en los filtros "
        "seleccionados. Un equipo presenta una desviación cuando no reporta al MDM, no está cifrado, no "
        "tiene dato de cifrado, tiene un mensaje de cifrado distinto al esperado por la política, lleva más "
        "de 90 días sin iniciar sesión o, en el caso de Windows, no está en el Directorio Activo. El "
        "porcentaje de cifrado se calcula solo con los equipos que reportan al MDM.", e["normal"]))

    # 2. Resultados generales
    h += _seccion("2.", "Resultados generales", e)
    h.append(Paragraph(_parrafo_grupo(t), e["normal"]))
    conteo = pd.Series([m for lista in t["motivos"] for m in lista], dtype=object).value_counts()
    if not conteo.empty:
        filas = [[Paragraph("Desviación", e["celda_enc"]), Paragraph("Equipos", e["celda_enc_der"]),
                  Paragraph("% del total", e["celda_enc_der"])]]
        for motivo, cantidad in sorted(conteo.items(), key=lambda x: (-x[1], x[0])):
            filas.append([Paragraph(motivo, e["celda"]), Paragraph(f"{cantidad:,}", e["celda_der"]),
                          Paragraph(_pct(cantidad, n["total"]), e["celda_der"])])
        h += [Spacer(1, 4),
              KeepTogether(_tabla(filas, [11.6 * cm, 3 * cm, 3 * cm], e, titulo="Desviaciones encontradas")),
              Paragraph("Un equipo puede presentar más de una desviación.", e["nota"])]

    # 3. Resultados por país
    lista_paises = sorted(t["pais_reporte"].unique())
    filas = [[Paragraph(c, e["celda_enc"] if i == 0 else e["celda_enc_der"]) for i, c in enumerate(
        ["País", "Equipos", "En MDM", "Cifrado en MDM", "Sin cifrar", "Inactivos +90 días", "Con desviación"])]]
    for pais in lista_paises:
        filas.append(_fila_resumen(pais, t[t["pais_reporte"] == pais], e))
    filas.append(_fila_resumen("TOTAL", t, e, negrita=True))
    num = 3
    h += _seccion(f"{num}.", "Resultados por país", e)
    h.append(KeepTogether(_tabla(filas, [4.1 * cm, 1.8 * cm, 2 * cm, 2.6 * cm, 2 * cm, 2.6 * cm, 2.5 * cm],
                                 e, titulo="Resumen por país", total=True)))
    h.append(Spacer(1, 8))
    if len(lista_paises) > 1:
        for pais in lista_paises:
            h += [Paragraph(pais, e["grupo"]),
                  Paragraph(_parrafo_grupo(t[t["pais_reporte"] == pais]), e["normal"])]
    if SIN_PAIS in lista_paises:
        h.append(Paragraph("Los equipos sin país asignado no tienen país en las fuentes, por lo que no "
                           "aparecen en los reportes por país y deben revisarse en el reporte general.",
                           e["nota"]))
    num += 1

    # 4. Resultados por sistema operativo
    lista_so = sorted(t["sistema_operativo"].unique())
    if len(lista_so) > 1:
        h += _seccion(f"{num}.", "Resultados por sistema operativo", e)
        for so in lista_so:
            h += [Paragraph(so, e["grupo"]),
                  Paragraph(_parrafo_grupo(t[t["sistema_operativo"] == so]), e["normal"])]

    # Anexo
    desv = t[t["motivos"].map(len).gt(0)].sort_values(["pais_reporte", "equipo_id"], kind="mergesort")
    h.append(PageBreak())
    h += _seccion("A.", "Anexo. Equipos con desviaciones", e)
    if desv.empty:
        h.append(Paragraph("No se encontraron equipos con desviaciones.", e["normal"]))
    else:
        filas = [[Paragraph(c, e["celda_enc"]) for c in ("Equipo", "País", "Sistema operativo", "Desviación")]]
        for _, r in desv.iterrows():
            filas.append([Paragraph(r["equipo_id"], e["celda"]), Paragraph(r["pais_reporte"], e["celda"]),
                          Paragraph(r["sistema_operativo"], e["celda"]),
                          Paragraph("; ".join(r["motivos"]), e["celda"])])
        h.append(_tabla(filas, [3 * cm, 3.3 * cm, 2.8 * cm, 8.5 * cm], e,
                        titulo=f"{len(desv):,} equipos con al menos una desviación"))

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, leftMargin=2 * cm, rightMargin=2 * cm,
                            topMargin=3.1 * cm, bottomMargin=2.2 * cm,
                            title="Reporte de cifrado de equipos", author="Auditoría Interna")
    doc.build(h, canvasmaker=_CanvasNumerado)
    return buffer.getvalue()


def generar_reporte_tecnico_pdf(df, paises=None, sistemas=None, fecha=None,
                                df_filtrado=False):
    """Genera un PDF técnico con indicadores, resúmenes y detalle de equipos."""
    fecha = fecha or datetime.now()
    preparado = preparar(df)
    t = preparado if df_filtrado else filtrar(preparado, paises, sistemas)
    if t.empty:
        raise ValueError("No hay equipos con los filtros elegidos.")

    e = _estilos()
    n = _numeros(t)
    texto_paises = ", ".join(paises) if paises else "Todos"
    texto_so = ", ".join(sistemas) if sistemas else "Todos"

    h = [
        Paragraph("Reporte Técnico de Cifrado de Equipos", e["titulo"]),
        Paragraph("Detalle operativo y trazabilidad de equipos", e["subtitulo"]),
        _ficha(fecha, texto_paises, texto_so, n["total"], e),
        Spacer(1, 12),
        _tarjetas(n, e),
    ]

    h += _seccion("1.", "Resumen técnico", e)
    h.append(Paragraph(_parrafo_grupo(t), e["normal"]))

    h += _seccion("2.", "Resumen por país", e)
    filas = [[
        Paragraph(c, e["celda_enc"] if i == 0 else e["celda_enc_der"])
        for i, c in enumerate(("País", "Equipos", "En MDM", "Cifrados", "Sin cifrar", "Con desviación"))
    ]]
    for pais in sorted(t["pais_reporte"].unique()):
        grupo = t[t["pais_reporte"] == pais]
        ng = _numeros(grupo)
        valores = [pais, f"{ng['total']:,}", f"{ng['en_mdm']:,}", f"{ng['cifrados']:,}",
                   f"{ng['no_cifrados']:,}", f"{ng['con_desv']:,}"]
        filas.append([
            Paragraph(valores[0], e["celda"]),
            *[Paragraph(valor, e["celda_der"]) for valor in valores[1:]],
        ])
    h.append(_tabla(filas, [5 * cm, 2.2 * cm, 2.2 * cm, 2.2 * cm, 2.7 * cm, 3 * cm], e,
                    titulo="Indicadores por país"))

    h += _seccion("3.", "Detalle de equipos", e)
    columnas = [
        ("equipo_id", "Equipo"),
        ("pais_reporte", "País"),
        ("sistema_operativo", "SO"),
        ("en_mdm", "MDM"),
        ("estado_cifrado", "Cifrado"),
        ("tecnologia_cifrado", "Tecnología"),
        ("banda_recencia", "Recencia"),
        ("estado_cuenta", "Cuenta"),
    ]
    filas = [[Paragraph(titulo, e["celda_enc"]) for _, titulo in columnas]]
    for _, fila in t.head(500).sort_values(["pais_reporte", "equipo_id"], kind="mergesort").iterrows():
        valores = [str(fila.get(columna, "") or "") for columna, _ in columnas]
        filas.append([
            Paragraph(valores[0], e["celda"]),
            *[Paragraph(valor, e["celda"]) for valor in valores[1:]],
        ])
    h.append(_tabla(
        filas,
        [2.3 * cm, 2.5 * cm, 2.3 * cm, 1.5 * cm, 2.2 * cm, 3 * cm, 2.3 * cm, 1.5 * cm],
        e,
        titulo=f"Detalle técnico ({min(len(t), 500):,} de {len(t):,} equipos)",
    ))
    if len(t) > 500:
        h.append(Paragraph(
            "Se muestran los primeros 500 equipos para mantener el PDF legible.",
            e["nota"],
        ))

    h += _seccion("4.", "Equipos con desviaciones", e)
    desviaciones = t[t["motivos"].map(len).gt(0)].sort_values(
        ["pais_reporte", "equipo_id"], kind="mergesort")
    if desviaciones.empty:
        h.append(Paragraph("No se encontraron equipos con desviaciones.", e["normal"]))
    else:
        filas = [[Paragraph(c, e["celda_enc"]) for c in (
            "Equipo", "País", "Sistema operativo", "Desviación")]]
        for _, fila in desviaciones.iterrows():
            filas.append([
                Paragraph(str(fila["equipo_id"]), e["celda"]),
                Paragraph(str(fila["pais_reporte"]), e["celda"]),
                Paragraph(str(fila["sistema_operativo"]), e["celda"]),
                Paragraph("; ".join(fila["motivos"]), e["celda"]),
            ])
        h.append(_tabla(
            filas,
            [3 * cm, 3.3 * cm, 2.8 * cm, 8.5 * cm],
            e,
            titulo=f"{len(desviaciones):,} equipos con al menos una desviación",
        ))

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        leftMargin=2 * cm,
        rightMargin=2 * cm,
        topMargin=3.1 * cm,
        bottomMargin=2.2 * cm,
        title="Reporte técnico de cifrado de equipos",
        author="Auditoría Interna",
    )
    doc.build(h, canvasmaker=_CanvasNumerado)
    return buffer.getvalue()


def _grafica_png(titulo, tipo, df, columna=None, columna2=None):
    """Convierte una gráfica del dashboard en una imagen PNG para el reporte ejecutivo."""
    fig, ax = plt.subplots(figsize=(7.2, 3.8), dpi=150)
    fig.patch.set_facecolor("white")
    ax.set_facecolor("white")
    colores = ["#C8102E", "#3D4A5C", "#E8A317", "#8A9BB0", "#7A1F2B", "#C9B79C"]

    if tipo == "dona" and columna:
        conteo = df[columna].fillna("Sin dato").astype(str).value_counts()
        ax.pie(conteo.values, labels=conteo.index, autopct="%1.1f%%",
               colors=colores, startangle=90, textprops={"fontsize": 8})
        centro = plt.Circle((0, 0), 0.55, fc="white")
        ax.add_artist(centro)

    elif tipo == "barras" and columna:
        conteo = df[columna].fillna("Sin dato").astype(str).value_counts().head(12)
        ax.bar(range(len(conteo)), conteo.values, color=colores[0])
        ax.set_xticks(range(len(conteo)))
        ax.set_xticklabels([str(v)[:18] for v in conteo.index], rotation=35,
                           ha="right", fontsize=7)
        ax.set_ylabel("Equipos", fontsize=8)
        ax.grid(axis="y", alpha=0.2)
        for i, valor in enumerate(conteo.values):
            ax.text(i, valor, f"{valor:,}", ha="center", va="bottom", fontsize=7)

    elif tipo == "apiladas" and columna and columna2:
        tabla = pd.crosstab(df[columna].fillna("Sin dato"),
                            df[columna2].fillna("Sin dato"), normalize="index") * 100
        izquierda = 0
        for i, categoria in enumerate(tabla.columns):
            valores = tabla[categoria].values
            ax.barh(range(len(tabla.index)), valores, left=izquierda,
                    label=str(categoria)[:24], color=colores[i % len(colores)])
            izquierda += valores
        ax.set_yticks(range(len(tabla.index)))
        ax.set_yticklabels([str(v)[:22] for v in tabla.index], fontsize=7)
        ax.set_xlabel("% de equipos", fontsize=8)
        ax.invert_yaxis()
        ax.legend(loc="lower center", bbox_to_anchor=(0.5, -0.42),
                  ncol=2, fontsize=7, frameon=False)
        ax.grid(axis="x", alpha=0.2)

    elif tipo == "histograma":
        valores = pd.to_numeric(df.get("antiguedad_meses"), errors="coerce").dropna()
        ax.hist(valores, bins=30, color=colores[0], edgecolor="white")
        ax.set_xlabel("Antigüedad (meses)", fontsize=8)
        ax.set_ylabel("Equipos", fontsize=8)
        ax.grid(axis="y", alpha=0.2)

    ax.set_title(titulo, fontsize=10, fontweight="bold", pad=8)
    ax.tick_params(labelsize=8)
    fig.tight_layout()
    buffer = io.BytesIO()
    fig.savefig(buffer, format="png", bbox_inches="tight")
    plt.close(fig)
    buffer.seek(0)
    return buffer


def _imagen_grafica(titulo, tipo, df, columna=None, columna2=None, ancho=8.4):
    buffer = _grafica_png(titulo, tipo, df, columna, columna2)
    return Image(buffer, width=ancho * cm, height=(ancho * 0.58) * cm)


def generar_reporte_ejecutivo_pdf(df, paises=None, sistemas=None, fecha=None,
                                  df_filtrado=False):
    """Reporte ejecutivo visual con indicadores y las gráficas del dashboard."""
    fecha = fecha or datetime.now()
    preparado = preparar(df)
    t = preparado if df_filtrado else filtrar(preparado, paises, sistemas)
    if t.empty:
        raise ValueError("No hay equipos con los filtros elegidos.")

    e = _estilos()
    n = _numeros(t)
    texto_paises = ", ".join(paises) if paises else "Todos"
    texto_so = ", ".join(sistemas) if sistemas else "Todos"

    h = [
        Paragraph("Reporte Ejecutivo de Cifrado de Equipos", e["titulo"]),
        Paragraph("Resumen visual para dirección y comités", e["subtitulo"]),
        _ficha(fecha, texto_paises, texto_so, n["total"], e),
        Spacer(1, 12),
        _tarjetas(n, e),
    ]

    h += _seccion("1.", "Resumen ejecutivo", e)
    h.append(Paragraph(_parrafo_grupo(t), e["normal"]))

    h += _seccion("2.", "Cifrado y cumplimiento", e)
    g1 = _imagen_grafica("Estado de cifrado", "dona", t, "estado_cifrado")
    g2 = _imagen_grafica("Estado de cumplimiento", "dona", t, "estado_cumplimiento")
    h.append(Table([[g1, g2]], colWidths=[8.8 * cm, 8.8 * cm]))

    h += _seccion("3.", "Distribución geográfica", e)
    g1 = _imagen_grafica("Equipos por país", "barras", t, "pais")
    g2 = _imagen_grafica("Cifrado por país", "apiladas", t, "pais", "estado_cifrado")
    h.append(Table([[g1, g2]], colWidths=[8.8 * cm, 8.8 * cm]))

    h += _seccion("4.", "Sistema operativo y tecnología", e)
    g1 = _imagen_grafica("Cifrado por sistema operativo", "apiladas",
                         t, "sistema_operativo", "estado_cifrado")
    g2 = _imagen_grafica("Tecnología de cifrado", "barras", t, "tecnologia_cifrado")
    h.append(Table([[g1, g2]], colWidths=[8.8 * cm, 8.8 * cm]))

    h += _seccion("5.", "Hardware y antigüedad", e)
    g1 = _imagen_grafica("Estado de TPM", "barras", t, "estado_tpm")
    g2 = _imagen_grafica("Antigüedad de los equipos", "histograma", t)
    h.append(Table([[g1, g2]], colWidths=[8.8 * cm, 8.8 * cm]))

    h.append(PageBreak())
    h += _seccion("6.", "Conclusión ejecutiva", e)
    con_desv = n["con_desv"]
    cifrado = n["cifrados"]
    en_mdm = n["en_mdm"]
    h.append(Paragraph(
        f"Con {_cuenta(n['total'], 'equipo incluido', 'equipos incluidos')} en el alcance "
        f"seleccionado, {_cuenta(con_desv, 'equipo presenta', 'equipos presentan')} al menos una "
        f"desviación. De los {_cuenta(en_mdm, ' equipo gestionado por MDM', ' equipos gestionados por MDM')}, "
        f"{_cuenta(cifrado, ' equipo está cifrado', ' equipos están cifrados')}. "
        "Se recomienda priorizar la atención de equipos sin cifrado, sin reporte al MDM y con recencia superior a 90 días.",
        e["normal"],
    ))

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        leftMargin=2 * cm,
        rightMargin=2 * cm,
        topMargin=3.1 * cm,
        bottomMargin=2.2 * cm,
        title="Reporte ejecutivo de cifrado de equipos",
        author="Auditoría Interna",
    )
    doc.build(h, canvasmaker=_CanvasNumerado)
    return buffer.getvalue()