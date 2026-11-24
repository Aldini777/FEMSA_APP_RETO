"""
App principal (Streamlit) - Dashboard de cifrado filtrable por país, con pestañas.

Reutiliza las gráficas de visualizaciones.py y agrega un selector de países
agrupado por región, que se puede usar desde un mapa (clic en el país) o por nombre.

Ejecutar:
cd reportes
python -m streamlit run app2.py
"""
import json
import math
import sys
import unicodedata
from datetime import datetime
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

# Agregamos ambas carpetas al path para que app2.py funcione tanto si se
# ejecuta desde reportes como desde la raíz del repositorio.
RAIZ = Path(__file__).resolve().parent
REPO = RAIZ.parent
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(RAIZ))

import reportes.visualizaciones as viz   # noqa: E402
from reporte import (_faltantes, _numeros, _por_cifrar,   # noqa: E402
                     generar_reporte_ejecutivo_pdf, generar_reporte_tecnico_pdf, preparar)

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


# Colores del mapa (pensados para el tema oscuro de .streamlit/config.toml)
# Rojo FEMSA para lo elegido; grises para el resto
COLOR_ELEGIDO, COLOR_DISPONIBLE, COLOR_FONDO = "#C8102E", "#6B7480", "#2A2F38"
COLOR_BORDE = "#0E1117"          # mismo color que el fondo de la página
COLOR_TEXTO = "#E6E8EB"          # nombres de los países
COLOR_PUNTO, COLOR_PUNTO_ELEGIDO = "#C9D1D9", "#FFFFFF"
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
                             fillcolor=COLOR_FONDO, line=dict(color=COLOR_BORDE, width=0.8)))

    # Países del catálogo: uno por traza para poder colorearlos por separado
    for p in EN_MAPA:
        x, y = geo[PAISES[p][1]]
        fig.add_trace(go.Scatter(
            x=x, y=y, fill="toself", mode="lines", hoveron="fills",
            name=f"{p} · {conteos.get(p, 0):,} equipos", customdata=[p] * len(x),
            fillcolor=COLOR_ELEGIDO if p in elegidos else COLOR_DISPONIBLE,
            line=dict(color=COLOR_BORDE, width=1),
        ))

    # Punto + nombre en cada país: es lo que se clica (funciona igual en países pequeños)
    fig.add_trace(go.Scatter(
        x=[PAISES[p][3] for p in EN_MAPA], y=[merc(PAISES[p][2]) for p in EN_MAPA],
        mode="markers+text", text=EN_MAPA, customdata=EN_MAPA,
        textposition=[POS_ETIQUETA.get(p, "top center") for p in EN_MAPA],
        textfont=dict(size=11, color=COLOR_TEXTO),
        hovertext=[f"<b>{p}</b><br>{region_de(p)}<br>{conteos.get(p, 0):,} equipos"
                   for p in EN_MAPA],
        hoverinfo="text",
        marker=dict(size=12, color=[COLOR_PUNTO_ELEGIDO if p in elegidos else COLOR_PUNTO for p in EN_MAPA],
                    line=dict(color=COLOR_BORDE, width=2)),
        unselected=dict(marker=dict(opacity=1), textfont=dict(color=COLOR_TEXTO)),
    ))

    fig.update_xaxes(range=[-118, -33], visible=False, fixedrange=True)
    fig.update_yaxes(range=[merc(-56), merc(33)], visible=False, fixedrange=True,
                     scaleanchor="x", scaleratio=1)
    fig.update_layout(height=600, margin=dict(l=0, r=0, t=0, b=0), showlegend=False,
                      plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
                      dragmode=False, hoverlabel=dict(bgcolor="#1C2129", font_size=13, font_color=COLOR_TEXTO))
    return fig


# ---------------------------------------------------------------- diseño de la página
ROJO = "#C8102E"
PALETA = viz.PALETA
TEXTO, TEXTO_SUAVE = "#E6E8EB", "#9AA3AF"
TARJETA, BORDE = "#1C2129", "#2A2F38"
LOGO = RAIZ / "assets" / "logo_femsa.png"

