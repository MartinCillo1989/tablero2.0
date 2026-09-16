"""
Corré esto con:  python check_registrados.py
Te muestra qué vendedores y supervisores YA se registraron en el bot de
Telegram, y cuáles todavía les falta.

Nota: el diccionario VENDEDOR_MAP de acá abajo es una copia del que tenés en
app.py, solo para poder mostrar los nombres completos. Si en algún momento
agregás o sacás vendedores en app.py, actualizalo acá también (o avisame y
te lo dejo leyendo directo de app.py de otra forma más robusta).
"""
import json
import os

from config import TELEGRAM_CHATS_FILE

VENDEDOR_MAP = {
    "01-coria":     "01-CORIA BLAS GUILLE",
    "02-lampert":   "02-LAMPERT MATIAS",
    "03-saldari":   "03-SALDARI DANIEL",
    "04-nicolas":   "04-NICOLAS MANUEL SEGURA",
    "05-palermo":   "05-GUSTAVO PALERMO",
    "06-fraile":    "06-FRAILE BIBIANA",
    "07-munoz":     "07-MUÑOZ ESTEBAN",
    "08-dauria":    "08-DAURIA NEYEM ELIA",
    "09-rumin":     "09-RUMIN GERMAN",
    "10-marche":    "10-MARCHE FERNANDO",
    "11-solano":    "11-SOLANO MARINA",
    "12-mercado":   "12-MERCADO RAFAEL",
    "13-reynoso":   "13-REYNOSO ENZO PAT",
    "14-solia":     "14-SOLIA WALTER",
    "15-meli":      "15-MARCOS EZEQUIEL MELI",
    "16-tamagnini": "16-TAMAGNINI MARCOS",
    "17-rugger":    "17-RUGGER SEBASTIAN",
    "18-allende":   "18-CESAR ALLENDE",
    "19-cabrera":   "19-JOEL CABRERA",
    "20-passaponti":"20-JOAQUIN PASSAPONTI",
    "21-ferreyra":  "21-FERREYRA MAURICIO EMANUEL",
}

SUPERVISORES = {"hugo", "ariel", "matias", "martin"}

if not os.path.exists(TELEGRAM_CHATS_FILE):
    chats = {}
else:
    with open(TELEGRAM_CHATS_FILE, "r", encoding="utf-8") as f:
        chats = json.load(f)

print("=" * 60)
print("VENDEDORES")
print("=" * 60)
registrados = []
faltantes = []
for usuario, nombre_completo in VENDEDOR_MAP.items():
    if usuario in chats:
        registrados.append(nombre_completo)
    else:
        faltantes.append(nombre_completo)

print(f"\n✅ Registrados ({len(registrados)} de {len(VENDEDOR_MAP)}):")
for n in sorted(registrados):
    print(f"   • {n}")

print(f"\n❌ TODAVÍA NO se registraron ({len(faltantes)}):")
for n in sorted(faltantes):
    print(f"   • {n}")

print()
print("=" * 60)
print("SUPERVISORES")
print("=" * 60)
for s in sorted(SUPERVISORES):
    estado = "✅ Registrado" if s in chats else "❌ No registrado"
    print(f"   {s.capitalize():15} {estado}")