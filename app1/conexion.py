import os
from pathlib import Path

#python -m pip install python-dotenv psycopg2-binary

import psycopg2
from dotenv import load_dotenv

# Lee el archivo .env que está en la carpeta principal del repo
load_dotenv(Path(__file__).resolve().parent.parent / ".env")


def conectar():
    """Abre la conexión a PostgreSQL con los datos del .env."""
    return psycopg2.connect(
        user=os.getenv("DB_USER", "postgres"),
        password=os.getenv("DB_PASSWORD"),
        host=os.getenv("DB_HOST", "localhost"),
        port=os.getenv("DB_PORT", "5432"),
        dbname=os.getenv("DB_NAME", "discos_duros"),
    )


# Prueba: solo se ejecuta si corres este archivo directamente
if __name__ == "__main__":
    with conectar() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM equipos_raw;")
            resultado = cur.fetchone()
            print("Conexión exitosa. Filas en equipos_raw:", resultado[0] if resultado is not None else 0)