CSS = f"""
<style>
.block-container {{padding-top: 1.6rem; padding-bottom: 3rem; max-width: 1400px;}}
header[data-testid="stHeader"] {{background: transparent;}}
[data-testid="stDecoration"] {{background: {ROJO}; height: 4px;}}

.encabezado {{display: flex; align-items: center; gap: 1.4rem; padding: 0.2rem 0 1.1rem 0;
             border-bottom: 1px solid {BORDE}; margin-bottom: 1.2rem;}}
.encabezado img {{height: 54px; background: #FFFFFF; border-radius: 10px; padding: 6px 12px;}}
.encabezado .titulo {{font-size: 2rem; font-weight: 800; color: {TEXTO}; line-height: 1.1; margin: 0;}}
.encabezado .sub {{color: {TEXTO_SUAVE}; font-size: 0.95rem; margin-top: 0.25rem;}}
.encabezado .linea {{width: 56px; height: 4px; background: {ROJO}; border-radius: 2px; margin-top: 0.5rem;}}

.chips {{display: flex; flex-wrap: wrap; gap: 0.45rem; margin: 0 0 1.1rem 0; align-items: center;}}
.chips .etq {{color: {TEXTO_SUAVE}; font-size: 0.85rem; margin-right: 0.2rem;}}
.chip {{background: {TARJETA}; border: 1px solid {BORDE}; color: {TEXTO}; border-radius: 999px;
        padding: 0.18rem 0.75rem; font-size: 0.82rem;}}
.chip.rojo {{border-color: {ROJO}; color: #FFFFFF; background: rgba(200,16,46,0.18);}}

.kpi {{background: {TARJETA}; border: 1px solid {BORDE}; border-top: 3px solid {ROJO};
       border-radius: 14px; padding: 1rem 1.2rem; height: 100%;}}
.kpi .valor {{font-size: 2rem; font-weight: 800; color: {TEXTO}; line-height: 1.1;}}
.kpi .nombre {{color: {TEXTO_SUAVE}; font-size: 0.85rem; text-transform: uppercase;
               letter-spacing: 0.04em; margin-bottom: 0.35rem;}}
.kpi .detalle {{color: {TEXTO_SUAVE}; font-size: 0.8rem; margin-top: 0.35rem;}}
.kpi.alerta {{border-top-color: #E8A317;}}

.seccion {{margin: 1.6rem 0 0.6rem 0;}}
.seccion .nombre {{font-size: 1.15rem; font-weight: 700; color: {TEXTO};}}
.seccion .desc {{color: {TEXTO_SUAVE}; font-size: 0.88rem;}}

.stTabs [data-baseweb="tab-list"] {{gap: 0.4rem; border-bottom: 1px solid {BORDE};}}
.stTabs [data-baseweb="tab"] {{padding: 0.6rem 1.2rem; color: {TEXTO_SUAVE};}}
.stTabs [data-baseweb="tab"] p {{font-size: 1.02rem; font-weight: 600;}}
[data-testid="stAppDeployButton"] {{display: none;}}
.stTabs [aria-selected="true"] {{color: {TEXTO} !important;}}
.stTabs [data-baseweb="tab-highlight"] {{background-color: {ROJO};}}

[data-testid="stSidebar"] {{border-right: 1px solid {BORDE};}}
.tarjeta-reporte {{background: {TARJETA}; border: 1px solid {BORDE}; border-radius: 14px;
                   padding: 1.1rem 1.3rem; margin-bottom: 0.8rem;}}
.tarjeta-reporte .nombre {{font-weight: 700; color: {TEXTO}; font-size: 1.05rem;}}
.tarjeta-reporte .desc {{color: {TEXTO_SUAVE}; font-size: 0.88rem; margin-top: 0.25rem;}}
</style>
"""


def logo_html():
    if not LOGO.exists():
        return ""
    import base64
    datos = base64.b64encode(LOGO.read_bytes()).decode()
    return f'<img src="data:image/png;base64,{datos}" alt="logo">'


def encabezado():
    st.markdown(CSS, unsafe_allow_html=True)
    st.markdown(f"""
    <div class="encabezado">
      {logo_html()}
      <div>
        <div class="titulo">Auditoría de cifrado de equipos</div>
        <div class="sub">Auditoría Interna · Monitoreo de cifrado de equipos de cómputo</div>
        <div class="linea"></div>
      </div>
    </div>""", unsafe_allow_html=True)


