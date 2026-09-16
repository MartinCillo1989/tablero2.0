"""
Corré esto con:  python check_shelfy_exhibicion.py
Muestra el JSON COMPLETO (todos los campos, no solo los que ya usamos) de
las entradas de tipo "exhibicion" que devuelve Shelfy, para ver si hay
info sobre qué clientes/filtro se usa para ese objetivo.
"""
import json

from utils.shelfy_client import fetch_objetivos_raw

objetivos = fetch_objetivos_raw(forzar=True)
print(f"Total de objetivos traídos: {len(objetivos)}\n")

exhibicion = [o for o in objetivos if o.get("tipo") == "exhibicion"]
print(f"Objetivos de tipo 'exhibicion': {len(exhibicion)}\n")

if not exhibicion:
    print("No encontré ninguno de tipo 'exhibicion'. Tipos que SÍ aparecen en tus datos:")
    tipos = sorted(set(o.get("tipo") for o in objetivos))
    for t in tipos:
        print(f"   - {t}")
else:
    print("=" * 70)
    print("JSON COMPLETO de las primeras 3 entradas de tipo 'exhibicion':")
    print("=" * 70)
    for o in exhibicion[:3]:
        print(json.dumps(o, indent=2, ensure_ascii=False, default=str))
        print("-" * 70)

    print("\nTODAS las claves (campos) que aparecen en estas entradas:")
    claves = set()
    for o in exhibicion:
        claves.update(o.keys())
    for k in sorted(claves):
        print(f"   - {k}")