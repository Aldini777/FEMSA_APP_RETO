"""
App principal (Streamlit) - Dashboard de cifrado filtrable por país.

Reutiliza las gráficas de visualizaciones.py y agrega un selector de países
agrupado por región, que se puede usar desde un mapa (clic en el país) o por nombre.

Ejecutar desde la raíz del repo:
    pip install -r requirements.txt
    streamlit run app.py
"""
import json
import math
import sys
import unicodedata
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

# visualizaciones.py importa módulos de la App 1 (cargar_datos, conexion)
RAIZ = Path(__file__).resolve().parent
sys.path.insert(0, str(RAIZ / "app1"))

import visualizaciones as viz   # noqa: E402

# ---------------------------------------------------------------- catálogo de países
NO_DISPONIBLE = "No disponible"
REGIONES = ["Norteamérica", "Centroamérica", "Sudamérica", NO_DISPONIBLE]

# nombre: (región, código ISO-3 para el mapa, latitud, longitud del marcador)
PAISES = {
    "México": ("Norteamérica", "MEX", 23.6, -102.5),
    "Guatemala": ("Centroamérica", "GTM", 15.6, -90.3),
    "Nicaragua": ("Centroamérica", "NIC", 12.9, -85.2),
    "Costa Rica": ("Centroamérica", "CRI", 9.9, -84.1),
    "Panamá": ("Centroamérica", "PAN", 8.5, -80.0),
    "Colombia": ("Sudamérica", "COL", 4.0, -73.0),
    "Venezuela": ("Sudamérica", "VEN", 7.1, -66.2),
    "Brasil": ("Sudamérica", "BRA", -10.0, -52.0),
    "Uruguay": ("Sudamérica", "URY", -32.8, -56.0),
    "Argentina": ("Sudamérica", "ARG", -36.0, -64.5),
    NO_DISPONIBLE: (NO_DISPONIBLE, None, None, None),
}
EN_MAPA = [p for p, (_, iso, _, _) in PAISES.items() if iso]

# Valores que en el CSV significan "sin país"
SIN_PAIS = {"", "no disponible", "sin dato", "n/a", "na", "nan", "none", "desconocido"}


def normalizar(texto):
    """Minúsculas y sin acentos, para comparar nombres de países."""
    texto = unicodedata.normalize("NFKD", str(texto).strip().lower())
    return "".join(c for c in texto if not unicodedata.combining(c))


ALIAS = {normalizar(p): p for p in PAISES}
ALIAS.update({"brazil": "Brasil", "mexico": "México", "panama": "Panamá"})


def pais_canonico(valor):
    clave = normalizar(valor)
    if clave in SIN_PAIS:
        return NO_DISPONIBLE
    return ALIAS.get(clave, str(valor).strip())   # países fuera del catálogo se dejan tal cual


def region_de(pais):
    return PAISES.get(pais, (NO_DISPONIBLE,))[0]


# ---------------------------------------------------------------- selección de países
# La selección vive en st.session_state como un checkbox por país (clave "sel_<país>").
# El mapa y los botones de región solo prenden/apagan esos checkboxes.
def clave(pais):
    return f"sel_{pais}"


def seleccionados(paises):
    return [p for p in paises if st.session_state.get(clave(p), False)]


def marcar(paises, valor):
    for p in paises:
        st.session_state[clave(p)] = valor


def al_hacer_clic_en_mapa():
    """Prende/apaga el país clicado y reinicia el mapa para permitir otro clic."""
    evento = st.session_state.get(f"mapa_{st.session_state.mapa_version}")
    puntos = evento.selection.points if evento else []
    clicados = {p["customdata"][0] if isinstance(p.get("customdata"), list) else p.get("customdata")
                for p in puntos}
    for pais in clicados:
        if pais in PAISES:
            st.session_state[clave(pais)] = not st.session_state.get(clave(pais), False)
    st.session_state.mapa_version += 1


# Colores del mapa
COLOR_ELEGIDO, COLOR_DISPONIBLE, COLOR_FONDO = "#d6001c", "#b8c4d4", "#eceff3"
# Dónde va el nombre de cada país respecto a su punto (Centroamérica es estrecha)
POS_ETIQUETA = {"Guatemala": "middle left", "Nicaragua": "middle right",
                "Costa Rica": "bottom left", "Panamá": "top right",
                "Colombia": "bottom center", "Uruguay": "middle right"}


def merc(lat):
    """Latitud -> eje Y en proyección Mercator (en 'grados' para mantener la escala)."""
    return math.degrees(math.log(math.tan(math.pi / 4 + math.radians(lat) / 2)))


@st.cache_data
def contornos():
    """Contornos simplificados (Natural Earth 1:50m) listos para dibujar: ISO-3 -> (xs, ys)."""
    datos = json.loads((RAIZ / "mapa_latam.json").read_text(encoding="utf-8"))
    salida = {}
    for iso, pais in datos.items():
        xs, ys = [], []
        for anillo in pais["anillos"]:
            xs += [x for x, _ in anillo] + [None]
            ys += [merc(y) for _, y in anillo] + [None]
        salida[iso] = (xs, ys)
    return salida