def seccion(nombre, desc=""):
    st.markdown(f'<div class="seccion"><div class="nombre">{nombre}</div>'
                f'<div class="desc">{desc}</div></div>', unsafe_allow_html=True)


def chips(paises, sistemas):
    p = "".join(f'<span class="chip rojo">{x}</span>' for x in paises) or '<span class="chip">Todos los países</span>'
    s = "".join(f'<span class="chip rojo">{x}</span>' for x in sistemas) or '<span class="chip">Todos los sistemas</span>'
    st.markdown(f'<div class="chips"><span class="etq">Mostrando:</span>{p}'
                f'<span class="etq" style="margin-left:.6rem">Sistema:</span>{s}</div>',
                unsafe_allow_html=True)


def tarjetas(df):
    """Indicadores principales, con las mismas reglas que el reporte PDF."""
    t = preparar(df)
    n = _numeros(t)
    pct = lambda a, b: f"{a / b * 100:.1f}%" if b else "0%"
    datos = [
        ("Equipos", f"{n['total']:,}", f"{t['pais_reporte'].nunique()} países · "
                                        f"{t['sistema_operativo'].nunique()} sistemas operativos", ""),
        ("Reportan al MDM", pct(n["en_mdm"], n["total"]), f"{n['en_mdm']:,} de {n['total']:,} equipos", ""),
        ("Cifrados en MDM", pct(n["cifrados"], n["en_mdm"]), f"{n['cifrados']:,} equipos gestionados cifrados", ""),
        ("Con desviación", f"{n['con_desv']:,}", f"{n['no_cifrados']:,} sin cifrar · "
                                                  f"{n['inactivos']:,} inactivos +90 días", "alerta"),
    ]
    for col, (nombre, valor, detalle, clase) in zip(st.columns(4), datos):
        col.markdown(f'<div class="kpi {clase}"><div class="nombre">{nombre}</div>'
                     f'<div class="valor">{valor}</div><div class="detalle">{detalle}</div></div>',
                     unsafe_allow_html=True)


def pintar(fig, alto=360):
    """Mismo estilo oscuro para todas las gráficas."""
    fig.update_layout(
        height=alto, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color=TEXTO, size=12), colorway=PALETA,
        margin=dict(l=10, r=10, t=10, b=10),
        legend=dict(orientation="h", yanchor="bottom", y=-0.32, xanchor="center", x=0.5,
                    title_text="", font=dict(size=11)),
        hoverlabel=dict(bgcolor=TARJETA, font_color=TEXTO),
    )
    fig.update_xaxes(gridcolor=BORDE, zerolinecolor=BORDE, linecolor=BORDE, automargin=True)
    fig.update_yaxes(gridcolor=BORDE, zerolinecolor=BORDE, linecolor=BORDE, automargin=True)
    return fig


def barras_delgadas(fig, n, horizontal=False):
    """Evita barras gigantes cuando hay pocas categorías (por ejemplo, un solo país)."""
    if n <= 3:
        fig.update_traces(width=0.35 if n == 1 else 0.5)
    if horizontal:
        return max(190, 70 + 42 * n)   # alto según el número de barras
    return 360


def grafica(titulo, fig, alto=360, key=None):
    with st.container(border=True):
        st.markdown(f"**{titulo}**")
        st.plotly_chart(pintar(fig, alto), theme=None, use_container_width=True,
                        config={"displayModeBar": False}, key=key)


def dona(df, col):
    fig = viz.dona(df, col)
    fig.update_traces(textinfo="percent", textposition="inside", insidetextorientation="horizontal",
                      marker=dict(colors=PALETA, line=dict(color="#0E1117", width=2)))
    fig.update_layout(showlegend=True)
    return fig


def desviaciones(df):
    t = preparar(df)
    conteo = pd.Series([m for lista in t["motivos"] for m in lista], dtype=object).value_counts()
    datos = conteo.rename_axis("desviacion").reset_index(name="equipos").iloc[::-1]
    fig = go.Figure(go.Bar(x=datos["equipos"], y=datos["desviacion"], orientation="h",
                           text=datos["equipos"], textposition="outside", marker_color=ROJO))
    fig.update_xaxes(title="Equipos")
    return fig


