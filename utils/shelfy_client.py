"""
Cliente para la API de Shelfy (https://shelfycenter.com).
Hace login con usuario/password (guardados en secrets_config.py), pide el
listado de objetivos de la distribuidora, y expone helpers para consultar
los objetivos de un vendedor puntual en un mes puntual.

Credenciales esperadas en secrets_config.py:
    SHELFY_USUARIO = "..."
    SHELFY_PASSWORD = "..."
(ese archivo NO se sube a git, igual que TELEGRAM_BOT_TOKEN)

OJO: el endpoint /api/supervision/objetivos/{id} devuelve TODO el historial
de objetivos (con fotos, ítems, etc.), así que la respuesta es pesada y puede
tardar bastante. Por eso cacheamos el resultado en memoria por unos minutos,
en vez de pedirlo de nuevo por cada vendedor al que le mandamos el mensaje.
"""

import time

import requests

from config import SHELFY_BASE_URL, SHELFY_ID_DISTRIBUIDOR

try:
    from secrets_config import SHELFY_USUARIO, SHELFY_PASSWORD
except ImportError:
    SHELFY_USUARIO = None
    SHELFY_PASSWORD = None


# Etiquetas legibles para cada "tipo" de objetivo que devuelve Shelfy
TIPO_LABELS = {
    "compradores":       "🛒 Compradores",
    "exhibicion":        "📸 Exhibición",
    "ruteo_alteo":       "📍 Alteo",
    "conversion_estado": "🟢 Activación",
    "conversion_mix":    "🔄 Mix de Conversión",
}

# Cuánto tiempo (segundos) reusamos la última respuesta antes de volver a
# pedirle todo el historial a Shelfy. 300 = 5 minutos.
CACHE_TTL_SEGUNDOS = 300

# Timeout de la request GET de objetivos. La respuesta es pesada (todo el
# historial), así que le damos bastante margen.
GET_TIMEOUT_SEGUNDOS = 60

_cache = {
    "objetivos":  None,   # última lista de objetivos traída con éxito
    "fetched_at": 0.0,    # timestamp (time.time()) de esa última traída
}


def _login():
    """Devuelve el access_token (str), o None si falla el login."""
    if not SHELFY_USUARIO or not SHELFY_PASSWORD:
        print("⚠️  SHELFY_USUARIO / SHELFY_PASSWORD no configurados en secrets_config.py")
        return None
    try:
        resp = requests.post(
            f"{SHELFY_BASE_URL}/auth/login",
            json={"usuario": SHELFY_USUARIO, "password": SHELFY_PASSWORD},
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
        return data.get("access_token")
    except Exception as e:
        print("⚠️  Error haciendo login en Shelfy:", e)
        return None


def fetch_objetivos_raw(forzar: bool = False) -> list:
    """Trae TODOS los objetivos de la distribuidora (todos los meses),
    usando una caché en memoria de CACHE_TTL_SEGUNDOS para no golpear la API
    una vez por cada vendedor. Pasá forzar=True para saltear la caché.
    Devuelve [] si nunca se pudo traer nada."""
    ahora = time.time()
    cache_vigente = (
        _cache["objetivos"] is not None
        and (ahora - _cache["fetched_at"]) < CACHE_TTL_SEGUNDOS
    )
    if cache_vigente and not forzar:
        return _cache["objetivos"]

    token = _login()
    if not token:
        # Si falla el login pero tenemos algo viejo en caché, mejor devolver
        # eso que nada (aunque esté un poco desactualizado).
        return _cache["objetivos"] or []

    try:
        resp = requests.get(
            f"{SHELFY_BASE_URL}/api/supervision/objetivos/{SHELFY_ID_DISTRIBUIDOR}",
            headers={"Authorization": f"Bearer {token}"},
            timeout=GET_TIMEOUT_SEGUNDOS,
        )
        resp.raise_for_status()
        data = resp.json()
        _cache["objetivos"]  = data
        _cache["fetched_at"] = ahora
        return data
    except Exception as e:
        print("⚠️  Error trayendo objetivos de Shelfy:", e)
        # Igual que arriba: preferimos devolver la caché vieja (si hay) a
        # devolver una lista vacía y que el mensaje quede sin esa sección.
        return _cache["objetivos"] or []


def _mes_str(year: int, month: int) -> str:
    return f"{year:04d}-{month:02d}"


def get_objetivos_vendedor(nombre_vendedor: str, year: int, month: int) -> list:
    """Devuelve los objetivos de Shelfy de UN vendedor para un mes puntual,
    ya formateados y listos para mostrar. Cada item:
    {"label": "🛒 Compradores", "actual": 91.0, "objetivo": 140.0,
     "cumplido": False, "pct": 65.0}
    """
    objetivos = fetch_objetivos_raw()
    if not objetivos:
        return []

    mes_target = _mes_str(year, month)
    resultado = []
    for o in objetivos:
        if o.get("nombre_vendedor") != nombre_vendedor:
            continue

        # Algunos tipos de objetivo (ej: "exhibicion") NO usan el campo
        # "mes_referencia" (viene null) — en su lugar usan "fecha_inicio"
        # para indicar a qué mes pertenecen. Si mes_referencia está
        # presente lo usamos (comportamiento de siempre); si no, caemos
        # a fecha_inicio en vez de descartar el objetivo directamente.
        mes_ref = o.get("mes_referencia")
        if mes_ref:
            if not str(mes_ref).startswith(mes_target):
                continue
        else:
            fecha_inicio = str(o.get("fecha_inicio") or "")
            if not fecha_inicio.startswith(mes_target):
                continue

        tipo = o.get("tipo", "")
        label = TIPO_LABELS.get(tipo) or f"🎯 {tipo.replace('_', ' ').capitalize()}"
        objetivo = float(o.get("valor_objetivo") or 0)
        actual = float(o.get("valor_actual") or 0)
        pct = (actual / objetivo * 100) if objetivo > 0 else 0.0

        resultado.append({
            "label":     label,
            "actual":    actual,
            "objetivo":  objetivo,
            "cumplido":  bool(o.get("cumplido")),
            "pct":       pct,
        })

    return resultado