"""
Corré esto con:  python test_enviar_supervisor.py
Manda el mensaje que le llegaría a un SUPERVISOR sobre UN vendedor puntual
(el mismo formato que usa enviar_resumen_supervisores), pero directo a tu
propio chat_id — no toca el envío real a Hugo/Ariel/Martin.

Antes de correr, cambiá las dos variables de abajo:
- MI_CHAT_ID: tu chat_id (el mismo que usaste en test_enviar_mensaje.py)
- NOMBRE_VENDEDOR: el vendedor sobre el que querés ver el resumen
"""
from datetime import date

from data.cache import CACHE
from logic.rankings import build_corona_raw, build_pier_roll_raw
from utils.telegram_bot import _armar_mensaje_supervisor_vendedor, _enviar_mensaje

# ⚠️ CAMBIÁ ESTOS DOS VALORES ⚠️
MI_CHAT_ID       = 8165958363
NOMBRE_VENDEDOR  = "02-LAMPERT MATIAS"

CACHE.reload()

hoy = date.today()
df_corona_raw = build_corona_raw(CACHE.ven, hoy.year, hoy.month)
df_pr_raw     = build_pier_roll_raw(CACHE.ven, hoy.year, hoy.month)
jornada_df    = getattr(CACHE, "jornada_all", None)

# El mensaje de encabezado que también le llega al supervisor (una vez, no por vendedor)
fecha_txt = hoy.strftime("%d/%m/%Y")
encabezado = f"📋 <b>Resumen diario de tu equipo — {fecha_txt}</b>"

msg = _armar_mensaje_supervisor_vendedor(NOMBRE_VENDEDOR, CACHE.ven, jornada_df, df_corona_raw, df_pr_raw)

print("=" * 60)
print("ENCABEZADO:")
print("=" * 60)
print(encabezado)
print()
print("=" * 60)
print("MENSAJE DEL VENDEDOR:")
print("=" * 60)
print(msg)
print("=" * 60)

_enviar_mensaje(MI_CHAT_ID, encabezado)
_enviar_mensaje(MI_CHAT_ID, msg)
print(f"✅ Mandado a chat_id {MI_CHAT_ID}")