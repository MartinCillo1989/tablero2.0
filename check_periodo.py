"""
Corré esto con:  python check_periodo.py
Te muestra valores REALES de la columna "Descripción Período" en tus
archivos de ventas, y si parse_period_spanish() los está pudiendo leer o no.
"""
import os
import pandas as pd

from config import DATA_DIR
from utils.helpers import list_month_folders, parse_period_spanish

all_months = list_month_folders(DATA_DIR)
print(f"Carpetas de meses encontradas: {all_months}\n")

for m in all_months:
    carpeta = os.path.join(DATA_DIR, m, "ventas")
    if not os.path.isdir(carpeta):
        continue
    for fn in os.listdir(carpeta):
        if not fn.lower().endswith(".xlsx") or fn.startswith("~$"):
            continue
        path = os.path.join(carpeta, fn)
        print("=" * 70)
        print(f"Archivo: {m}/ventas/{fn}")
        print("=" * 70)
        try:
            df = pd.read_excel(path)
        except Exception as e:
            print(f"⚠️  Error leyendo el archivo: {e}")
            continue

        if "Descripción Período" not in df.columns:
            print("⚠️  Este archivo NO TIENE la columna 'Descripción Período'.")
            print(f"   Columnas que sí tiene: {list(df.columns)[:15]}")
            continue

        valores = df["Descripción Período"].dropna().unique()
        print(f"Valores únicos encontrados ({len(valores)}):")
        for v in valores[:10]:
            parsed = parse_period_spanish(v)
            estado = "✅ Parseado OK" if parsed[0] else "❌ NO SE PUDO PARSEAR"
            print(f"   {estado}  →  {v!r}  →  {parsed}")
        if len(valores) > 10:
            print(f"   ... y {len(valores) - 10} más")
        print()