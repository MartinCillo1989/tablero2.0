"""
chesserp_ventas.py — Descarga automática del "Reporte de Comprobantes de
Venta" (detallado) desde ChessERP, para saber la fecha real de la última
compra de cada cliente — incluidas las ventas fuera de la ruta habitual,
que el archivo de Visitas no registra.

Login propio, copiado del mismo mecanismo ya probado en sistema_v3
(chesserp_sync.py) — no depende de ningún otro proyecto.

Endpoints reales (confirmados con DevTools):
  POST /AR1252/web/api/reporteComprobantesVta/exportarExcel
       body: {"dsFiltrosRepCbtsVta": {"eFiltros": [{... fechadesde, fechahasta ...}]}, "pcTipo": "C"}
       response: {"pcArchivo": "/static/downloads/XXXXX.xlsx", "error": []}
  GET  {BASE_URL}{pcArchivo}   -> bytes del Excel

Solo se cuentan como "compra real" los comprobantes tipo FCVTA (Factura de
Venta) — se excluyen recibos (RECCC), devoluciones (DVVTA) y anulados.

--------------------------------------------------------------------------
CAMBIOS (31/08/2026) — fix de dos bugs detectados por timeouts repetidos:

1) BUG DE CACHÉ (retry storm): antes, si `_cache["ultima_compra_por_cliente"]`
   era un dict vacío (por ej. porque ChessERP nunca respondió con éxito),
   la condición `and _cache["ultima_compra_por_cliente"]` daba False (dict
   vacío = falsy), así que la función volvía a intentar el login + descarga
   completos EN CADA CALLBACK del mapa, aunque no hubiese pasado el TTL.
   Eso generaba un timeout de 60s en cada refresh de la UI.

   Fix: se agregó `ultimo_intento` al caché y un cooldown propio
   (`REINTENTO_COOLDOWN_SEGUNDOS`) para no reintentar más seguido que eso,
   incluso si el caché está vencido y aunque esté vacío.

2) LOGS DE DIAGNÓSTICO: se agregaron prints en cada paso (login, pedido de
   reporte, descarga del excel) para poder ver en qué paso exacto se cuelga
   la llamada real a ChessERP. Sacarlos o bajarlos a logging.debug() una vez
   que esté diagnosticado el timeout de fondo.

--------------------------------------------------------------------------
CAMBIOS (03/09/2026) — cache INCREMENTAL persistente en disco:

Antes, cada vez que el caché en memoria vencía (cada CACHE_TTL_SEGUNDOS =
1 hora), se volvía a pedir a ChessERP el Excel de comprobantes de LOS
ÚLTIMOS 2 MESES completos — un archivo grande e innecesario, porque las
ventas de días ya pasados no cambian.

Ahora:
  - El resultado {cliente: última_fecha_de_compra} se guarda en un archivo
    JSON en disco (CACHE_DISCO_PATH), junto con la fecha hasta la que se
    bajó ("fecha_hasta_bajada"). Así sobrevive a un reinicio de app.py:
    no hay que rebajar 2 meses cada vez que arranca el server.
  - En cada actualización (por vencimiento de TTL o forzada):
      * Si nunca se bajó nada antes (no existe el JSON, o está vacío) ->
        se baja el rango completo de `meses_hacia_atras` meses, igual que
        antes, para tener la base histórica.
      * Si ya había algo guardado -> se baja SOLO desde unos días antes de
        la última descarga (SOLAPAMIENTO_DIAS, por si hay facturas
        cargadas con fecha atrasada) hasta hoy. Ese resultado chico se
        combina con lo que ya había en disco, quedándose con la fecha más
        reciente por cliente.
  - La función pública `obtener_ultima_compra_por_cliente()` mantiene la
    misma firma y el mismo resultado hacia afuera (mapa.py no necesita
    ningún cambio) — solo cambia internamente cuánto le pide a ChessERP.
--------------------------------------------------------------------------
"""
from __future__ import annotations

import io
import json
import os
import time
from datetime import date, timedelta

import pandas as pd
import requests

try:
    from secrets_config import CHESSERP_USERNAME, CHESSERP_PASSWORD
except ImportError:
    CHESSERP_USERNAME = None
    CHESSERP_PASSWORD = None

BASE_URL = "https://alomasrl.chesserp.com"

