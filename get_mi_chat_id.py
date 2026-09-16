"""
Corré esto con:  python get_mi_chat_id.py
Te va a mostrar el chat_id del último mensaje que le mandaste al bot.
Usalo para probar el envío de mensajes directo a tu celular.
"""
import requests
from config import BASE_DIR
try:
    from secrets_config import TELEGRAM_BOT_TOKEN
except ImportError:
    TELEGRAM_BOT_TOKEN = None

if not TELEGRAM_BOT_TOKEN:
    print("❌ No encontré TELEGRAM_BOT_TOKEN en secrets_config.py")
    raise SystemExit(1)

resp = requests.get(f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getUpdates", timeout=15)
data = resp.json()
resultados = data.get("result", [])

if not resultados:
    print("⚠️  No hay mensajes recientes. Mandale un mensaje cualquiera al bot desde tu celu y corré esto de nuevo.")
else:
    ultimo = resultados[-1]
    msg = ultimo.get("message", {})
    chat = msg.get("chat", {})
    print(f"✅ chat_id: {chat.get('id')}")
    print(f"   Nombre: {chat.get('first_name')} {chat.get('last_name', '')}")
    print(f"   Texto del último mensaje: {msg.get('text')!r}")