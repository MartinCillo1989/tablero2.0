import json
import os
import time
from calendar import monthrange
from datetime import date, datetime

import pandas as pd
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


def _rango_mismo_periodo(hoy=None):
    """Devuelve (inicio_actual, fin_actual, inicio_prev, fin_prev) para comparar
    'día 1 hasta hoy' del mes actual contra el mismo rango de días del mes anterior."""
    hoy = hoy or date.today()
    inicio_actual = date(hoy.year, hoy.month, 1)
    fin_actual    = hoy

    if hoy.month == 1:
        prev_year, prev_month = hoy.year - 1, 12
    else:
        prev_year, prev_month = hoy.year, hoy.month - 1

    ultimo_dia_prev = monthrange(prev_year, prev_month)[1]
    dia_corte_prev  = min(hoy.day, ultimo_dia_prev)
    inicio_prev = date(prev_year, prev_month, 1)
    fin_prev    = date(prev_year, prev_month, dia_corte_prev)

    return inicio_actual, fin_actual, inicio_prev, fin_prev


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


def resetear_registro(usuario: str) -> bool:
    """Elimina el registro de Telegram de un usuario (vendedor o supervisor),
    para que se pueda volver a registrar. Devuelve True si existía y se borró,
    False si no estaba registrado."""
    chats = _cargar_chats()
    if usuario in chats:
        del chats[usuario]
        _guardar_chats(chats)
        return True
    return False


def esta_registrado(usuario: str) -> bool:
    return usuario in _cargar_chats()


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
# LISTENER — registra vendedores (por NÚMERO) y supervisores (por usuario)
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


def iniciar_listener(vendedor_map: dict, supervisores: set = None):
    """Loop de long-polling. Corre indefinidamente en un thread aparte.
    - Un vendedor le escribe al bot su NÚMERO (ej: '21') → queda registrado.
    - Un supervisor le escribe su usuario (ej: 'hugo') → queda registrado
      para recibir el resumen diario de su equipo.
    Si el número de vendedor es ambiguo, se le pide que aclare con el nombre completo.
    UNA VEZ REGISTRADO, EL USUARIO QUEDA FIJO: nadie (ni el mismo vendedor) puede
    volver a registrarlo — solo se puede resetear desde el dashboard."""
    if not TELEGRAM_API:
        print("⚠️  TELEGRAM_BOT_TOKEN no configurado — listener de Telegram deshabilitado.")
        return

    supervisores = supervisores or set()

    offset             = _cargar_offset()
    numero_a_usuarios  = _armar_mapa_numeros(vendedor_map)
    nombre_a_usuario   = {vendedor_map[u].strip().lower(): u for u in vendedor_map.keys()}
    supervisores_low   = {s.lower(): s for s in supervisores}
    print("🤖 Listener de Telegram iniciado...")

    def _registrar_vendedor(usuario_real, chat_id, chats):
        if usuario_real in chats:
            _enviar_mensaje(
                chat_id,
                "Ya estás registrado. Si necesitás cambiar algo (por ejemplo cambiaste "
                "de teléfono), pedile a tu supervisor que reinicie tu registro desde el sistema."
            )
            return
        nombre_completo = vendedor_map[usuario_real]
        chats[usuario_real] = chat_id
        _guardar_chats(chats)
        _enviar_mensaje(
            chat_id,
            f"✅ ¡Listo, <b>{nombre_completo}</b>!\n"
            f"Vas a recibir tus objetivos de Corona y Pier &amp; Roll "
            f"todos los días a las {HORA_ENVIO_TELEGRAM}."
        )

    def _registrar_supervisor(usuario_sup, chat_id, chats):
        if usuario_sup in chats:
            _enviar_mensaje(
                chat_id,
                "Ya estás registrado. Si necesitás cambiar algo, pedile a otro "
                "supervisor que reinicie tu registro desde el sistema."
            )
            return
        chats[usuario_sup] = chat_id
        _guardar_chats(chats)
        _enviar_mensaje(
            chat_id,
            f"✅ ¡Listo, <b>{usuario_sup.capitalize()}</b>!\n"
            f"Vas a recibir el resumen diario de tu equipo todos los días a las {HORA_ENVIO_TELEGRAM}."
        )

    while True:
        try:
            # Recargamos los chats en cada vuelta por si se reseteó algún
            # registro desde el dashboard mientras el listener estaba corriendo.
            chats  = _cargar_chats()
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
                        _registrar_vendedor(candidatos[0], chat_id, chats)
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
                    _registrar_vendedor(nombre_a_usuario[texto_low], chat_id, chats)
                elif texto_low in supervisores_low:
                    _registrar_supervisor(supervisores_low[texto_low], chat_id, chats)
                else:
                    _enviar_mensaje(
                        chat_id,
                        "Escribime tu número de vendedor (ej: 21), o si sos supervisor, tu usuario (ej: hugo)."
                    )
        except Exception as e:
            print("⚠️  Error en listener de Telegram:", e)
            time.sleep(5)


