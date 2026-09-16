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
def _enviar_mensaje(chat_id, texto: str) -> bool:
    """Envía un mensaje por Telegram. Devuelve True si Telegram confirmó la
    entrega (status 200 y 'ok': true), False en cualquier otro caso."""
    if not TELEGRAM_API:
        print("⚠️  TELEGRAM_BOT_TOKEN no configurado — no se puede enviar el mensaje.")
        return False
    try:
        r = requests.post(
            f"{TELEGRAM_API}/sendMessage",
            json={"chat_id": chat_id, "text": texto, "parse_mode": "HTML"},
            timeout=10,
        )
        try:
            data = r.json()
        except Exception:
            data = {}
        if r.status_code != 200 or not data.get("ok", False):
            print(f"⚠️  Telegram rechazó el mensaje a chat_id={chat_id}: "
                  f"status={r.status_code} respuesta={data}")
            return False
        return True
    except Exception as e:
        print(f"⚠️  Error enviando mensaje Telegram a chat_id={chat_id}:", e)
        return False


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
            f"Vas a recibir tus objetivos de Corona, Pier &amp; Roll y Cobertura "
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

                # Si este chat ya está registrado (vendedor o supervisor), no
                # respondemos NADA más — ignoramos el mensaje en silencio.
                if chat_id in chats.values():
                    continue

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
def _armar_mensaje(nombre_completo: str, df_corona_raw, df_pr_raw, df_cob_raw, dias_restantes) -> str:
    lineas = [f"📊 <b>Tus objetivos — {nombre_completo}</b>", ""]

    # ── Corona ────────────────────────────────────────────
    fila_c = df_corona_raw[df_corona_raw["vendedor"] == nombre_completo] if (df_corona_raw is not None and not df_corona_raw.empty) else None
    if fila_c is not None and not fila_c.empty:
        corona     = float(fila_c.iloc[0]["corona"])
        obj_corona = float(fila_c.iloc[0]["obj_corona"])
        pct        = (corona / obj_corona * 100) if obj_corona > 0 else 0.0  # 100% = objetivo cumplido
        cumple     = corona >= obj_corona - 1e-9

        lineas.append(
            f"🚬 <b>Corona</b>: {corona:,.2f} (Bultos vendidos) / {obj_corona:,.2f} (Bultos objetivo) "
            f"({pct:.1f}%) {'✅' if cumple else '❌'}"
        )
    else:
        lineas.append("🚬 <b>Corona</b>: sin datos este mes.")

    # ── Pier & Roll ───────────────────────────────────────
    fila_p = df_pr_raw[df_pr_raw["vendedor"] == nombre_completo] if (df_pr_raw is not None and not df_pr_raw.empty) else None
    if fila_p is not None and not fila_p.empty:
        blisters = float(fila_p.iloc[0]["blisters_vendidos"])
        objetivo = float(fila_p.iloc[0]["objetivo_blisters"])
        pct      = (blisters / objetivo * 100) if objetivo > 0 else 0.0
        cumple   = blisters >= objetivo - 1e-9

        lineas.append(
            f"📜 <b>Pier &amp; Roll</b>: {blisters:,.0f} / {objetivo:,.0f} "
            f"({pct:.1f}%) {'✅' if cumple else '❌'}"
        )
    else:
        lineas.append("📜 <b>Pier &amp; Roll</b>: sin datos este mes.")

    # ── Objetivos Shelfy (compradores / exhibición / alteo / activación) ──
    try:
        from utils.shelfy_client import get_objetivos_vendedor
        hoy = date.today()
        objetivos_shelfy = get_objetivos_vendedor(nombre_completo, hoy.year, hoy.month)
    except Exception as e:
        objetivos_shelfy = []
        print("⚠️  Error consultando objetivos de Shelfy:", e)

    if objetivos_shelfy:
        for obj in objetivos_shelfy:
            lineas.append(
                f"{obj['label']}: {obj['actual']:,.0f} / {obj['objetivo']:,.0f} "
                f"({obj['pct']:.0f}%) {'✅' if obj['cumplido'] else '❌'}"
            )

    # ── Cobertura (informativo, no es un objetivo más) ───────
    lineas.append("")
    fila_cob = df_cob_raw[df_cob_raw["vendedor"] == nombre_completo] if (df_cob_raw is not None and not df_cob_raw.empty) else None
    if fila_cob is not None and not fila_cob.empty:
        visitados    = int(fila_cob.iloc[0]["visitados"])
        total        = int(fila_cob.iloc[0]["total"])
        pct          = float(fila_cob.iloc[0]["pct"])
        objetivo_pct = float(fila_cob.iloc[0]["objetivo_pct"])
        cumple       = pct >= objetivo_pct - 1e-9

        lineas.append(
            f"🗺️ <b>Cobertura</b>: {pct:.0f}% / {objetivo_pct:.0f}% "
            f"{'✅' if cumple else '❌'} ({visitados} de {total} visitados)"
        )
    else:
        lineas.append("🗺️ <b>Cobertura</b>: sin datos este mes.")

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


