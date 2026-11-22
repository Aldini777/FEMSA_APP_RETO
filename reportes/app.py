"""
Pantalla de prueba de la sección de reportes.
Lee la tabla que cargó la App 1, deja elegir país y sistema operativo,
y descarga el reporte escrito en PDF.

Correr (desde la carpeta reportes):  streamlit run app.py
En el dashboard (App 2) esto va como la pestaña "Reportes".
"""
from datetime import datetime

import streamlit as st

from reporte import filtrar, generar_reporte_pdf, leer_equipos, opciones_filtros, preparar

st.set_page_config(page_title="Reportes de cifrado", layout="centered")
st.title("Reportes de cifrado de equipos")

try:
    df = leer_equipos()
except Exception:
    st.error("No se pudo leer la base de datos. Primero carga el CSV en la App 1.")
    st.stop()

if df.empty:
    st.warning("La base de datos está vacía. Primero carga el CSV en la App 1.")
    st.stop()

lista_paises, lista_so = opciones_filtros(df)
paises = st.multiselect("País (vacío = reporte general)", lista_paises)
sistemas = st.multiselect("Sistema operativo (vacío = todos)", lista_so)

total = len(filtrar(preparar(df), paises, sistemas))
st.write(f"Equipos con estos filtros: {total:,}")

if total == 0:
    st.warning("No hay equipos con los filtros elegidos.")
    st.stop()

pdf = generar_reporte_pdf(df, paises, sistemas)
nombre = "reporte_" + ("_".join(paises) if paises else "general")
nombre += "_" + datetime.now().strftime("%Y%m%d") + ".pdf"
st.download_button("Descargar reporte PDF", data=pdf,
                   file_name=nombre.replace(" ", "_"), mime="application/pdf")