# Cuánto tiempo guardamos el resultado en memoria antes de volver a
# evaluar si hace falta pedirle algo a ChessERP — evita golpear el
# servidor cada vez que alguien cambia un filtro del mapa. Se puede
# forzar antes con forzar_actualizar=True.
CACHE_TTL_SEGUNDOS = 3600  # 1 hora

# Si el último intento (exitoso o no) fue hace menos de esto, no se
# reintenta — aunque el caché esté vencido o vacío. Esto es lo que evita
# el "retry storm" cuando ChessERP está lento/caído: en vez de colgar cada
# callback del mapa por 60s+, se devuelve lo último que haya en caché
# (aunque esté vencido, o vacío si todavía no hubo ningún éxito).
REINTENTO_COOLDOWN_SEGUNDOS = 120  # 2 minutos

# Días de "solapamiento" al hacer una descarga incremental: en vez de
# pedir SOLO desde el día siguiente a la última descarga exitosa, pedimos
# desde unos días antes — por si algún comprobante se cargó en ChessERP
# con fecha atrasada (ej: se factura hoy una venta con fecha de ayer).
SOLAPAMIENTO_DIAS = 5

# Dónde persistimos el resultado en disco, para no perder el historial ya
# bajado cada vez que se reinicia app.py.
CACHE_DISCO_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "cache_chesserp_ventas.json")

_cache = {
    "ultima_compra_por_cliente": {},
    "actualizado_en": 0.0,
    "ultimo_intento": 0.0,
    # Fecha (date) hasta la que ya está descargado el historial en disco.
    # None si todavía no se bajó nada nunca.
    "fecha_hasta_bajada": None,
}


def _cargar_cache_disco():
    """Carga el JSON persistido (si existe) en _cache, al importar el
    módulo — así un reinicio de app.py no obliga a rebajar 2 meses."""
    if not os.path.exists(CACHE_DISCO_PATH):
        return
    try:
        with open(CACHE_DISCO_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        ultima_compra = {int(k): date.fromisoformat(v) for k, v in data.get("ultima_compra_por_cliente", {}).items()}
        fecha_hasta = data.get("fecha_hasta_bajada")
        _cache["ultima_compra_por_cliente"] = ultima_compra
        _cache["fecha_hasta_bajada"] = date.fromisoformat(fecha_hasta) if fecha_hasta else None
        # No tocamos "actualizado_en": lo dejamos en 0 para que la próxima
        # llamada evalúe igual si conviene refrescar (aunque sea con una
        # descarga chica, incremental) — pero ya arrancamos con datos.
        print(f"✅ [ChessERP] Cache en disco cargado: {len(ultima_compra)} clientes, hasta {fecha_hasta}.")
    except Exception as e:
        print(f"⚠️  No se pudo leer el cache en disco de ChessERP ({CACHE_DISCO_PATH}): {e}")


def _guardar_cache_disco():
    """Persiste el estado actual de _cache al JSON en disco."""
    try:
        os.makedirs(os.path.dirname(CACHE_DISCO_PATH), exist_ok=True)
        data = {
            "ultima_compra_por_cliente": {
                str(k): v.isoformat() for k, v in _cache["ultima_compra_por_cliente"].items()
            },
            "fecha_hasta_bajada": _cache["fecha_hasta_bajada"].isoformat() if _cache["fecha_hasta_bajada"] else None,
        }
        with open(CACHE_DISCO_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)
    except Exception as e:
        print(f"⚠️  No se pudo guardar el cache en disco de ChessERP ({CACHE_DISCO_PATH}): {e}")


_cargar_cache_disco()


def login() -> dict:
    """Hace login en ChessERP y devuelve la sesión autenticada (cookies)."""
    if not CHESSERP_USERNAME or not CHESSERP_PASSWORD:
        raise Exception("Faltan CHESSERP_USERNAME / CHESSERP_PASSWORD en secrets_config.py")

    url = f"{BASE_URL}/AR1252/static/auth/j_spring_security_check"
    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "es-ES,es;q=0.9",
        "Referer": f"{BASE_URL}/AR1252/",
    })
    resp = session.post(url, data={
        "j_username": CHESSERP_USERNAME,
        "j_password": CHESSERP_PASSWORD,
    }, allow_redirects=True, timeout=30)

    if resp.status_code not in (200, 302):
        raise Exception(f"Login a ChessERP fallido: HTTP {resp.status_code}")

    cookies = dict(session.cookies)
    if not cookies.get("JSESSIONID") and not cookies.get("alomasrl_chesserp.com_chkLogged"):
        raise Exception("Login a ChessERP fallido: no se obtuvieron cookies de sesión")

    return {"session": session, "cookies": cookies}


