"""
Corré esto con:  python test_enviar_mensaje.py
Manda el mensaje de "objetivos" de UN vendedor real (con datos reales) a tu
propio chat_id, sin tocar registros de nadie. Sirve para ver cómo queda el
mensaje sin mandárselo al vendedor de verdad.

Antes de correr, cambiá las dos variables de abajo:
- MI_CHAT_ID: el que te dio get_mi_chat_id.py
- NOMBRE_VENDEDOR: el nombre completo tal cual aparece en tu VENDEDOR_MAP,
  ej: "21-FERREYRA MAURICIO EMANUEL"
"""
from datetime import date

from data.cache import CACHE
from logic.rankings import build_corona_raw, build_pier_roll_raw, build_cobertura_raw
from utils.telegram_bot import _armar_mensaje, _enviar_mensaje, _dias_habiles_restantes

# ⚠️ CAMBIÁ ESTOS DOS VALORES ⚠️
MI_CHAT_ID       = 8165958363
NOMBRE_VENDEDOR  = "15-MARCOS EZEQUIEL MELI"

CACHE.reload()

hoy = date.today()
df_corona_raw  = build_corona_raw(CACHE.ven, hoy.year, hoy.month)
df_pr_raw      = build_pier_roll_raw(CACHE.ven, hoy.year, hoy.month)
df_cob_raw     = build_cobertura_raw(CACHE.vis, hoy.year, hoy.month)
dias_restantes = _dias_habiles_restantes(hoy.year, hoy.month)

msg = _armar_mensaje(NOMBRE_VENDEDOR, df_corona_raw, df_pr_raw, df_cob_raw, dias_restantes)

print("=" * 60)
print("MENSAJE QUE SE VA A MANDAR:")
print("=" * 60)
print(msg)
print("=" * 60)

_enviar_mensaje(MI_CHAT_ID, msg)
print(f"✅ Mandado a chat_id {MI_CHAT_ID}")