def _armar_mensaje_supervisor_vendedor(nombre_completo: str, ven_df, jornada_df, df_corona_raw, df_pr_raw, df_cob_raw=None) -> str:
    inicio_actual, fin_actual, inicio_prev, fin_prev = _rango_mismo_periodo()

    lineas = [f"👤 <b>{nombre_completo}</b>"]

    # Corona
    fila_c = df_corona_raw[df_corona_raw["vendedor"] == nombre_completo] if (df_corona_raw is not None and not df_corona_raw.empty) else None
    if fila_c is not None and not fila_c.empty:
        corona     = float(fila_c.iloc[0]["corona"])
        obj_corona = float(fila_c.iloc[0]["obj_corona"])
        pct        = (corona / obj_corona * 100) if obj_corona > 0 else 0.0  # 100% = objetivo cumplido
        cumple     = corona >= obj_corona - 1e-9
        lineas.append(f"🚬 Corona: {corona:,.2f}(Bultos vendidos) / {obj_corona:,.2f} (Bultos objetivo), ({pct:.1f}%) {'✅' if cumple else '❌'}")
    else:
        lineas.append("🚬 Corona: sin datos este mes.")

    # Pier & Roll
    fila_p = df_pr_raw[df_pr_raw["vendedor"] == nombre_completo] if (df_pr_raw is not None and not df_pr_raw.empty) else None
    if fila_p is not None and not fila_p.empty:
        blisters = float(fila_p.iloc[0]["blisters_vendidos"])
        objetivo = float(fila_p.iloc[0]["objetivo_blisters"])
        pct      = (blisters / objetivo * 100) if objetivo > 0 else 0.0
        cumple   = blisters >= objetivo - 1e-9
        lineas.append(f"📜 Pier &amp; Roll: {blisters:,.0f} (Blisters vendidos) / {objetivo:,.0f} (Blisters objetivo), ({pct:.1f}%) {'✅' if cumple else '❌'}")
    else:
        lineas.append("📜 Pier &amp; Roll: sin datos este mes.")

    # Objetivos Shelfy (compradores / exhibición / alteo / activación)
    try:
        from utils.shelfy_client import get_objetivos_vendedor
        hoy = date.today()
        objetivos_shelfy = get_objetivos_vendedor(nombre_completo, hoy.year, hoy.month)
    except Exception as e:
        objetivos_shelfy = []
        print("⚠️  Error consultando objetivos de Shelfy:", e)

    if objetivos_shelfy:
        for obj in objetivos_shelfy:
            lineas.append(
                f"{obj['label']}: {obj['actual']:,.0f} / {obj['objetivo']:,.0f} "
                f"({obj['pct']:.0f}%) {'✅' if obj['cumplido'] else '❌'}"
            )

    # Inicio ≤ 9:30 (mismo período, día 1 a hoy)
    cumplidos, total = _inicio_cumplimiento_vendedor(jornada_df, nombre_completo, inicio_actual, fin_actual)
    if total > 0:
        pct_inicio = cumplidos / total * 100
        lineas.append(f"🕒 Inicio ≤9:30: {cumplidos}/{total} días ({pct_inicio:.0f}%)")
    else:
        lineas.append("🕒 Inicio ≤9:30: sin datos este mes.")

    # Cobertura
    fila_cob = df_cob_raw[df_cob_raw["vendedor"] == nombre_completo] if (df_cob_raw is not None and not df_cob_raw.empty) else None
    if fila_cob is not None and not fila_cob.empty:
        visitados    = int(fila_cob.iloc[0]["visitados"])
        total_cob    = int(fila_cob.iloc[0]["total"])
        pct_cob      = float(fila_cob.iloc[0]["pct"])
        objetivo_pct = float(fila_cob.iloc[0]["objetivo_pct"])
        cumple_cob   = pct_cob >= objetivo_pct - 1e-9
        lineas.append(
            f"🗺️ Cobertura: {pct_cob:.0f}% / {objetivo_pct:.0f}% "
            f"{'✅' if cumple_cob else '❌'} ({visitados} de {total_cob} visitados)"
        )
    else:
        lineas.append("🗺️ Cobertura: sin datos este mes.")

    return "\n".join(lineas)