# ── Sesión de ChessERP cacheada (para no loguearse de nuevo en cada
#    consulta de "¿está anulado?" — son muchas consultas seguidas) ──
_session_cache = {"session": None, "obtenido_en": 0.0}
SESSION_TTL_SEGUNDOS = 600  # 10 minutos


def _get_session():
    ahora = time.time()
    vencida = (ahora - _session_cache["obtenido_en"]) > SESSION_TTL_SEGUNDOS
    if _session_cache["session"] is None or vencida:
        sess_data = login()
        _session_cache["session"] = sess_data["session"]
        _session_cache["obtenido_en"] = ahora
    return _session_cache["session"]


# ── Caché de "¿está anulado?" por cliente — 24hs, porque un alta/baja de
#    cliente no cambia seguido, no hace falta reconsultar en cada refresh
#    del mapa. Guardado solo en memoria (se resetea al reiniciar app.py,
#    no hace falta persistirlo en disco como el de última compra). ──
_cache_anulados = {}
ANULADO_CACHE_TTL_SEGUNDOS = 24 * 3600  # 1 día


def es_cliente_anulado(codigo_cliente: int) -> bool:
    """Consulta (con caché de 24hs) si un cliente está anulado/dado de
    baja en ChessERP. Se usa para sacar de "inactivos" a los clientes que
    en realidad ya no son clientes — el Excel de Visitas no tiene esa
    info, hay que preguntarle a ChessERP directo por cada uno.

    Si no se puede determinar (sin conexión, error, etc.), devuelve False
    a propósito — preferimos mostrar de más un "inactivo" real que
    esconder uno por un error de red puntual."""
    ahora = time.time()
    entrada = _cache_anulados.get(codigo_cliente)
    if entrada and (ahora - entrada["consultado_en"]) < ANULADO_CACHE_TTL_SEGUNDOS:
        return entrada["anulado"]

    try:
        session = _get_session()
        url = f"{BASE_URL}/AR1252/web/api/clientes/obtenerCliente?piSuc=1&piCli={codigo_cliente}"
        resp = session.get(url, timeout=15)
        if resp.status_code != 200:
            return entrada["anulado"] if entrada else False
        data = resp.json()
        eclientes = (data.get("dsClientes") or {}).get("eClientes") or []
        anulado = bool(eclientes[0].get("anulado")) if eclientes else False
    except Exception as e:
        print(f"⚠️  No se pudo consultar 'anulado' del cliente {codigo_cliente}: {e}")
        return entrada["anulado"] if entrada else False

    _cache_anulados[codigo_cliente] = {"anulado": anulado, "consultado_en": ahora}
    return anulado


def filtrar_no_anulados(codigos_cliente: set) -> set:
    """Dado un set de códigos de cliente, devuelve el mismo set SIN los
    que están anulados/dados de baja en ChessERP. Pensado para usarse
    sobre el set de "inactivos" del mapa, justo antes de mostrarlo."""
    return {c for c in codigos_cliente if not es_cliente_anulado(c)}