# ======================================================
# ARMADO DE MENSAJE POR VENDEDOR (para el propio vendedor)
# ======================================================
def _armar_mensaje(nombre_completo: str, df_corona_raw, df_pr_raw, dias_restantes) -> str:
    lineas = [f"📊 <b>Tus objetivos — {nombre_completo}</b>", ""]

    # ── Corona (con cálculo de unidades/día) ─────────────
    fila_c = df_corona_raw[df_corona_raw["vendedor"] == nombre_completo] if (df_corona_raw is not None and not df_corona_raw.empty) else None
    if fila_c is not None and not fila_c.empty:
        corona     = float(fila_c.iloc[0]["corona"])
        obj_corona = float(fila_c.iloc[0]["obj_corona"])
        pct        = float(fila_c.iloc[0]["pct"])  # ya es corona/base*100 (0-20% es el objetivo)
        cumple     = corona >= obj_corona - 1e-9
        faltante   = max(obj_corona - corona, 0)

        lineas.append(
            f"🚬 <b>Corona</b>: {corona:,.2f} / {obj_corona:,.2f} "
            f"({pct:.1f}%) {'✅' if cumple else '❌'}"
        )

        if not cumple:
            if dias_restantes is None:
                pass  # mes distinto al actual, no aplica
            elif dias_restantes > 0:
                por_dia = faltante / dias_restantes
                lineas.append(
                    f"   👉 Te faltan {faltante:,.2f} unidades de Corona. Con {dias_restantes} "
                    f"día{'s' if dias_restantes != 1 else ''} hábil{'es' if dias_restantes != 1 else ''} "
                    f"que quedan en el mes, necesitás vender {por_dia:.2f}/día para llegar."
                )
            else:
                lineas.append("   ⏰ Ya no quedan días hábiles este mes para llegar al objetivo de Corona.")
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
                pass
            elif dias_restantes > 0:
                por_dia = faltante / dias_restantes
                lineas.append(
                    f"   👉 Te faltan {faltante:,.0f} blisters. Con {dias_restantes} "
                    f"día{'s' if dias_restantes != 1 else ''} hábil{'es' if dias_restantes != 1 else ''} "
                    f"que quedan en el mes, necesitás vender {por_dia:.1f}/día para llegar."
                )
            else:
                lineas.append("   ⏰ Ya no quedan días hábiles este mes para llegar al objetivo.")
    else:
        lineas.append("🍬 <b>Pier &amp; Roll</b>: sin datos este mes.")

    return "\n".join(lineas)


# ======================================================
# HELPERS PARA EL RESUMEN DE SUPERVISORES
# ======================================================
def _cantidades_categoria_vendedor(ven_df: pd.DataFrame, vendedor: str, fecha_ini: date, fecha_fin: date) -> dict:
    """Suma de Cantidades Totales por categoría (Cigarrillos/Varios) para un
    vendedor, filtrando por 'period_start' entre fecha_ini y fecha_fin (inclusive)."""
    resultado = {"Cigarrillos": 0.0, "Varios": 0.0}
    if not isinstance(ven_df, pd.DataFrame) or ven_df.empty:
        return resultado
    if "period_start" not in ven_df.columns or "categoria" not in ven_df.columns or "vendedor" not in ven_df.columns:
        return resultado

    tmp = ven_df[ven_df["vendedor"] == vendedor].copy()
    if tmp.empty:
        return resultado

    ps   = pd.to_datetime(tmp["period_start"], errors="coerce").dt.date
    mask = ps.apply(lambda d: isinstance(d, date) and pd.notna(d) and fecha_ini <= d <= fecha_fin)
    tmp  = tmp[mask]
    if tmp.empty:
        return resultado

    for cat in ["Cigarrillos", "Varios"]:
        resultado[cat] = float(tmp.loc[tmp["categoria"] == cat, "Cantidades Totales"].sum())
    return resultado


