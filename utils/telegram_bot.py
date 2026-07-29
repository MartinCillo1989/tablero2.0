import json
import os
import time
from calendar import monthrange
from datetime import date, datetime

import requests

from config import BASE_DIR, TELEGRAM_CHATS_FILE, TELEGRAM_OFFSET_FILE, HORA_ENVIO_TELEGRAM

try:
    from secrets_config import TELEGRAM_BOT_TOKEN
except ImportError:
    TELEGRAM_BOT_TOKEN = None

TELEGRAM_API = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}" if TELEGRAM_BOT_TOKEN else None


def _dias_habiles_restantes(anio: int, mes: int):
    """Días hábiles (lunes a viernes) que quedan en el mes, contando desde HOY
    hasta fin de mes inclusive. Devuelve None si el año/mes no es el actual
    (no tiene sentido calcular 'restantes' para un mes que ya pasó)."""
    hoy = date.today()
    if anio != hoy.year or mes != hoy.month:
        return None
    ultimo_dia = monthrange(anio, mes)[1]
    dias = 0
    for d in range(hoy.day, ultimo_dia + 1):
        f = date(anio, mes, d)
        if f.weekday() < 5:  # 0=lunes ... 4=viernes
            dias += 1
    return dias


# ======================================================
# PERSISTENCIA (chats registrados + offset de getUpdates)
# ======================================================
def _cargar_json(path: str) -> dict:
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _guardar_json(path: str, data: dict):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _cargar_chats() -> dict:
    return _cargar_json(TELEGRAM_CHATS_FILE)


def _guardar_chats(chats: dict):
    _guardar_json(TELEGRAM_CHATS_FILE, chats)


def _cargar_offset():
    data = _cargar_json(TELEGRAM_OFFSET_FILE)
    return data.get("offset")


def _guardar_offset(offset):
    _guardar_json(TELEGRAM_OFFSET_FILE, {"offset": offset})


# ======================================================
# ENVÍO DE MENSAJES
# ======================================================
def _enviar_mensaje(chat_id, texto: str):
    if not TELEGRAM_API:
        print("⚠️  TELEGRAM_BOT_TOKEN no configurado — no se puede enviar el mensaje.")
        return
    try:
        requests.post(
            f"{TELEGRAM_API}/sendMessage",
            json={"chat_id": chat_id, "text": texto, "parse_mode": "HTML"},
            timeout=10,
        )
    except Exception as e:
        print("⚠️  Error enviando mensaje Telegram:", e)


# ======================================================
# LISTENER — registra vendedores que escriben su NÚMERO
# ======================================================
def _armar_mapa_numeros(vendedor_map: dict) -> dict:
    """Devuelve {numero: [usuarios]} soportando tanto '05' como '5'."""
    mapa = {}
    for usuario in vendedor_map.keys():
        num = usuario.split("-")[0].strip()
        mapa.setdefault(num, []).append(usuario)
        num_sin_cero = str(int(num)) if num.isdigit() else num
        if num_sin_cero != num:
            mapa.setdefault(num_sin_cero, []).append(usuario)
    return mapa


def iniciar_listener(vendedor_map: dict):
    """Loop de long-polling. Corre indefinidamente en un thread aparte.
    Cuando un vendedor le escribe al bot su NÚMERO de vendedor (ej: '21'),
    queda registrado y a partir de ahí recibe los envíos diarios.
    Si el número es ambiguo (hay más de un vendedor con ese número),
    se le pide que aclare escribiendo su nombre completo."""
    if not TELEGRAM_API:
        print("⚠️  TELEGRAM_BOT_TOKEN no configurado — listener de Telegram deshabilitado.")
        return

    chats           = _cargar_chats()
    offset          = _cargar_offset()
    numero_a_usuarios = _armar_mapa_numeros(vendedor_map)
    nombre_a_usuario  = {vendedor_map[u].strip().lower(): u for u in vendedor_map.keys()}
    print("🤖 Listener de Telegram iniciado...")

    def _registrar(usuario_real, chat_id):
        nombre_completo = vendedor_map[usuario_real]
        chats[usuario_real] = chat_id
        _guardar_chats(chats)
        _enviar_mensaje(
            chat_id,
            f"✅ ¡Listo, <b>{nombre_completo}</b>!\n"
            f"Vas a recibir tus objetivos de Corona y Pier &amp; Roll "
            f"todos los días a las {HORA_ENVIO_TELEGRAM}."
        )

    while True:
        try:
            params = {"timeout": 30}
            if offset is not None:
                params["offset"] = offset
            resp = requests.get(f"{TELEGRAM_API}/getUpdates", params=params, timeout=35)
            data = resp.json()

            for update in data.get("result", []):
                offset = update["update_id"] + 1
                _guardar_offset(offset)

                msg = update.get("message")
                if not msg:
                    continue
                chat_id = msg["chat"]["id"]
                texto   = str(msg.get("text", "")).strip()
                texto_low = texto.lower()

                if texto.isdigit():
                    candidatos = numero_a_usuarios.get(texto, [])
                    if len(candidatos) == 1:
                        _registrar(candidatos[0], chat_id)
                    elif len(candidatos) > 1:
                        nombres = "\n".join(f"- {vendedor_map[u]}" for u in candidatos)
                        _enviar_mensaje(
                            chat_id,
                            f"Hay más de un vendedor con el número {texto}. "
                            f"Escribime tu nombre completo tal cual aparece acá:\n{nombres}"
                        )
                    else:
                        _enviar_mensaje(chat_id, f"No encontré ningún vendedor con el número {texto}.")
                elif texto_low in nombre_a_usuario:
                    _registrar(nombre_a_usuario[texto_low], chat_id)
                else:
                    _enviar_mensaje(chat_id, "Escribime tu número de vendedor (ej: 21).")
        except Exception as e:
            print("⚠️  Error en listener de Telegram:", e)
            time.sleep(5)