def descargar_reporte_ventas(session, fecha_desde: str, fecha_hasta: str, id_sucursal: str = "1") -> pd.DataFrame:
    """Pide a ChessERP el Excel detallado de comprobantes de venta entre
    fecha_desde y fecha_hasta (formato 'YYYY-MM-DD'), lo descarga, y lo
    devuelve como DataFrame."""
    url_exportar = f"{BASE_URL}/AR1252/web/api/reporteComprobantesVta/exportarExcel"
    payload = {
        "dsFiltrosRepCbtsVta": {
            "eFiltros": [{
                "letra": None, "serie": None, "numero": None, "numeroHasta": None,
                "fechadesde": fecha_desde, "fechahasta": fecha_hasta,
                "timbrado": "", "empresas": "", "idsucur": id_sucursal,
                "tiposdoc": "", "formasagruart": ",,,,,,,,,",
            }]
        },
        "pcTipo": "C",
    }

    print(f"   🔹 POST exportarExcel (rango {fecha_desde} a {fecha_hasta})...")
    t0 = time.time()
    resp = session.post(url_exportar, json=payload, timeout=60)
    print(f"   ⏱️  exportarExcel respondió en {time.time() - t0:.1f}s (HTTP {resp.status_code})")
    if resp.status_code != 200:
        raise Exception(f"Error pidiendo el reporte: HTTP {resp.status_code}")

    data = resp.json()
    ruta_archivo = data.get("pcArchivo")
    if not ruta_archivo:
        raise Exception(f"ChessERP no devolvió la ruta del archivo: {data}")

    # OJO: pcArchivo viene como ruta relativa a la app (/AR1252/), no a la
    # raíz del dominio. Si armamos la URL como BASE_URL + ruta_archivo sin
    # el prefijo /AR1252/, caemos en una ruta inexistente en el contexto de
    # la app y el firewall/proxy delante del servidor la rechaza con
    # "Request refused" (HTTP 400) — confirmado comparando con la URL real
    # que usa el navegador: https://alomasrl.chesserp.com/AR1252/static/downloads/...
    url_descarga = f"{BASE_URL}/AR1252{ruta_archivo}"
    print(f"   🔹 GET descarga del archivo generado ({ruta_archivo})...")

    # El header Accept que usamos para login/API (application/json) puede
    # hacer que un firewall/WAF delante del servidor rechace la descarga
    # de un archivo estático, porque no "parece" un navegador pidiendo un
    # archivo para descargar. Simulamos los headers que manda un navegador
    # real en una navegación de descarga, solo para este request puntual.
    headers_descarga = {
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "same-origin",
        "Sec-Fetch-User": "?1",
        "Referer": f"{BASE_URL}/AR1252/",
    }

    # El archivo puede tardar un instante en terminar de escribirse del
    # lado del servidor después de que exportarExcel devuelve la ruta.
    # Reintentamos con una pequeña espera creciente antes de rendirnos.
    intentos_descarga = [0, 1, 2, 4]  # segundos de espera antes de cada intento
    resp_archivo = None
    for i, espera in enumerate(intentos_descarga):
        if espera:
            print(f"      (esperando {espera}s antes de reintentar la descarga...)")
            time.sleep(espera)
        t0 = time.time()
        resp_archivo = session.get(url_descarga, headers=headers_descarga, timeout=60)
        print(f"   ⏱️  Intento {i + 1}: descarga en {time.time() - t0:.1f}s (HTTP {resp_archivo.status_code})")
        if resp_archivo.status_code == 200:
            break
        else:
            print(f"      Cuerpo de la respuesta: {resp_archivo.text[:500]!r}")

    if resp_archivo.status_code != 200:
        raise Exception(f"Error descargando el archivo generado: HTTP {resp_archivo.status_code}")

    return pd.read_excel(io.BytesIO(resp_archivo.content))


def _calcular_ultima_compra(df: pd.DataFrame) -> dict:
    """A partir del DataFrame crudo del reporte, calcula {cliente: fecha_ultima_compra}.
    Solo cuentan como compra real los comprobantes FCVTA (Factura de Venta),
    no anulados."""
    if df.empty or "Comprobante" not in df.columns or "Cliente" not in df.columns:
        return {}

    ventas = df[df["Comprobante"] == "FCVTA"].copy()
    if "Anulado" in ventas.columns:
        ventas = ventas[ventas["Anulado"].astype(str).str.upper() != "SI"]

    col_fecha = "Fecha pedido" if "Fecha pedido" in ventas.columns else "Fecha Comprobante"
    ventas[col_fecha] = pd.to_datetime(ventas[col_fecha], errors="coerce")
    ventas = ventas[ventas[col_fecha].notna()]
    if ventas.empty:
        return {}

    ultima_por_cliente = ventas.groupby("Cliente")[col_fecha].max()
    return {int(cliente): fecha.date() for cliente, fecha in ultima_por_cliente.items()}