VISTAS = {
    "Todos los equipos": "Todos los equipos del alcance elegido arriba.",
    "Deben cifrarse o revisar cifrado": "Sin cifrar, sin evidencia de cifrado o fuera de la política.",
    "No están en alguna fuente": "Windows fuera del MDM o del Directorio Activo; macOS fuera del MDM "
                                 "o del inventario de macOS.",
    "Con alguna desviación": "Cualquier desviación de las reglas del reporte.",
    "Sin desviaciones": "Equipos que cumplen todo.",
}


def pestana_equipos(df):
    """Lista de equipos con filtros propios (solo afectan a esta pestaña)."""
    t = preparar(df)
    t["que_revisar"] = t["motivos"].map("; ".join)
    accion = _por_cifrar(t)["accion"]
    t["accion"] = accion.reindex(t.index).fillna("")
    falta = _faltantes(t)["falta_en"]
    t["falta_en"] = falta.reindex(t.index).fillna("")

    seccion("Equipos", "Filtra la lista para saber exactamente qué equipos atender. "
                       "Estos filtros solo afectan a esta pestaña.")

    vista = st.radio("Vista", list(VISTAS), horizontal=True, key="eq_vista")
    st.caption(VISTAS[vista])

    c1, c2, c3, c4 = st.columns(4)
    cifrado = c1.multiselect("Estado de cifrado", sorted(t["estado_cifrado"].unique()),
                             placeholder="Todos", key="eq_cifrado")
    mdm = c2.selectbox("¿Está en el MDM?", ["Todos", "Sí", "No"], key="eq_mdm")
    ad = c3.selectbox("¿Está en el Directorio Activo?", ["Todos", "Sí", "No"], key="eq_ad")
    tipos = sorted({m for lista in t["motivos"] for m in lista})
    tipo = c4.selectbox("Tipo de desviación", ["Todas"] + tipos, key="eq_tipo")
    buscar = st.text_input("Buscar equipo o usuario", placeholder="Escribe parte del ID...",
                           key="eq_buscar")

    if vista == "Deben cifrarse o revisar cifrado":
        t = t[t["accion"] != ""]
    elif vista == "No están en alguna fuente":
        t = t[t["falta_en"] != ""]
    elif vista == "Con alguna desviación":
        t = t[t["motivos"].map(len) > 0]
    elif vista == "Sin desviaciones":
        t = t[t["motivos"].map(len) == 0]
    if cifrado:
        t = t[t["estado_cifrado"].isin(cifrado)]
    if mdm != "Todos":
        t = t[t["en_mdm"] == mdm]
    if ad != "Todos":
        t = t[t["en_ad"] == ad]
    if tipo != "Todas":
        t = t[t["motivos"].map(lambda lista: tipo in lista)]
    if buscar.strip():
        texto = buscar.strip().lower()
        t = t[t["equipo_id"].str.lower().str.contains(texto, regex=False) |
              t["usuario_id"].astype(str).str.lower().str.contains(texto, regex=False)]

    n = len(t)
    k1, k2, k3, k4 = st.columns(4)
    for col, (nombre, valor) in zip((k1, k2, k3, k4), [
            ("Equipos en la lista", n),
            ("Sin cifrar", int(t["no_cifrado_b"].sum())),
            ("Fuera del MDM", int((~t["en_mdm_b"]).sum())),
            ("Con desviación", int((t["motivos"].map(len) > 0).sum()))]):
        col.markdown(f'<div class="kpi"><div class="nombre">{nombre}</div>'
                     f'<div class="valor">{valor:,}</div></div>', unsafe_allow_html=True)
    st.write("")

    if t.empty:
        st.info("Ningún equipo cumple con estos filtros.")
        return

    orden = t.sort_values(["pais_reporte", "equipo_id"], kind="mergesort")
    tabla = pd.DataFrame({
        "Equipo": orden["equipo_id"],
        "País": orden["pais_reporte"],
        "Sistema operativo": orden["sistema_operativo"],
        "Estado de cifrado": orden["estado_cifrado"],
        "En MDM": orden["en_mdm"],
        "En AD": orden["en_ad"],
        "Acción de cifrado": orden["accion"],
        "No está en": orden["falta_en"],
        "Qué revisar": orden["que_revisar"],
    })
    st.dataframe(tabla, use_container_width=True, hide_index=True,
                 height=min(560, 38 + 35 * len(tabla)), key="eq_tabla")