# ======================================================
# ARMADO DE MENSAJE POR VENDEDOR
# ======================================================
def _armar_mensaje(nombre_completo: str, df_corona, df_pr_raw, dias_restantes) -> str:
    lineas = [f"📊 <b>Tus objetivos — {nombre_completo}</b>", ""]

    # ── Corona ────────────────────────────────────────────
    fila_c = df_corona[df_corona["Vendedor"] == nombre_completo] if (df_corona is not None and not df_corona.empty) else None
    if fila_c is not None and not fila_c.empty:
        r = fila_c.iloc[0]
        lineas.append(
            f"🚬 <b>Corona</b>: {r['Corona Vendido']} / {r['Obj. Corona (20%)']} "
            f"({r['% Cumpl. Actual']}) {r['Cumple']}"
        )
    else:
        lineas.append("🚬 <b>Corona</b>: sin datos este mes.")

    # ── Pier & Roll (con cálculo de blisters/día) ────────
    fila_p = df_pr_raw[df_pr_raw["vendedor"] == nombre_completo] if (df_pr_raw is not None and not df_pr_raw.empty) else None
    if fila_p is not None and not fila_p.empty:
        blisters = float(fila_p.iloc[0]["blisters_vendidos"])
        objetivo = float(fila_p.iloc[0]["objetivo_blisters"])
        pct      = (blisters / objetivo * 100) if objetivo > 0 else 0.0
        cumple   = blisters >= objetivo - 1e-9
        faltante = max(objetivo - blisters, 0)

        lineas.append(
            f"🍬 <b>Pier &amp; Roll</b>: {blisters:,.0f} / {objetivo:,.0f} "
            f"({pct:.1f}%) {'✅' if cumple else '❌'}"
        )

        if not cumple:
            if dias_restantes is None:
                pass  # mes distinto al actual, no aplica
            elif dias_restantes > 0:
                por_dia = faltante / dias_restantes
                lineas.append(
                    f"   👉 Te faltan {faltante:,.0f} blisters. Con {dias_restantes} "
                    f"día{'s' if dias_restantes != 1 else ''} hábil{'es' if dias_restantes != 1 else ''} "
                    f"que quedan en el mes, necesitás vender {por_dia:.1f} blisters por día para llegar."
                )
            else:
                lineas.append("   ⏰ Ya no quedan días hábiles este mes para llegar al objetivo.")
    else:
        lineas.append("🍬 <b>Pier &amp; Roll</b>: sin datos este mes.")

    return "\n".join(lineas)


# ======================================================
# ENVÍO A TODOS LOS VENDEDORES REGISTRADOS
# ======================================================
def enviar_objetivos_a_todos(vendedor_map: dict, year=None, month=None) -> int:
    """Devuelve la cantidad de mensajes enviados."""
    from data.cache import CACHE
    from logic.rankings import build_corona_ranking, build_pier_roll_raw

    if not TELEGRAM_API:
        print("⚠️  TELEGRAM_BOT_TOKEN no configurado — no se puede enviar.")
        return 0

    chats = _cargar_chats()
    if not chats:
        print("⚠️  Todavía no hay vendedores registrados en Telegram.")
        return 0

    hoy = date.today()
    y = year  if year  is not None else hoy.year
    m = month if month is not None else hoy.month

    df_corona      = build_corona_ranking(CACHE.ven, y, m)
    df_pr_raw      = build_pier_roll_raw(CACHE.ven, y, m)
    dias_restantes = _dias_habiles_restantes(y, m)

    enviados = 0
    for usuario, chat_id in chats.items():
        nombre_completo = vendedor_map.get(usuario)
        if not nombre_completo:
            continue
        msg = _armar_mensaje(nombre_completo, df_corona, df_pr_raw, dias_restantes)
        _enviar_mensaje(chat_id, msg)
        enviados += 1

    print(f"📨 Objetivos enviados por Telegram a {enviados} vendedor/es.")
    return enviados


# ======================================================
# SCHEDULER DIARIO
# ======================================================
def iniciar_scheduler_diario(vendedor_map: dict):
    """Loop que revisa cada 20s si llegó la hora configurada (HORA_ENVIO_TELEGRAM)
    y dispara el envío una sola vez por día."""
    if not TELEGRAM_API:
        print("⚠️  TELEGRAM_BOT_TOKEN no configurado — scheduler diario deshabilitado.")
        return

    print(f"⏰ Scheduler diario de Telegram iniciado (hora configurada: {HORA_ENVIO_TELEGRAM})...")
    ya_enviado_hoy = None
    while True:
        ahora = datetime.now()
        hhmm  = ahora.strftime("%H:%M")
        hoy   = ahora.date()
        if hhmm == HORA_ENVIO_TELEGRAM and ya_enviado_hoy != hoy:
            enviar_objetivos_a_todos(vendedor_map)
            ya_enviado_hoy = hoy
        time.sleep(20)