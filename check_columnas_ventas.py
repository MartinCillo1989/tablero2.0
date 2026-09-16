"""
Corré esto con:  python check_columnas_ventas.py
Te muestra TODAS las columnas del archivo de ventas que cruza dos semanas
(01-09 AGO), y las primeras filas de cada una — para ver si hay una fecha
real por venta que no estemos usando.
"""
import os
import pandas as pd

from config import DATA_DIR

# Ajustá esta ruta si hace falta
ARCHIVO = os.path.join(DATA_DIR, "2026-08", "ventas", "ventas 01-09.xlsx")

if not os.path.exists(ARCHIVO):
    print(f"⚠️  No encontré el archivo en: {ARCHIVO}")
    print("   Ajustá la variable ARCHIVO en este script con la ruta correcta.")
else:
    df = pd.read_excel(ARCHIVO)
    print(f"Archivo: {ARCHIVO}")
    print(f"Filas: {len(df)}")
    print(f"\nTODAS las columnas ({len(df.columns)}):")
    for c in df.columns:
        print(f"   - {c!r}  (tipo: {df[c].dtype})")

    print("\nPrimeras 5 filas completas:")
    pd.set_option("display.max_columns", None)
    pd.set_option("display.width", 200)
    print(df.head(5).to_string())