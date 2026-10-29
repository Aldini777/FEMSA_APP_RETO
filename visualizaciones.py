"""
App 2 (Dashboard) - Prototipo de visualizaciones.

Solo muestra gráficas sobre la tabla equipos_raw (sin pestañas ni reglas de negocio todavía).
Ejecutar desde la raíz del repo:
    pip install streamlit pandas plotly
    streamlit run app2/visualizaciones.py

Fuente de datos:
  - Base de datos PostgreSQL offline (tabla equipos_raw, la llena la App 1), o
  - Un CSV subido en la barra lateral (se valida con la misma función leer_csv de la App 1).
"""
import sys
import tempfile
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

# La App 1 vive en ../app1: se reutilizan su conexión y su validación del CSV
RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "app1"))

from cargar_datos import leer_csv   # noqa: E402
from conexion import conectar       # noqa: E402

# Mismo orden que COLUMNAS_ESPERADAS (App 1) y que sql/crear_tabla.sql
COLUMNAS = [
    "equipo_id", "usuario_id", "pais", "region", "sistema_operativo", "version_so",
    "estado_tpm", "encryption_readiness", "estado_cifrado", "tecnologia_cifrado",
    "estado_cumplimiento", "categoria_equipo", "clase_equipo", "perfil_privilegio",
    "antiguedad_meses", "banda_antiguedad", "estado_cuenta", "mes_ultimo_logon",
    "banda_recencia", "estado_hardware", "tipo_red", "fuente_datos",
    "en_mdm", "en_ad", "en_macos",
]

# Nombres legibles para títulos y selectores
ETIQUETAS = {
    "pais": "País", "region": "Región", "sistema_operativo": "Sistema operativo",
    "version_so": "Versión SO", "estado_tpm": "Estado TPM",
    "encryption_readiness": "Encryption readiness", "estado_cifrado": "Estado de cifrado",
    "tecnologia_cifrado": "Tecnología de cifrado",
    "estado_cumplimiento": "Estado de cumplimiento", "categoria_equipo": "Categoría de equipo",
    "clase_equipo": "Clase de equipo", "perfil_privilegio": "Perfil de privilegio",
    "banda_antiguedad": "Banda de antigüedad", "estado_cuenta": "Estado de cuenta",
    "banda_recencia": "Banda de recencia", "estado_hardware": "Estado de hardware",
    "tipo_red": "Tipo de red", "fuente_datos": "Fuente de datos",
    "en_mdm": "En MDM", "en_ad": "En AD", "en_macos": "En MacOS",
}
CATEGORICAS = list(ETIQUETAS)   # columnas que tienen sentido para conteos


# ---------------------------------------------------------------- carga de datos
@st.cache_data(ttl=300, show_spinner="Leyendo equipos_raw...")
def cargar_desde_db():
    conn = conectar()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM equipos_raw")
            filas = cur.fetchall()
            columnas = [d[0] for d in cur.description]
    finally:
        conn.close()
    return pd.DataFrame(filas, columns=columnas)


def cargar_desde_csv(archivo):
    """Valida el CSV con la lógica de la App 1 y lo regresa como DataFrame."""
    with tempfile.TemporaryDirectory() as tmp:
        ruta = Path(tmp) / "subido.csv"
        ruta.write_bytes(archivo.getvalue())
        # lanza ValueError si el archivo no es válido
        datos = leer_csv(ruta)
    return pd.DataFrame(datos, columns=COLUMNAS)


def limpiar(df):
    """Rellena vacíos y convierte la antigüedad a número."""
    df = df.copy()
    for col in CATEGORICAS:
        df[col] = df[col].fillna("Sin dato").astype(
            str).str.strip().replace("", "Sin dato")
    df["antiguedad_meses"] = pd.to_numeric(
        df["antiguedad_meses"], errors="coerce")
    return df


# ---------------------------------------------------------------- gráficas
def conteo(df, col):
    return df[col].value_counts().rename_axis(col).reset_index(name="equipos")


def barras(df, col, horizontal=False):
    datos = conteo(df, col)
    if horizontal:
        fig = px.bar(datos, x="equipos", y=col,
                     orientation="h", text="equipos")
        fig.update_yaxes(categoryorder="total ascending")
    else:
        fig = px.bar(datos, x=col, y="equipos", text="equipos")
    fig.update_layout(xaxis_title=None if not horizontal else "Equipos",
                      yaxis_title="Equipos" if not horizontal else None,
                      margin=dict(t=30, b=10))
    return fig


def dona(df, col):
    fig = px.pie(conteo(df, col), names=col, values="equipos", hole=0.5)
    fig.update_traces(textinfo="percent+label")
    fig.update_layout(showlegend=False, margin=dict(t=30, b=10))
    return fig


def apiladas(df, eje, color):
    """Barras apiladas al 100 %: composición de `color` dentro de cada valor de `eje`."""
    datos = df.groupby([eje, color]).size().reset_index(name="equipos")
    fig = px.bar(datos, x=eje, y="equipos", color=color)
    fig.update_layout(barmode="stack", barnorm="percent", yaxis_title="% de equipos",
                      xaxis_title=None, margin=dict(t=30, b=10))
    return fig


