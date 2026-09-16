"""
Corré esto con:  python check_rutas_por_vendedor.py
Consulta DIRECTO en Python (sin pasar por el navegador ni por Dash) qué
valores de "Ruta" tiene realmente un vendedor puntual en CACHE.vis.
"""
from data.cache import CACHE

# ⚠️ CAMBIÁ ESTE VALOR por el vendedor que estabas probando ⚠️
NOMBRE_VENDEDOR = "04-NICOLAS MANUEL SEGURA"

CACHE.reload()

df = CACHE.vis
print(f"Total de filas en CACHE.vis: {len(df)}")
print(f"Columnas disponibles: {list(df.columns)}\n")

if "vendedor" not in df.columns:
    print("⚠️  No hay columna 'vendedor' en CACHE.vis.")
    raise SystemExit(0)

# Vendedores que existen tal cual, para comparar con el nombre que pusiste arriba
print("Vendedores únicos en CACHE.vis (primeros 25):")
for v in sorted(df["vendedor"].dropna().unique())[:25]:
    marca = "  <-- este es el que buscás" if v == NOMBRE_VENDEDOR else ""
    print(f"   {v!r}{marca}")

print()
df_v = df[df["vendedor"] == NOMBRE_VENDEDOR]
print(f"Filas que matchean exactamente {NOMBRE_VENDEDOR!r}: {len(df_v)}")

if "Ruta" not in df.columns:
    print("⚠️  No hay columna 'Ruta' en CACHE.vis.")
    raise SystemExit(0)

print(f"\nValores de 'Ruta' que tiene ESE vendedor:")
rutas_de_ese_vendedor = sorted(df_v["Ruta"].dropna().astype(str).str.strip().unique())
for r in rutas_de_ese_vendedor:
    print(f"   {r!r}")

print(f"\nTotal de rutas distintas de ese vendedor: {len(rutas_de_ese_vendedor)}")

# Buscamos específicamente si "19-LUNES" (o similar) aparece
sospechosas = [r for r in rutas_de_ese_vendedor if r.strip().startswith("19")]
if sospechosas:
    print(f"\n⚠️  SÍ aparecen rutas que empiezan con '19' para este vendedor: {sospechosas}")
    print("   (Esto explicaría por qué el dropdown las muestra — no sería un bug.)")
else:
    print(f"\n✅ NO aparece ninguna ruta que empiece con '19' para este vendedor en los datos reales.")
    print("   (Esto confirma que el problema es del dropdown, no de los datos.)")