# ---------------------------------------------------------------- selector de países
def selector_paises(df):
    """Mapa + filtros. Regresa (países elegidos, sistemas operativos elegidos)."""
    conteos = df["pais"].value_counts().to_dict()
    todos = list(PAISES) + sorted(set(conteos) - set(PAISES))
    st.session_state.setdefault("mapa_version", 0)

    col_mapa, col_lista = st.columns([3, 2], gap="large")
    with col_lista:
        st.markdown("**Sistema operativo**")
        so = st.multiselect(viz.ETIQUETAS["sistema_operativo"],
                            sorted(df["sistema_operativo"].unique()),
                            placeholder="Todos los sistemas operativos",
                            label_visibility="collapsed")
        st.markdown("**Países**")
        b1, b2 = st.columns(2)
        b1.button("Seleccionar todos", on_click=marcar, args=(todos, True), width="stretch")
        b2.button("Limpiar selección", on_click=marcar, args=(todos, False), width="stretch")
        for region in REGIONES:
            paises_region = [p for p in todos if region_de(p) == region]
            if not paises_region:
                continue
            n_sel = len(seleccionados(paises_region))
            with st.expander(f"{region}  ·  {n_sel}/{len(paises_region)}", expanded=False):
                r1, r2 = st.columns(2)
                r1.button("Toda la región", key=f"todo_{region}", on_click=marcar,
                          args=(paises_region, True), width="stretch")
                r2.button("Quitar región", key=f"nada_{region}", on_click=marcar,
                          args=(paises_region, False), width="stretch")
                for p in paises_region:
                    st.checkbox(f"{p} ({conteos.get(p, 0):,})", key=clave(p))

    with col_mapa:
        with st.container(border=True):
            st.plotly_chart(
                mapa(conteos), key=f"mapa_{st.session_state.mapa_version}",
                on_select=al_hacer_clic_en_mapa, selection_mode="points",
                use_container_width=True, config={"displayModeBar": False, "scrollZoom": False},
            )
    return seleccionados(todos), so


