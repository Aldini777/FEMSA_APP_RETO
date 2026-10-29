"""
App principal (Streamlit) - Dashboard de cifrado filtrable por país.

Reutiliza las gráficas de visualizaciones.py y agrega un selector de países
agrupado por región, que se puede usar desde un mapa (clic en el país) o por nombre.

Ejecutar desde la raíz del repo:
    pip install -r requirements.txt
    streamlit run app.py
"""
import sys
import unicodedata
from pathlib import Path

import numpy as np
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


# ---------------------------------------------------------------- datos de ejemplo
@st.cache_data
def datos_ejemplo(n=3000, semilla=7):
    """Datos ficticios para probar la app sin base de datos ni CSV."""
    rng = np.random.default_rng(semilla)
    pesos = np.array([30, 6, 3, 5, 4, 12, 4, 20, 3, 9, 4], dtype=float)
    so = rng.choice(["Windows 11", "Windows 10", "macOS"], n, p=[0.5, 0.35, 0.15])
    df = pd.DataFrame({c: "" for c in viz.COLUMNAS}, index=range(n))
    df["equipo_id"] = [f"EQ{i:05d}" for i in range(n)]
    df["usuario_id"] = [f"U{i:05d}" for i in rng.integers(0, n, n)]
    df["pais"] = rng.choice(list(PAISES), n, p=pesos / pesos.sum())
    df["region"] = df["pais"].map(region_de)
    df["sistema_operativo"] = so
    df["version_so"] = rng.choice(["22H2", "23H2", "24H2"], n)
    df["estado_tpm"] = rng.choice(["TPM 2.0", "TPM 1.2", "Sin TPM"], n, p=[0.8, 0.12, 0.08])
    df["encryption_readiness"] = rng.choice(["Listo", "No listo"], n, p=[0.85, 0.15])
    df["estado_cifrado"] = rng.choice(["Cifrado", "No cifrado", "Parcial"], n, p=[0.7, 0.2, 0.1])
    df["tecnologia_cifrado"] = np.where(so == "macOS", "FileVault", "BitLocker")
    df["estado_cumplimiento"] = rng.choice(["Cumple", "No cumple"], n, p=[0.75, 0.25])
    df["categoria_equipo"] = rng.choice(["Laptop", "Desktop"], n, p=[0.7, 0.3])
    df["clase_equipo"] = rng.choice(["Estándar", "Ejecutivo"], n, p=[0.9, 0.1])
    df["perfil_privilegio"] = rng.choice(["Usuario", "Administrador"], n, p=[0.85, 0.15])
    meses = rng.integers(1, 84, n)
    df["antiguedad_meses"] = meses.astype(str)
    df["banda_antiguedad"] = pd.cut(meses, [0, 24, 48, 84],
                                    labels=["0-2 años", "2-4 años", "4+ años"]).astype(str)
    df["estado_cuenta"] = rng.choice(["Activa", "Inactiva"], n, p=[0.9, 0.1])
    df["banda_recencia"] = rng.choice(["< 30 días", "30-90 días", "> 90 días"], n, p=[0.7, 0.2, 0.1])
    df["estado_hardware"] = rng.choice(["Vigente", "Obsoleto"], n, p=[0.8, 0.2])
    df["tipo_red"] = rng.choice(["Corporativa", "VPN", "Externa"], n)
    df["fuente_datos"] = rng.choice(["Intune", "AD", "Jamf"], n)
    for col in ("en_mdm", "en_ad", "en_macos"):
        df[col] = rng.choice(["Sí", "No"], n)
    return df


def obtener_datos():
    """Igual que viz.obtener_datos, pero con una opción de datos ficticios."""
    st.sidebar.header("Fuente de datos")
    fuente = st.sidebar.radio(
        "Origen", ["Base de datos (equipos_raw)", "Subir CSV", "Datos de ejemplo (ficticios)"])

    if fuente == "Datos de ejemplo (ficticios)":
        st.sidebar.caption("Datos inventados, solo para probar la app.")
        return viz.limpiar(datos_ejemplo())
    if fuente == "Subir CSV":
        archivo = st.sidebar.file_uploader("Archivo CSV", type="csv")
        if archivo is None:
            st.info("Sube un CSV en la barra lateral para ver las gráficas.")
            return None
        try:
            return viz.limpiar(viz.cargar_desde_csv(archivo))
        except ValueError as error:
            st.error(f"Archivo rechazado: {error}")
            return None

    try:
        df = viz.cargar_desde_db()
    except Exception as error:   # sin BD levantada, .env faltante, etc.
        st.error(f"No se pudo leer la base de datos: {error}")
        return None
    if df.empty:
        st.warning("La tabla equipos_raw está vacía. Corre primero la carga de la App 1.")
        return None
    return viz.limpiar(df)


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


def mapa(conteos):
    """Mapa de Latinoamérica: países seleccionados en color, el resto en gris."""
    elegidos = set(seleccionados(EN_MAPA))
    z = [1 if p in elegidos else 0 for p in EN_MAPA]
    texto = [f"<b>{p}</b><br>{region_de(p)}<br>{conteos.get(p, 0):,} equipos" for p in EN_MAPA]

    fig = go.Figure()
    fig.add_trace(go.Choropleth(
        locations=[PAISES[p][1] for p in EN_MAPA], z=z, zmin=0, zmax=1,
        colorscale=[[0, "#d9dee5"], [1, "#d6001c"]], showscale=False,
        customdata=[[p] for p in EN_MAPA], text=texto, hoverinfo="text",
        marker_line_color="white", marker_line_width=0.8,
    ))
    # Marcadores en el centro de cada país: más fáciles de clicar en países pequeños
    fig.add_trace(go.Scattergeo(
        lat=[PAISES[p][2] for p in EN_MAPA], lon=[PAISES[p][3] for p in EN_MAPA],
        mode="markers", customdata=[[p] for p in EN_MAPA], text=texto, hoverinfo="text",
        marker=dict(size=11, color=["#7a0010" if v else "#5b6b7f" for v in z],
                    line=dict(color="white", width=1.5)),
    ))
    fig.update_geos(
        projection_type="mercator", lataxis_range=[-56, 33], lonaxis_range=[-118, -33],
        showcountries=True, countrycolor="white", showland=True, landcolor="#f1f3f6",
        showocean=True, oceancolor="#eaf2fb", showframe=False, resolution=50,
    )
    fig.update_layout(height=560, margin=dict(l=0, r=0, t=0, b=0),
                      showlegend=False, dragmode=False, clickmode="event+select")
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

    df = obtener_datos()
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