def _inicio_cumplimiento_vendedor(jornada_df: pd.DataFrame, vendedor: str, fecha_ini: date, fecha_fin: date):
    """Devuelve (dias_a_horario, dias_totales_con_dato) contando 'Inicio ≤ 9:30'
    entre fecha_ini y fecha_fin para un vendedor, usando el mismo dato que la
    tabla de Jornada del dashboard."""
    if not isinstance(jornada_df, pd.DataFrame) or jornada_df.empty:
        return 0, 0
    if "vendedor" not in jornada_df.columns or "date" not in jornada_df.columns or "inicio_obj" not in jornada_df.columns:
        return 0, 0

    tmp = jornada_df[jornada_df["vendedor"] == vendedor].copy()
    if tmp.empty:
        return 0, 0

    mask = tmp["date"].apply(lambda d: isinstance(d, date) and pd.notna(d) and fecha_ini <= d <= fecha_fin)
    tmp  = tmp[mask]
    tmp  = tmp[tmp["inicio_obj"].isin(["✅", "❌"])]

    total     = len(tmp)
    cumplidos = int((tmp["inicio_obj"] == "✅").sum())
    return cumplidos, total


def _variacion_txt(actual: float, previo: float) -> str:
    if previo <= 0:
        return "—" if actual <= 0 else "▲ (sin datos mes ant.)"
    dif    = (actual - previo) / previo * 100
    flecha = "▲" if dif >= 0 else "▼"
    return f"{flecha} {abs(dif):.1f}%"


def _armar_mensaje_supervisor_vendedor(nombre_completo: str, ven_df, jornada_df, df_corona_raw, df_pr_raw) -> str:
    inicio_actual, fin_actual, inicio_prev, fin_prev = _rango_mismo_periodo()

    cant_actual = _cantidades_categoria_vendedor(ven_df, nombre_completo, inicio_actual, fin_actual)
    cant_prev   = _cantidades_categoria_vendedor(ven_df, nombre_completo, inicio_prev,   fin_prev)

    lineas = [f"👤 <b>{nombre_completo}</b>"]

    lineas.append(
        f"📦 Cigarrillos: {cant_actual['Cigarrillos']:,.2f} "
        f"(mismo período mes ant.: {cant_prev['Cigarrillos']:,.2f}, "
        f"{_variacion_txt(cant_actual['Cigarrillos'], cant_prev['Cigarrillos'])})"
    )
    lineas.append(
        f"🧃 Varios: {cant_actual['Varios']:,.2f} "
        f"(mismo período mes ant.: {cant_prev['Varios']:,.2f}, "
        f"{_variacion_txt(cant_actual['Varios'], cant_prev['Varios'])})"
    )

    # Corona
    fila_c = df_corona_raw[df_corona_raw["vendedor"] == nombre_completo] if (df_corona_raw is not None and not df_corona_raw.empty) else None
    if fila_c is not None and not fila_c.empty:
        corona     = float(fila_c.iloc[0]["corona"])
        obj_corona = float(fila_c.iloc[0]["obj_corona"])
        pct        = float(fila_c.iloc[0]["pct"])
        cumple     = corona >= obj_corona - 1e-9
        lineas.append(f"🚬 Corona: {corona:,.2f} / {obj_corona:,.2f} ({pct:.1f}%) {'✅' if cumple else '❌'}")
    else:
        lineas.append("🚬 Corona: sin datos este mes.")

    # Pier & Roll
    fila_p = df_pr_raw[df_pr_raw["vendedor"] == nombre_completo] if (df_pr_raw is not None and not df_pr_raw.empty) else None
    if fila_p is not None and not fila_p.empty:
        blisters = float(fila_p.iloc[0]["blisters_vendidos"])
        objetivo = float(fila_p.iloc[0]["objetivo_blisters"])
        pct      = (blisters / objetivo * 100) if objetivo > 0 else 0.0
        cumple   = blisters >= objetivo - 1e-9
        lineas.append(f"🍬 Pier &amp; Roll: {blisters:,.0f} / {objetivo:,.0f} ({pct:.1f}%) {'✅' if cumple else '❌'}")
    else:
        lineas.append("🍬 Pier &amp; Roll: sin datos este mes.")

    # Inicio ≤ 9:30 (mismo período, día 1 a hoy)
    cumplidos, total = _inicio_cumplimiento_vendedor(jornada_df, nombre_completo, inicio_actual, fin_actual)
    if total > 0:
        pct_inicio = cumplidos / total * 100
        lineas.append(f"🕒 Inicio ≤9:30: {cumplidos}/{total} días ({pct_inicio:.0f}%)")
    else:
        lineas.append("🕒 Inicio ≤9:30: sin datos este mes.")

    return "\n".join(lineas)


