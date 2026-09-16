"""
Diagnóstico: reproduce paso a paso lo que hace el callback
'cargar_tabla_rutas' de ui/callbacks/combustible.py, para ver en qué
momento se pierden las filas.

Uso:
    python diagnostico_rutas.py            -> mes actual
    python diagnostico_rutas.py 2026 8      -> agosto 2026
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from datetime import date

print("1) Importando VENDEDOR_MAP desde app.py...")
try:
    from app import VENDEDOR_MAP
    print(f"   OK — {len(VENDEDOR_MAP)} vendedores encontrados.")
except Exception as e:
    print(f"   ❌ FALLÓ el import de app.py: {e}")
    sys.exit(1)

print("\n2) Importando funciones de logic/pagos_combustible.py...")
try:
    from logic.pagos_combustible import obtener_ruta_mes, asegurar_rutas_mes, DIAS_SEMANA
    print("   OK")
except Exception as e:
    print(f"   ❌ FALLÓ el import de logic/pagos_combustible.py: {e}")
    sys.exit(1)

if len(sys.argv) >= 3:
    year, month = int(sys.argv[1]), int(sys.argv[2])
else:
    hoy = date.today()
    year, month = hoy.year, hoy.month

print(f"\n3) Mes a probar: {month:02d}/{year}")

vendedores = sorted(VENDEDOR_MAP.values())
print(f"   Vendedores a procesar: {len(vendedores)}")
print(f"   Primeros 3: {vendedores[:3]}")

print("\n4) Corriendo asegurar_rutas_mes (copia automática del mes anterior)...")
try:
    copiados = asegurar_rutas_mes(vendedores, year, month)
    print(f"   OK — se copiaron {copiados} rutas desde meses anteriores.")
except Exception as e:
    print(f"   ❌ FALLÓ asegurar_rutas_mes: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("\n5) Armando las filas de la tabla (igual que el callback)...")
rows = []
try:
    for vendedor in vendedores:
        kms_por_dia = obtener_ruta_mes(vendedor, year, month)
        row = {"vendedor": vendedor}
        for dia in DIAS_SEMANA:
            row[dia] = kms_por_dia.get(dia, 0) or None
        rows.append(row)
    print(f"   OK — se armaron {len(rows)} filas.")
except Exception as e:
    print(f"   ❌ FALLÓ armando las filas: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print(f"\n{'='*70}")
print("RESULTADO — primeras 5 filas que debería mostrar la tabla:")
print(f"{'='*70}")
for row in rows[:5]:
    print(row)

if not rows:
    print("\n⚠️  La lista de filas está VACÍA. Eso explicaría la tabla vacía en pantalla.")
else:
    print(f"\n✅ Hay {len(rows)} filas. Si en el navegador la tabla sigue vacía, el problema")
    print("   está en el callback de Dash (permisos de admin) o en el layout, no en los datos.")