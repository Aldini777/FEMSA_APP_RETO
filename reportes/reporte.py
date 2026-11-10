"""
Sección de reportes (Reto Cifrado de Información Sensible en PCs).

Lee la tabla equipos_raw que cargó la App 1 en PostgreSQL, aplica los filtros
de país y sistema operativo, y genera un reporte escrito en PDF (sin gráficas).

- leer_equipos():         trae la tabla de PostgreSQL
- opciones_filtros(df):   listas de países y sistemas operativos para los filtros
- generar_reporte_pdf():  regresa el PDF en bytes, listo para descargarse

El dashboard (App 2) solo tiene que llamar a estas funciones con los filtros elegidos.
"""
import io
import os
import re
from datetime import datetime
from pathlib import Path

import pandas as pd
import psycopg2
from reportlab import rl_config
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (PageBreak, Paragraph, SimpleDocTemplate, Spacer,
                                Table, TableStyle)

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


def _parrafo_grupo(t):
    """Texto con los resultados de un grupo de equipos (todos, un país o un SO)."""
    total = len(t)
    en_mdm = int(t["en_mdm_b"].sum())
    fuera_mdm = total - en_mdm
    cifrados = int((t["en_mdm_b"] & t["cifrado_b"]).sum())
    no_cifrados = int(t["no_cifrado_b"].sum())
    sin_evidencia = int((~t["cifrado_b"] & ~t["no_cifrado_b"]).sum())
    inactivos = int(t["inactivo_b"].sum())
    con_desv = int(t["motivos"].map(len).gt(0).sum())

    texto = (f"Se analizaron {_cuenta(total, 'equipo', 'equipos')}. "
             f"{en_mdm:,} ({_pct(en_mdm, total)}) reportan al MDM y {fuera_mdm:,} no lo hacen. ")
    if en_mdm:
        texto += (f"Dentro del MDM, {cifrados:,} equipos están cifrados, lo que equivale a "
                  f"{_pct(cifrados, en_mdm)} de los equipos gestionados. ")
    texto += (f"{_cuenta(no_cifrados, 'equipo está', 'equipos están')} sin cifrar y "
              f"{_cuenta(sin_evidencia, 'equipo no tiene', 'equipos no tienen')} evidencia de cifrado. "
              f"{_cuenta(inactivos, 'equipo lleva', 'equipos llevan')} más de 90 días sin iniciar sesión. "
              f"En total, {_cuenta(con_desv, 'equipo presenta', 'equipos presentan')} al menos una desviación.")
    return texto


# ---------------------------------------------------------------- PDF

def _pie_pagina(canvas, doc):
    canvas.saveState()
    canvas.setFont("Helvetica", 7)
    canvas.drawString(2 * cm, 1.2 * cm, "Documento confidencial. Uso interno de Auditoría.")
    canvas.drawRightString(letter[0] - 2 * cm, 1.2 * cm, f"Página {doc.page}")
    canvas.restoreState()