# ======================================================
# ENVÍO A UN SOLO VENDEDOR
# ======================================================
def enviar_objetivos_a_uno(vendedor_map: dict, nombre_completo: str, year=None, month=None):
    """Envía el mensaje de objetivos a UN solo vendedor (nombre completo,
    tal como aparece en la columna 'vendedor' de ventas).
    Devuelve 'ok', 'no_registrado' o 'no_encontrado'."""
    from data.cache import CACHE
    from logic.rankings import build_corona_raw, build_pier_roll_raw

    if not TELEGRAM_API:
        print("⚠️  TELEGRAM_BOT_TOKEN no configurado — no se puede enviar.")
        return "sin_token"

    usuario = next((u for u, n in vendedor_map.items() if n == nombre_completo), None)
    if usuario is None:
        return "no_encontrado"

    chats   = _cargar_chats()
    chat_id = chats.get(usuario)
    if chat_id is None:
        return "no_registrado"

    hoy = date.today()
    y = year  if year  is not None else hoy.year
    m = month if month is not None else hoy.month

    df_corona_raw  = build_corona_raw(CACHE.ven, y, m)
    df_pr_raw      = build_pier_roll_raw(CACHE.ven, y, m)
    dias_restantes = _dias_habiles_restantes(y, m)

    msg = _armar_mensaje(nombre_completo, df_corona_raw, df_pr_raw, dias_restantes)
    _enviar_mensaje(chat_id, msg)
    return "ok"


# ======================================================
# ENVÍO A TODOS LOS VENDEDORES REGISTRADOS
# ======================================================
def enviar_objetivos_a_todos(vendedor_map: dict, year=None, month=None) -> int:
    """Devuelve la cantidad de mensajes enviados."""
    from data.cache import CACHE
    from logic.rankings import build_corona_raw, build_pier_roll_raw

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

    df_corona_raw  = build_corona_raw(CACHE.ven, y, m)
    df_pr_raw      = build_pier_roll_raw(CACHE.ven, y, m)
    dias_restantes = _dias_habiles_restantes(y, m)

    enviados = 0
    for usuario, chat_id in chats.items():
        nombre_completo = vendedor_map.get(usuario)
        if not nombre_completo:
            continue
        msg = _armar_mensaje(nombre_completo, df_corona_raw, df_pr_raw, dias_restantes)
        _enviar_mensaje(chat_id, msg)
        enviados += 1

    print(f"📨 Objetivos enviados por Telegram a {enviados} vendedor/es.")
    return enviados


# ======================================================
# ENVÍO DEL RESUMEN DIARIO A LOS SUPERVISORES
# ======================================================
def enviar_resumen_supervisores(vendedor_map: dict, supervisor_vendedores: dict, year=None, month=None) -> int:
    """Le manda a cada supervisor un mensaje de encabezado + un mensaje por
    cada vendedor de su equipo, con cantidades, objetivos y cumplimiento de
    inicio de jornada. Devuelve la cantidad de supervisores a los que se
    les mandó algo (que ya estaban registrados)."""
    from data.cache import CACHE
    from logic.rankings import build_corona_raw, build_pier_roll_raw

    if not TELEGRAM_API:
        print("⚠️  TELEGRAM_BOT_TOKEN no configurado — no se puede enviar.")
        return 0

    chats = _cargar_chats()
    if not chats:
        print("⚠️  Todavía no hay nadie registrado en Telegram.")
        return 0

    hoy = date.today()
    y = year  if year  is not None else hoy.year
    m = month if month is not None else hoy.month

    df_corona_raw = build_corona_raw(CACHE.ven, y, m)
    df_pr_raw     = build_pier_roll_raw(CACHE.ven, y, m)
    jornada_df    = getattr(CACHE, "jornada_all", None)

    enviados = 0
    for supervisor_usuario, usuarios_vendedores in supervisor_vendedores.items():
        chat_id = chats.get(supervisor_usuario)
        if chat_id is None:
            print(f"⚠️  El supervisor '{supervisor_usuario}' todavía no se registró en Telegram.")
            continue

        fecha_txt = hoy.strftime("%d/%m/%Y")
        _enviar_mensaje(chat_id, f"📋 <b>Resumen diario de tu equipo — {fecha_txt}</b>")

        for usuario_vend in usuarios_vendedores:
            nombre_completo = vendedor_map.get(usuario_vend)
            if not nombre_completo:
                continue
            msg = _armar_mensaje_supervisor_vendedor(nombre_completo, CACHE.ven, jornada_df, df_corona_raw, df_pr_raw)
            _enviar_mensaje(chat_id, msg)

        enviados += 1

    print(f"📨 Resumen diario enviado a {enviados} supervisor/es.")
    return enviados


# ======================================================
# SCHEDULER DIARIO
# ======================================================
def iniciar_scheduler_diario(vendedor_map: dict, supervisor_vendedores: dict = None):
    """Loop que revisa cada 20s si llegó la hora configurada (HORA_ENVIO_TELEGRAM)
    y dispara el envío a vendedores + el resumen a supervisores, una sola vez por día."""
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
            if supervisor_vendedores:
                enviar_resumen_supervisores(vendedor_map, supervisor_vendedores)
            ya_enviado_hoy = hoy
        time.sleep(20)