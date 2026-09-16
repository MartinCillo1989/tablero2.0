"""
Corré esto con:  python check_cobertura.py
Reproduce paso a paso, para UN vendedor puntual, exactamente lo mismo que
hace build_cobertura_raw() — mostrando cada etapa intermedia, para ver en
qué punto exacto se pierde/queda vacío el dato.
"""
import pandas as pd

from data.cache import CACHE
from logic.rankings import _filter_ym, _cobertura_por_vendedor, PLACEHOLDERS_MOTIVO

# ⚠️ CAMBIÁ ESTOS VALORES SI HACE FALTA ⚠️
NOMBRE_VENDEDOR = "02-LAMPERT MATIAS"
YEAR  = 2026
MONTH = 9

print("=" * 60)
print("PASO 1 — Recargar CACHE")
print("=" * 60)
CACHE.reload()
print(f"CACHE.vis tiene {len(CACHE.vis)} filas en total (todos los meses).")

print()
print("=" * 60)
print("PASO 2 — Filtrar CACHE.vis por año/mes")
print("=" * 60)
vis_ym = _filter_ym(CACHE.vis, YEAR, MONTH)
print(f"Filas para {YEAR}-{MONTH:02d} (todos los vendedores): {len(vis_ym)}")

if vis_ym.empty:
    print("❌ vis_ym quedó VACÍO — el problema es que CACHE.vis no tiene NADA para este año/mes.")
    print("   Revisá si 'year'/'month' de esas filas están bien calculados (columnas 'year','month' en CACHE.vis).")
    raise SystemExit(1)

print()
print("=" * 60)
print(f"PASO 3 — Filas de {YEAR}-{MONTH:02d} específicas de {NOMBRE_VENDEDOR!r}")
print("=" * 60)
vis_vend = vis_ym[vis_ym["vendedor"] == NOMBRE_VENDEDOR]
print(f"Filas encontradas: {len(vis_vend)}")

if vis_vend.empty:
    print(f"❌ No hay NINGUNA fila para {NOMBRE_VENDEDOR!r} en {YEAR}-{MONTH:02d} dentro de CACHE.vis.")
    print("   Puede ser un problema de cómo se escribe el nombre (espacios, mayúsculas) o de carga del archivo.")
    print()
    print("   Vendedores que SÍ tienen datos este mes (primeros 25):")
    for v in sorted(vis_ym["vendedor"].dropna().unique())[:25]:
        marca = "  <-- FIJATE SI ESTE ES EL CORRECTO" if NOMBRE_VENDEDOR.lower() in v.lower() else ""
        print(f"      {v!r}{marca}")
    raise SystemExit(1)

print("Primeras filas de este vendedor (columnas clave):")
cols_ver = [c for c in ["date", "Hora visita", "Hora venta", "Hora motivo", "Motivo", "vendedor"] if c in vis_vend.columns]
print(vis_vend[cols_ver].head(15).to_string())

print()
print("=" * 60)
print("PASO 4 — Corriendo _cobertura_por_vendedor() sobre TODO el mes (todos los vendedores)")
print("=" * 60)
cobertura_todos = _cobertura_por_vendedor(vis_ym)
print(f"Vendedores en el resultado: {len(cobertura_todos)}")

fila_vend = cobertura_todos[cobertura_todos["vendedor"] == NOMBRE_VENDEDOR]
if fila_vend.empty:
    print(f"❌ {NOMBRE_VENDEDOR!r} NO aparece en el resultado de _cobertura_por_vendedor(),")
    print("   a pesar de tener filas en vis_vend. Raro — revisemos por qué.")
    print()
    print("   ¿La columna 'vendedor' tiene algún espacio de más o algo raro?")
    valores_raros = vis_vend["vendedor"].unique()
    for v in valores_raros:
        print(f"      repr: {v!r}  (len={len(str(v))})")
else:
    print("✅ Encontrado:")
    print(fila_vend.to_string(index=False))

print()
print("=" * 60)
print("PASO 5 — Resultado final de build_cobertura_raw()")
print("=" * 60)
from logic.rankings import build_cobertura_raw
df_cob_raw = build_cobertura_raw(CACHE.vis, YEAR, MONTH)
print(f"Total de filas en df_cob_raw: {len(df_cob_raw)}")
fila_final = df_cob_raw[df_cob_raw["vendedor"] == NOMBRE_VENDEDOR]
if fila_final.empty:
    print(f"❌ {NOMBRE_VENDEDOR!r} NO está en el resultado final de build_cobertura_raw().")
else:
    print("✅ SÍ está en el resultado final:")
    print(fila_final.to_string(index=False))