# ======================================================
# ENVÍO A UN SOLO VENDEDOR
# ======================================================
def enviar_objetivos_a_uno(vendedor_map: dict, nombre_completo: str, year=None, month=None):
    """Envía el mensaje de objetivos a UN solo vendedor (nombre completo,
    tal como aparece en la columna 'vendedor' de ventas).
    Devuelve 'ok', 'no_registrado' o 'no_encontrado'."""
    from data.cache import CACHE
    from logic.rankings import build_corona_raw, build_pier_roll_raw, build_cobertura_raw

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
    df_cob_raw     = build_cobertura_raw(CACHE.vis, y, m)
    dias_restantes = _dias_habiles_restantes(y, m)

    msg = _armar_mensaje(nombre_completo, df_corona_raw, df_pr_raw, df_cob_raw, dias_restantes)
    _enviar_mensaje(chat_id, msg)
    return "ok"


# ======================================================
# ENVÍO A TODOS LOS VENDEDORES REGISTRADOS
# ======================================================
def enviar_objetivos_a_todos(vendedor_map: dict, year=None, month=None) -> int:
    """Devuelve la cantidad de mensajes enviados."""
    from data.cache import CACHE
    from logic.rankings import build_corona_raw, build_pier_roll_raw, build_cobertura_raw

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
    df_cob_raw     = build_cobertura_raw(CACHE.vis, y, m)
    dias_restantes = _dias_habiles_restantes(y, m)

    enviados = 0
    for usuario, chat_id in chats.items():
        nombre_completo = vendedor_map.get(usuario)
        if not nombre_completo:
            continue
        msg = _armar_mensaje(nombre_completo, df_corona_raw, df_pr_raw, df_cob_raw, dias_restantes)
        _enviar_mensaje(chat_id, msg)
        enviados += 1

    print(f"📨 Objetivos enviados por Telegram a {enviados} vendedor/es.")
    return enviados


# ======================================================
# ENVÍO DEL RESUMEN DIARIO A LOS SUPERVISORES
# ======================================================
def enviar_resumen_supervisores(vendedor_map: dict, supervisor_vendedores: dict, year=None, month=None) -> int:
    """Le manda a cada supervisor un mensaje de encabezado + un mensaje por
    cada vendedor de su equipo, con cantidades, objetivos, cobertura y
    cumplimiento de inicio de jornada. Devuelve la cantidad de supervisores
    a los que se les mandó algo (que ya estaban registrados)."""
    from data.cache import CACHE
    from logic.rankings import build_corona_raw, build_pier_roll_raw, build_cobertura_raw

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
    df_cob_raw    = build_cobertura_raw(CACHE.vis, y, m)
    jornada_df    = getattr(CACHE, "jornada_all", None)

    enviados = 0
    for supervisor_usuario, usuarios_vendedores in supervisor_vendedores.items():
        chat_id = chats.get(supervisor_usuario)
        if chat_id is None:
            print(f"⚠️  El supervisor '{supervisor_usuario}' todavía no se registró en Telegram.")
            continue

        fecha_txt = hoy.strftime("%d/%m/%Y")
        ok_header = _enviar_mensaje(chat_id, f"📋 <b>Resumen diario de tu equipo — {fecha_txt}</b>")
        if not ok_header:
            print(f"⚠️  No se pudo enviar el encabezado al supervisor '{supervisor_usuario}' (chat_id={chat_id}). Salteando su equipo.")
            continue

        for usuario_vend in usuarios_vendedores:
            nombre_completo = vendedor_map.get(usuario_vend)
            if not nombre_completo:
                continue
            msg = _armar_mensaje_supervisor_vendedor(nombre_completo, CACHE.ven, jornada_df, df_corona_raw, df_pr_raw, df_cob_raw)
            ok = _enviar_mensaje(chat_id, msg)
            if not ok:
                print(f"⚠️  Falló el envío del vendedor '{usuario_vend}' al supervisor '{supervisor_usuario}'.")

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