def mapa(conteos):
    """Mapa ligero de Latinoamérica (sin motor geográfico): elegidos en rojo, resto en gris."""
    geo = contornos()
    elegidos = set(seleccionados(EN_MAPA))
    nuestros = {PAISES[p][1] for p in EN_MAPA}
    fig = go.Figure()

    # Países fuera del catálogo: solo de fondo, sin interacción
    xs, ys = [], []
    for iso, (x, y) in geo.items():
        if iso not in nuestros:
            xs += x
            ys += y
    fig.add_trace(go.Scatter(x=xs, y=ys, fill="toself", mode="lines", hoverinfo="skip",
                             fillcolor=COLOR_FONDO, line=dict(color="white", width=0.8)))

    # Países del catálogo: uno por traza para poder colorearlos por separado
    for p in EN_MAPA:
        x, y = geo[PAISES[p][1]]
        fig.add_trace(go.Scatter(
            x=x, y=y, fill="toself", mode="lines", hoveron="fills",
            name=f"{p} · {conteos.get(p, 0):,} equipos", customdata=[p] * len(x),
            fillcolor=COLOR_ELEGIDO if p in elegidos else COLOR_DISPONIBLE,
            line=dict(color="white", width=1),
        ))

    # Punto + nombre en cada país: es lo que se clica (funciona igual en países pequeños)
    fig.add_trace(go.Scatter(
        x=[PAISES[p][3] for p in EN_MAPA], y=[merc(PAISES[p][2]) for p in EN_MAPA],
        mode="markers+text", text=EN_MAPA, customdata=EN_MAPA,
        textposition=[POS_ETIQUETA.get(p, "top center") for p in EN_MAPA],
        textfont=dict(size=11, color="#2b3440"),
        hovertext=[f"<b>{p}</b><br>{region_de(p)}<br>{conteos.get(p, 0):,} equipos"
                   for p in EN_MAPA],
        hoverinfo="text",
        marker=dict(size=12, color=["#7a0010" if p in elegidos else "#5b6b7f" for p in EN_MAPA],
                    line=dict(color="white", width=2)),
        unselected=dict(marker=dict(opacity=1), textfont=dict(color="#2b3440")),
    ))

    fig.update_xaxes(range=[-118, -33], visible=False, fixedrange=True)
    fig.update_yaxes(range=[merc(-56), merc(33)], visible=False, fixedrange=True,
                     scaleanchor="x", scaleratio=1)
    fig.update_layout(height=600, margin=dict(l=0, r=0, t=0, b=0), showlegend=False,
                      plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
                      dragmode=False, hoverlabel=dict(bgcolor="white", font_size=13))
    return fig


def selector_paises(df):
    """Dibuja el mapa y las listas por región. Regresa los países elegidos."""
    conteos = df["pais"].value_counts().to_dict()
    # Catálogo + cualquier país del archivo que no esté en el catálogo
    todos = list(PAISES) + sorted(set(conteos) - set(PAISES))
    st.session_state.setdefault("mapa_version", 0)

    st.subheader("Selección de países")
    col_mapa, col_lista = st.columns([3, 2], gap="large")

    with col_lista:
        st.caption("Elige por nombre o haz clic en el mapa. Sin selección se muestran todos.")
        b1, b2 = st.columns(2)
        b1.button("Seleccionar todos", on_click=marcar, args=(todos, True),
                  width="stretch")
        b2.button("Limpiar selección", on_click=marcar, args=(todos, False),
                  width="stretch")
        for region in REGIONES:
            paises_region = [p for p in todos if region_de(p) == region]
            n_sel = len(seleccionados(paises_region))
            with st.expander(f"{region}  ·  {n_sel}/{len(paises_region)}", expanded=True):
                r1, r2 = st.columns(2)
                r1.button("Toda la región", key=f"todo_{region}", on_click=marcar,
                          args=(paises_region, True), width="stretch")
                r2.button("Quitar región", key=f"nada_{region}", on_click=marcar,
                          args=(paises_region, False), width="stretch")
                for p in paises_region:
                    st.checkbox(f"{p} ({conteos.get(p, 0):,})", key=clave(p))

    with col_mapa:
        st.plotly_chart(
            mapa(conteos), key=f"mapa_{st.session_state.mapa_version}",
            on_select=al_hacer_clic_en_mapa, selection_mode="points",
            width="stretch", config={"displayModeBar": False, "scrollZoom": False},
        )

    return seleccionados(todos)


# ---------------------------------------------------------------- app
def main():
    st.set_page_config(page_title="Auditoría de cifrado - FEMSA", layout="wide")
    st.title("Auditoría de cifrado de equipos")

    df = viz.obtener_datos()
    if df is None:
        return

    df = df.copy()
    df["pais"] = df["pais"].map(pais_canonico)
    df["region"] = df["pais"].map(region_de)

    elegidos = selector_paises(df)
    if elegidos:
        df = df[df["pais"].isin(elegidos)]
        st.info("Mostrando: " + ", ".join(elegidos))
    else:
        st.info("Mostrando: todos los países")

    st.sidebar.header("Filtros")
    so = st.sidebar.multiselect(viz.ETIQUETAS["sistema_operativo"],
                                sorted(df["sistema_operativo"].unique()))
    if so:
        df = df[df["sistema_operativo"].isin(so)]

    st.divider()
    viz.mostrar(df)


if __name__ == "__main__":
    main()