def generar_reporte_pdf(df, paises=None, sistemas=None, fecha=None):
    """
    df: tabla equipos_raw (de leer_equipos()).
    paises / sistemas: lo que eligió el usuario. Vacío o None = todos.
    fecha: texto con la fecha a mostrar (por ejemplo, la fecha de la carga).
    Regresa el PDF en bytes.
    """
    fecha = fecha or datetime.now().strftime("%d/%m/%Y %H:%M")
    t = filtrar(preparar(df), paises, sistemas)
    if t.empty:
        raise ValueError("No hay equipos con los filtros elegidos.")

    base = getSampleStyleSheet()
    normal = ParagraphStyle("n", parent=base["Normal"], fontSize=10, leading=14, spaceAfter=6)
    chico = ParagraphStyle("c", parent=normal, fontSize=8, leading=10, spaceAfter=0)
    h1 = ParagraphStyle("h1", parent=base["Heading1"], fontSize=15)
    h2 = ParagraphStyle("h2", parent=base["Heading2"], fontSize=12, spaceBefore=10)
    h3 = ParagraphStyle("h3", parent=base["Heading3"], fontSize=10.5, spaceBefore=6)

    texto_paises = ", ".join(paises) if paises else "Todos"
    texto_so = ", ".join(sistemas) if sistemas else "Todos"
    tipo = f"de {paises[0]}" if paises and len(paises) == 1 else "general"

    h = [Paragraph(f"Reporte {tipo} de cifrado de equipos de cómputo", h1),
         Paragraph(f"<b>Países:</b> {texto_paises}<br/><b>Sistemas operativos:</b> {texto_so}"
                   f"<br/><b>Fecha:</b> {fecha}", normal),
         Spacer(1, 6)]

    h.append(Paragraph("1. Alcance y criterios", h2))
    h.append(Paragraph(
        "Este reporte resume el estado de cifrado de los equipos de cómputo incluidos en los filtros "
        "seleccionados. Un equipo presenta una desviación cuando no reporta al MDM, no está cifrado, "
        "no tiene dato de cifrado, tiene un mensaje de cifrado distinto al esperado por la política, "
        "lleva más de 90 días sin iniciar sesión o, en el caso de Windows, no está en el Directorio "
        "Activo. El porcentaje de cifrado se calcula solo con los equipos que reportan al MDM.", normal))

    h.append(Paragraph("2. Resultados generales", h2))
    h.append(Paragraph(_parrafo_grupo(t), normal))

    conteo = pd.Series([m for lista in t["motivos"] for m in lista]).value_counts()
    if not conteo.empty:
        partes = [f"{m[0].lower() + m[1:]} ({n:,})" for m, n in
                  sorted(conteo.items(), key=lambda x: (-x[1], x[0]))]
        h.append(Paragraph("Las desviaciones encontradas, de la más a la menos frecuente, son: "
                           + "; ".join(partes) + ".", normal))

    num = 3
    lista_paises = sorted(t["pais_reporte"].unique())
    if len(lista_paises) > 1:
        h.append(Paragraph(f"{num}. Resultados por país", h2))
        num += 1
        for pais in lista_paises:
            h.append(Paragraph(pais, h3))
            h.append(Paragraph(_parrafo_grupo(t[t["pais_reporte"] == pais]), normal))
    if SIN_PAIS in lista_paises:
        h.append(Paragraph("Los equipos sin país asignado no tienen país en las fuentes, por lo que "
                           "no aparecen en los reportes por país y deben revisarse en el reporte general.",
                           normal))

    lista_so = sorted(t["sistema_operativo"].unique())
    if len(lista_so) > 1:
        h.append(Paragraph(f"{num}. Resultados por sistema operativo", h2))
    for so in (lista_so if len(lista_so) > 1 else []):
        h.append(Paragraph(so, h3))
        h.append(Paragraph(_parrafo_grupo(t[t["sistema_operativo"] == so]), normal))

    desv = t[t["motivos"].map(len).gt(0)].sort_values(["pais_reporte", "equipo_id"], kind="mergesort")
    h.append(PageBreak())
    h.append(Paragraph("Anexo. Equipos con desviaciones", h2))
    if desv.empty:
        h.append(Paragraph("No se encontraron equipos con desviaciones.", normal))
    else:
        filas = [[Paragraph(f"<b>{c}</b>", chico) for c in ("Equipo", "País", "Sistema operativo", "Desviación")]]
        for _, r in desv.iterrows():
            filas.append([Paragraph(r["equipo_id"], chico), Paragraph(r["pais_reporte"], chico),
                          Paragraph(r["sistema_operativo"], chico),
                          Paragraph("; ".join(r["motivos"]), chico)])
        tabla = Table(filas, colWidths=[3 * cm, 3.3 * cm, 2.7 * cm, 8 * cm], repeatRows=1)
        tabla.setStyle(TableStyle([
            ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#999999")),
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e6e6e6")),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ]))
        h.append(tabla)

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, leftMargin=2 * cm, rightMargin=2 * cm,
                            topMargin=2 * cm, bottomMargin=2 * cm,
                            title="Reporte de cifrado de equipos")
    doc.build(h, onFirstPage=_pie_pagina, onLaterPages=_pie_pagina)
    return buffer.getvalue()
