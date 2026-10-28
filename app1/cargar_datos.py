"""
Carga automática: CSV del usuario -> tabla equipos_raw en PostgreSQL.
Prueba: python app1/cargar_datos.py ../data.csv
"""
import csv
import io
import sys
import unicodedata
from pathlib import Path

from conexion import conectar

CARPETA = Path(__file__).resolve().parent
SQL_CREAR_TABLA = CARPETA / "sql" / "crear_tabla.sql"

COLUMNAS_ESPERADAS = [
    "EquipoID", "UsuarioID", "País", "Región", "Sistema Operativo", "Versión SO",
    "Estado TPM", "Encryption Readiness", "Estado de Cifrado",
    "Tecnología de cifrado State", "Estado de Cumplimiento", "Categoría de Equipo",
    "Clase de Equipo", "Perfil de Privilegio", "Antigüedad Meses", "Banda Antigüedad",
    "Estado de Cuenta", "Mes Último Logon", "Banda Recencia", "Estado Hardware",
    "Tipo de Red", "Fuente de Datos", "En MDM", "En AD", "En MacOS",
]


def limpiar(texto):
    """Quita espacios y unifica acentos para comparar nombres de columnas."""
    return unicodedata.normalize("NFC", texto).strip()


def leer_csv(ruta):
    """Lee el CSV, se salta lo que haya antes de los encabezados y valida columnas."""
    ruta = Path(ruta)
    if not ruta.exists():
        raise ValueError(f"No se encontró el archivo: {ruta}")
    if ruta.suffix.lower() != ".csv":
        raise ValueError("El archivo debe ser .csv")

    try:
        texto = ruta.read_text(encoding="utf-8-sig")
    except UnicodeDecodeError:
        texto = ruta.read_text(encoding="latin-1")

    # Detectar si el separador es coma o punto y coma
    primeras = texto[:5000]
    separador = ";" if primeras.count(";") > primeras.count(",") else ","

    filas = list(csv.reader(io.StringIO(texto), delimiter=separador))

    # Buscar la fila de encabezados (la que empieza con EquipoID)
    inicio = None
    for i, fila in enumerate(filas[:20]):
        if fila and limpiar(fila[0]) == "EquipoID":
            inicio = i
            break
    if inicio is None:
        raise ValueError("No se encontró la fila de encabezados (columna 'EquipoID')")

    encabezados = [limpiar(c) for c in filas[inicio]]
    while encabezados and encabezados[-1] == "":
        encabezados.pop()   # quita columnas vacías que a veces agrega Excel

    if encabezados != COLUMNAS_ESPERADAS:
        faltan = [c for c in COLUMNAS_ESPERADAS if c not in encabezados]
        sobran = [c for c in encabezados if c not in COLUMNAS_ESPERADAS]
        raise ValueError(f"Las columnas no coinciden. Faltan: {faltan}. Sobran: {sobran}")

    n = len(COLUMNAS_ESPERADAS)
    datos = []
    for num, fila in enumerate(filas[inicio + 1:], start=inicio + 2):
        if not any(c.strip() for c in fila):
            continue                      # salta filas vacías
        extra = fila[n:]
        if any(c.strip() for c in extra) or len(fila) < n:
            raise ValueError(f"La fila {num} no tiene {n} columnas")
        datos.append(fila[:n])

    if not datos:
        raise ValueError("El archivo no tiene filas de datos")
    return datos


def cargar_a_postgres(datos):
    """Crea la tabla si no existe, reemplaza su contenido y regresa el total de filas."""
    buffer = io.StringIO()
    csv.writer(buffer).writerows(datos)
    buffer.seek(0)

    conn = conectar()
    try:
        with conn:   # todo o nada: si algo falla, no se guarda nada
            with conn.cursor() as cur:
                cur.execute(SQL_CREAR_TABLA.read_text(encoding="utf-8"))
                cur.execute("TRUNCATE TABLE equipos_raw;")
                cur.copy_expert("COPY equipos_raw FROM STDIN WITH (FORMAT csv)", buffer)
                cur.execute("SELECT COUNT(*) FROM equipos_raw;")
                fila_total = cur.fetchone()
                if fila_total is None:
                    raise RuntimeError("No se pudo obtener el total de filas cargadas")
                total = fila_total[0]
    finally:
        conn.close()
    return total


def procesar_archivo(ruta):
    """Función que llamará la app cuando el usuario suba su CSV."""
    datos = leer_csv(ruta)
    print(f"Archivo leído: {len(datos)} equipos")
    total = cargar_a_postgres(datos)
    print(f"Carga completa: {total} filas en equipos_raw")
    return total


if __name__ == "__main__":
    ruta = sys.argv[1] if len(sys.argv) > 1 else "../data.csv"
    try:
        procesar_archivo(ruta)
    except ValueError as error:
        print(f"Archivo rechazado: {error}")