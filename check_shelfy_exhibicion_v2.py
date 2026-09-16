"""
Corré esto con:  python check_shelfy_exhibicion_v2.py
Trae TODO el JSON crudo de Shelfy (sin pasar por el filtro de
get_objetivos_vendedor) y muestra:
  1. Todos los "tipo" distintos que existen hoy en los datos (para ver si
     "exhibicion" sigue llamándose igual, o le cambiaron el nombre).
  2. El JSON completo de 2-3 objetivos de tipo "exhibición" (o parecido),
     para comparar sus campos contra los de otro tipo que sí funciona
     (ej: "compradores").
"""
import json

from utils.shelfy_client import fetch_objetivos_raw

print("=" * 60)
print("Trayendo objetivos de Shelfy (sin caché, forzado)...")
print("=" * 60)
objetivos = fetch_objetivos_raw(forzar=True)
print(f"Total de objetivos traídos: {len(objetivos)}")

if not objetivos:
    print("❌ No se trajo NADA. Revisá SHELFY_USUARIO/SHELFY_PASSWORD en secrets_config.py,")
    print("   o si Shelfy está caído / cambió el login.")
    raise SystemExit(1)

print()
print("=" * 60)
print("PASO 1 — Todos los 'tipo' distintos que aparecen hoy")
print("=" * 60)
tipos_encontrados = sorted({str(o.get("tipo", "")) for o in objetivos})
for t in tipos_encontrados:
    cantidad = sum(1 for o in objetivos if str(o.get("tipo", "")) == t)
    print(f"  {t!r}  ({cantidad} objetivos)")

print()
print("=" * 60)
print("PASO 2 — Buscando cualquier tipo que contenga 'exhib' (por si cambió el nombre)")
print("=" * 60)
candidatos_exhibicion = [o for o in objetivos if "exhib" in str(o.get("tipo", "")).lower()]
print(f"Encontrados: {len(candidatos_exhibicion)}")

if candidatos_exhibicion:
    print("\n--- JSON completo de hasta 3 ejemplos de 'exhibición' ---")
    for o in candidatos_exhibicion[:3]:
        print(json.dumps(o, ensure_ascii=False, indent=2, default=str))
        print("-" * 40)
else:
    print("⚠️  No hay NINGÚN objetivo con 'exhib' en el tipo. Puede que:")
    print("   a) Todavía no esté cargado en Shelfy para el mes actual, o")
    print("   b) Le hayan cambiado el nombre al tipo por completo (no algo parecido a 'exhibicion').")

print()
print("=" * 60)
print("PASO 3 — Comparación: un ejemplo de 'compradores' (que sí funciona)")
print("=" * 60)
ejemplo_compradores = next((o for o in objetivos if o.get("tipo") == "compradores"), None)
if ejemplo_compradores:
    print(json.dumps(ejemplo_compradores, ensure_ascii=False, indent=2, default=str))
else:
    print("(no se encontró ningún ejemplo de 'compradores' para comparar)")