def histograma_antiguedad(df):
    fig = px.histogram(
        df.dropna(subset=["antiguedad_meses"]), x="antiguedad_meses", nbins=30)
    fig.update_layout(xaxis_title="Antigüedad (meses)", yaxis_title="Equipos",
                      margin=dict(t=30, b=10))
    return fig


def heatmap(df, fila, columna):
    tabla = pd.crosstab(df[fila], df[columna])
    fig = px.imshow(tabla, text_auto=True, aspect="auto",
                    color_continuous_scale="Blues")
    fig.update_layout(xaxis_title=ETIQUETAS[columna], yaxis_title=ETIQUETAS[fila],
                      margin=dict(t=30, b=10))
    return fig


# ---------------------------------------------------------------- interfaz
def obtener_datos():
    st.sidebar.header("Fuente de datos")
    fuente = st.sidebar.radio(
        "Origen", ["Base de datos (equipos_raw)", "Subir CSV"])

    if fuente == "Subir CSV":
        archivo = st.sidebar.file_uploader("Archivo CSV", type="csv")
        if archivo is None:
            st.info("Sube un CSV en la barra lateral para ver las gráficas.")
            return None
        try:
            return limpiar(cargar_desde_csv(archivo))
        except ValueError as error:
            st.error(f"Archivo rechazado: {error}")
            return None

    try:
        df = cargar_desde_db()
    except Exception as error:   # sin BD levantada, .env faltante, tabla vacía, etc.
        st.error(f"No se pudo leer la base de datos: {error}")
        return None
    if df.empty:
        st.warning(
            "La tabla equipos_raw está vacía. Corre primero la carga de la App 1.")
        return None
    return limpiar(df)


def filtros(df):
    st.sidebar.header("Filtros")
    for col in ("pais", "sistema_operativo"):
        opciones = sorted(df[col].unique())
        elegidas = st.sidebar.multiselect(ETIQUETAS[col], opciones)
        if elegidas:
            df = df[df[col].isin(elegidas)]
    return df


def mostrar(df):
    if df.empty:
        st.warning("Los filtros no dejan ningún equipo.")
        return

    c1, c2, c3 = st.columns(3)
    c1.metric("Equipos", f"{len(df):,}")
    c2.metric("Países", df["pais"].nunique())
    c3.metric("Sistemas operativos", df["sistema_operativo"].nunique())

    st.subheader("Cifrado y cumplimiento")
    a, b = st.columns(2)
    a.caption("Estado de cifrado")
    a.plotly_chart(dona(df, "estado_cifrado"), use_container_width=True)
    b.caption("Estado de cumplimiento")
    b.plotly_chart(dona(df, "estado_cumplimiento"), use_container_width=True)

    st.subheader("Distribución geográfica")
    a, b = st.columns(2)
    a.caption("Equipos por país")
    a.plotly_chart(barras(df, "pais", horizontal=True),
                   use_container_width=True)
    b.caption("Estado de cifrado por país (% de equipos)")
    b.plotly_chart(apiladas(df, "pais", "estado_cifrado"),
                   use_container_width=True)

    st.subheader("Sistema operativo y tecnología")
    a, b = st.columns(2)
    a.caption("Estado de cifrado por sistema operativo (% de equipos)")
    a.plotly_chart(apiladas(df, "sistema_operativo",
                   "estado_cifrado"), use_container_width=True)
    b.caption("Tecnología de cifrado")
    b.plotly_chart(barras(df, "tecnologia_cifrado"), use_container_width=True)

    st.subheader("Hardware y antigüedad")
    a, b = st.columns(2)
    a.caption("Estado de TPM")
    a.plotly_chart(barras(df, "estado_tpm"), use_container_width=True)
    b.caption("Antigüedad de los equipos")
    b.plotly_chart(histograma_antiguedad(df), use_container_width=True)

    st.subheader("Visualizador libre")
    st.caption(
        "Elige las variables para probar cruces antes de definirlos en el dashboard.")
    a, b = st.columns(2)
    var1 = a.selectbox("Variable principal", CATEGORICAS, index=CATEGORICAS.index("pais"),
                       format_func=ETIQUETAS.get)
    var2 = b.selectbox("Cruzar con (opcional)", ["(ninguna)"] + CATEGORICAS,
                       format_func=lambda c: c if c == "(ninguna)" else ETIQUETAS[c])
    if var2 == "(ninguna)":
        st.plotly_chart(barras(df, var1), use_container_width=True, key="libre_barras")
    elif var1 == var2:
        st.info("Elige dos variables distintas para el cruce.")
    else:
        st.plotly_chart(heatmap(df, var1, var2), use_container_width=True, key="libre_heatmap")

    with st.expander("Ver datos"):
        st.dataframe(df.head(500), use_container_width=True)


def main():
    st.set_page_config(
        page_title="Auditoría de cifrado - FEMSA", layout="wide")
    st.title("Auditoría de cifrado de equipos")
    st.caption("Prototipo de visualizaciones (App 2)")
    df = obtener_datos()
    if df is not None:
        mostrar(filtros(df))


if __name__ == "__main__":
    main()