def obtener_ultima_compra_por_cliente(meses_hacia_atras: int = 6, forzar_actualizar: bool = False) -> dict:
    """Devuelve {cliente_id: fecha_ultima_compra_real} — con cache en
    memoria de CACHE_TTL_SEGUNDOS para no golpear ChessERP en cada filtro
    del mapa, y cache persistente en disco para no perder el historial ya
    bajado entre reinicios de app.py.

    A diferencia de antes, cuando toca refrescar NO se vuelve a bajar todo
    el rango de `meses_hacia_atras` meses — eso solo pasa la primera vez
    (cuando no hay nada guardado en disco todavía). Las veces siguientes
    se baja solo un rango chico (desde unos días antes de la última
    descarga hasta hoy) y se combina con lo que ya había, quedándose con
    la fecha más reciente por cliente.

    Si el último intento (haya salido bien o mal) fue hace menos de
    REINTENTO_COOLDOWN_SEGUNDOS, se devuelve directamente lo que haya en
    caché (aunque esté vencido o vacío) SIN reintentar — esto es lo que
    evita que cada refresh de la UI dispare un login+descarga completo
    mientras ChessERP esté lento o caído.
    """
    ahora = time.time()
    vencido = (ahora - _cache["actualizado_en"]) > CACHE_TTL_SEGUNDOS
    intento_muy_reciente = (ahora - _cache["ultimo_intento"]) < REINTENTO_COOLDOWN_SEGUNDOS

    if not forzar_actualizar and not vencido and _cache["ultima_compra_por_cliente"]:
        return _cache["ultima_compra_por_cliente"]

    if not forzar_actualizar and intento_muy_reciente:
        # Ya intentamos hace poco (haya salido bien o mal) — no reintentar
        # todavía, para no colgar este callback esperando a ChessERP.
        return _cache["ultima_compra_por_cliente"]

    _cache["ultimo_intento"] = ahora

    hoy = date.today()
    fecha_hasta_previa = _cache["fecha_hasta_bajada"]

    if fecha_hasta_previa is None:
        # Primera vez (nunca se bajó nada, ni siquiera de una sesión
        # anterior persistida en disco) -> traemos la base histórica
        # completa, como antes.
        fecha_desde = hoy - timedelta(days=meses_hacia_atras * 30)
        es_incremental = False
    else:
        # Ya tenemos historial -> solo pedimos desde un poco antes de la
        # última descarga (solapamiento de seguridad) hasta hoy.
        fecha_desde = fecha_hasta_previa - timedelta(days=SOLAPAMIENTO_DIAS)
        es_incremental = True

    try:
        print(f"🔹 [ChessERP] Intentando login... ({'incremental' if es_incremental else 'descarga base completa'})")
        t0 = time.time()
        sess_data = login()
        session = sess_data["session"]
        print(f"✅ [ChessERP] Login OK en {time.time() - t0:.1f}s. Pidiendo reporte...")

        df = descargar_reporte_ventas(session, fecha_desde.isoformat(), hoy.isoformat())
        print(f"✅ [ChessERP] Reporte descargado: {len(df)} filas.")
        resultado_nuevo = _calcular_ultima_compra(df)

        # Combinamos con lo que ya teníamos: para cada cliente, nos
        # quedamos con la fecha más reciente entre lo viejo y lo nuevo.
        # (En una descarga incremental, un cliente que no compró en el
        # rango pedido simplemente no aparece en resultado_nuevo, y
        # conserva la fecha que ya teníamos guardada.)
        combinado = dict(_cache["ultima_compra_por_cliente"])
        for cliente, fecha in resultado_nuevo.items():
            if cliente not in combinado or fecha > combinado[cliente]:
                combinado[cliente] = fecha

        _cache["ultima_compra_por_cliente"] = combinado
        _cache["actualizado_en"] = ahora
        _cache["fecha_hasta_bajada"] = hoy
        _guardar_cache_disco()
        print(f"✅ [ChessERP] 'última compra' actualizada: {len(resultado_nuevo)} clientes nuevos/actualizados, {len(combinado)} en total.")
        return combinado

    except Exception as e:
        print(f"⚠️  No se pudo actualizar 'última compra' desde ChessERP: {e}")
        # Si falla, devolvemos lo último que teníamos (aunque esté vencido)
        # en vez de dejar el mapa sin nada. El cooldown de arriba evita que
        # esto se reintente en cada callback.
        return _cache["ultima_compra_por_cliente"]