# ---------------------------------------------------------------- app
def main():
    st.set_page_config(page_title="Auditoría de cifrado - FEMSA", layout="wide",
                       initial_sidebar_state="expanded")
    encabezado()

    df = viz.obtener_datos()
    if df is None:
        return

    df = df.copy()
    df["pais"] = df["pais"].map(pais_canonico)
    df["region"] = df["pais"].map(region_de)

    # 1. Primero se eligen los países (arriba de todo)
    seccion("Filtros", "Haz clic en el mapa o usa las listas para elegir países. "
                       "Si no eliges nada se muestran todos.")
    elegidos, so = selector_paises(df)

    if elegidos:
        df = df[df["pais"].isin(elegidos)]
    if so:
        df = df[df["sistema_operativo"].isin(so)]

    st.divider()
    chips(elegidos, so)
    if df.empty:
        st.warning("Los filtros no dejan ningún equipo.")
        return

    # 2. Abajo, las pestañas para ver la información
    tab_res, tab_pais, tab_tec, tab_eq, tab_exp, tab_rep = st.tabs(
        ["Resumen", "Por país", "Tecnología y hardware", "Equipos", "Explorador", "Reportes"])

    with tab_eq:
        pestana_equipos(df)

    with tab_res:
        tarjetas(df)
        seccion("Cifrado y cumplimiento", "Estado reportado por las fuentes.")
        a, b = st.columns(2)
        with a:
            grafica("Estado de cifrado", dona(df, "estado_cifrado"), key="g_cif")
        with b:
            grafica("Estado de cumplimiento", dona(df, "estado_cumplimiento"), key="g_cum")
        seccion("Desviaciones principales", "Un equipo puede tener más de una desviación.")
        grafica("Equipos por tipo de desviación", desviaciones(df), alto=340, key="g_desv")

    with tab_pais:
        seccion("Resultados por país")
        n_paises = df["pais"].nunique()
        a, b = st.columns(2)
        with a:
            fig = viz.barras(df, "pais", horizontal=True)
            grafica("Equipos por país", fig, alto=barras_delgadas(fig, n_paises, True), key="g_pais")
        with b:
            fig = viz.apiladas(df, "pais", "estado_cifrado")
            barras_delgadas(fig, n_paises)
            grafica("Estado de cifrado por país (% de equipos)", fig, key="g_pais_cif")

    with tab_tec:
        seccion("Sistema operativo y tecnología")
        a, b = st.columns(2)
        with a:
            fig = viz.apiladas(df, "sistema_operativo", "estado_cifrado")
            barras_delgadas(fig, df["sistema_operativo"].nunique())
            grafica("Estado de cifrado por sistema operativo (% de equipos)", fig, key="g_so")
        with b:
            grafica("Tecnología de cifrado", viz.barras(df, "tecnologia_cifrado", horizontal=True),
                    key="g_tec")
        seccion("Hardware y antigüedad")
        a, b = st.columns(2)
        with a:
            grafica("Estado de TPM", viz.barras(df, "estado_tpm", horizontal=True), key="g_tpm")
        with b:
            grafica("Antigüedad de los equipos", viz.histograma_antiguedad(df), key="g_ant")

    with tab_exp:
        seccion("Visualizador libre", "Elige variables para probar cruces.")
        cat = viz.CATEGORICAS
        a, b = st.columns(2)
        var1 = a.selectbox("Variable principal", cat, index=cat.index("pais"),
                           format_func=lambda c: viz.ETIQUETAS[c])
        var2 = b.selectbox("Cruzar con (opcional)", ["(ninguna)"] + cat,
                           format_func=lambda c: c if c == "(ninguna)" else viz.ETIQUETAS[c])
        if var2 == "(ninguna)":
            grafica(viz.ETIQUETAS[var1], viz.barras(df, var1, horizontal=True), alto=420, key="g_libre")
        elif var1 == var2:
            st.info("Elige dos variables distintas para el cruce.")
        else:
            grafica(f"{viz.ETIQUETAS[var1]} × {viz.ETIQUETAS[var2]}",
                    viz.heatmap(df, var1, var2), alto=460, key="g_cruce")
        with st.expander("Ver datos (primeros 500 equipos)"):
            st.dataframe(df.head(500), use_container_width=True)

    with tab_rep:
        seccion("Descarga de reportes", "El PDF usa los mismos filtros de país y sistema operativo.")
        tipos = {
            "Reporte ejecutivo": ("Resumen visual con indicadores y gráficas, para dirección y comités.",
                                  generar_reporte_ejecutivo_pdf, "ejecutivo"),
            "Reporte técnico": ("Detalle por país y lista de equipos con desviaciones.",
                                generar_reporte_tecnico_pdf, "tecnico"),
        }
        izq, der = st.columns([2, 3], gap="large")
        with izq:
            tipo = st.radio("Tipo de reporte", list(tipos))
            st.caption(f"Equipos incluidos: {len(df):,}")
        with der:
            desc, funcion, nombre_tipo = tipos[tipo]
            st.markdown(f'<div class="tarjeta-reporte"><div class="nombre">{tipo}</div>'
                        f'<div class="desc">{desc}</div></div>', unsafe_allow_html=True)
            try:
                paises_pdf = ["Sin país asignado" if p == NO_DISPONIBLE else p for p in elegidos]
                pdf = funcion(df, paises_pdf, so, df_filtrado=True)
                nombre = "reporte_" + nombre_tipo + "_" + ("_".join(elegidos) if elegidos else "general")
                nombre += "_" + datetime.now().strftime("%Y%m%d") + ".pdf"
                st.download_button(
                    "Descargar PDF", data=pdf, file_name=nombre.replace(" ", "_"),
                    mime="application/pdf", type="primary", width="stretch",
                    key="pdf_" + nombre_tipo + "_" + str(len(df)) + "_" +
                        "_".join(elegidos).replace(" ", "_") + "_" + "_".join(so).replace(" ", "_"),
                )
            except ValueError as error:
                st.warning(str(error))
            except Exception as error:
                st.error(f"No se pudo generar el reporte: {error}")


if __name__ == "__main__":
    main()
