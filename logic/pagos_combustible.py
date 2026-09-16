"""
Liquidación de combustible por ruta planificada — versión simple.

Cada vendedor tiene, para cada mes, los kms que recorre Lunes a Viernes.
Sin descripción de recorrido (no afecta el cálculo, solo agregaba campos
para llenar). La ruta de un mes se copia automáticamente del mes anterior
la primera vez que se abre ese mes, así el admin solo edita lo que cambió.

El monto a liquidar por vendedor y mes se calcula así:
    para cada día hábil real de ese mes (ej: los 4 lunes de agosto 2026)
        si el vendedor NO tiene esa fecha marcada como ausencia
            sumar: kms_de_ese_dia_de_semana * precio_nafta_del_mes

Usa las fechas reales del mes (no todos los meses tienen la misma cantidad
de lunes, martes, etc.) y descuenta las ausencias que ya se cargan para la
liquidación normal (AUSENCIAS_VENDEDORES_FILE) — no hay que tocar nada dos
veces.

Dos archivos JSON:

- RUTAS_VENDEDORES_FILE: kms por vendedor, mes y día de semana
    {
      "1 - Guille Coria": {
        "2026-08": {"Lunes": 73, "Martes": 50, "Miercoles": 35, "Jueves": 107, "Viernes": 122}
      }
    }
  Un día en 0 o ausente significa que ese día no hace ruta.

- PRECIO_NAFTA_FILE: precio de la nafta por mes (con historial, porque
  cambia con el tiempo)
    { "2026-08": 203.0, "2026-09": 210.0 }

- Reutiliza AUSENCIAS_VENDEDORES_FILE (mismo formato que en
  logic/pagos_vendedores.py) para descontar días no trabajados.
"""

import json
import os
from calendar import monthrange
from datetime import date

from config import (
    RUTAS_VENDEDORES_FILE,
    PRECIO_NAFTA_FILE,
    AUSENCIAS_VENDEDORES_FILE,
)

DIAS_SEMANA = ["Lunes", "Martes", "Miercoles", "Jueves", "Viernes", "Sabado"]
# weekday() de Python: 0=Lunes ... 5=Sábado
DIA_A_WEEKDAY = {"Lunes": 0, "Martes": 1, "Miercoles": 2, "Jueves": 3, "Viernes": 4, "Sabado": 5}


# ======================================================
# HELPERS JSON GENÉRICOS
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
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _clave_mes(year: int, month: int) -> str:
    return f"{year:04d}-{month:02d}"


# ======================================================
# PRECIO DE LA NAFTA (con historial por mes)
# ======================================================
def obtener_precio_nafta(year: int, month: int) -> float:
    """Precio cargado para ese mes. Si no hay uno cargado puntual, usa el
    último precio conocido de un mes anterior. 0.0 si nunca se cargó nada."""
    data = _cargar_json(PRECIO_NAFTA_FILE)
    clave = _clave_mes(year, month)
    if clave in data:
        return float(data[clave])

    anteriores = [k for k in data.keys() if k < clave]
    if anteriores:
        return float(data[max(anteriores)])
    return 0.0


def guardar_precio_nafta(year: int, month: int, precio: float):
    data = _cargar_json(PRECIO_NAFTA_FILE)
    data[_clave_mes(year, month)] = float(precio)
    _guardar_json(PRECIO_NAFTA_FILE, data)


# ======================================================
# RUTAS (kms por vendedor, mes y día de semana)
# ======================================================
def _cargar_rutas() -> dict:
    return _cargar_json(RUTAS_VENDEDORES_FILE)


def _guardar_rutas(data: dict):
    _guardar_json(RUTAS_VENDEDORES_FILE, data)


def obtener_ruta_mes(vendedor: str, year: int, month: int) -> dict:
    """Devuelve {"Lunes": kms, "Martes": kms, ...} para ese vendedor y mes.
    Dict vacío si nunca se cargó nada para ese mes."""
    data = _cargar_rutas()
    return data.get(vendedor, {}).get(_clave_mes(year, month), {})


def guardar_ruta_mes(vendedor: str, year: int, month: int, kms_por_dia: dict):
    """Pisa por completo los kms de ese vendedor para ese mes."""
    data = _cargar_rutas()
    data.setdefault(vendedor, {})
    data[vendedor][_clave_mes(year, month)] = {
        d: float(kms_por_dia.get(d, 0) or 0) for d in DIAS_SEMANA
    }
    _guardar_rutas(data)


def asegurar_rutas_mes(vendedores: list, year: int, month: int) -> int:
    """Para cada vendedor de la lista que NO tenga ruta cargada este mes,
    copia automáticamente la del mes anterior más reciente disponible (si
    existe). Pensado para llamarse cada vez que se abre la pantalla, así
    el admin nunca tiene que tocar un botón de 'copiar' a mano.
    Devuelve la cantidad de vendedores a los que se les copió algo."""
    if month == 1:
        prev_year, prev_month = year - 1, 12
    else:
        prev_year, prev_month = year, month - 1

    data = _cargar_rutas()
    clave_mes = _clave_mes(year, month)
    clave_prev = _clave_mes(prev_year, prev_month)

    copiados = 0
    for vendedor in vendedores:
        meses_vendedor = data.get(vendedor, {})
        if clave_mes in meses_vendedor:
            continue  # ya tiene algo cargado este mes, no tocar

        # Buscamos el mes anterior más reciente que tenga datos (no
        # necesariamente el inmediato anterior, por si se saltearon meses).
        meses_anteriores = sorted([k for k in meses_vendedor.keys() if k < clave_mes])
        if not meses_anteriores:
            continue

        ultimo_mes = meses_anteriores[-1]
        data.setdefault(vendedor, {})
        data[vendedor][clave_mes] = dict(meses_vendedor[ultimo_mes])
        copiados += 1

    if copiados:
        _guardar_rutas(data)
    return copiados


# ======================================================
# CÁLCULO DE LIQUIDACIÓN DE COMBUSTIBLE
# ======================================================
def _fechas_habiles_por_dia_semana(year: int, month: int) -> dict:
    """{"Lunes": [date, date, ...], "Martes": [...], ...} con todas las
    fechas reales de ese día de semana en ese mes."""
    ultimo_dia = monthrange(year, month)[1]
    resultado = {d: [] for d in DIAS_SEMANA}
    for d in range(1, ultimo_dia + 1):
        f = date(year, month, d)
        for nombre_dia, wd in DIA_A_WEEKDAY.items():
            if f.weekday() == wd:
                resultado[nombre_dia].append(f)
    return resultado


def _obtener_ausencias_mes(vendedor: str, year: int, month: int) -> set:
    data = _cargar_json(AUSENCIAS_VENDEDORES_FILE)
    clave = _clave_mes(year, month)
    return set(data.get(vendedor, {}).get(clave, []))


def calcular_liquidacion_combustible_mes(year: int, month: int) -> dict:
    """Para cada vendedor con ruta cargada este mes, calcula cuánto se le
    debe liquidar de combustible.

    Devuelve:
        {
          "1 - Guille Coria": {
              "kms_totales": 1234.0,
              "precio_nafta": 203.0,
              "total": 250502.0,
              "dias_ausente_descontados": 2,
          },
          ...
        }
    """
    rutas = _cargar_rutas()
    clave_mes = _clave_mes(year, month)
    precio_nafta = obtener_precio_nafta(year, month)
    fechas_por_dia = _fechas_habiles_por_dia_semana(year, month)

    resultado = {}
    for vendedor, meses in rutas.items():
        kms_por_dia = meses.get(clave_mes, {})
        if not kms_por_dia or not any(kms_por_dia.values()):
            continue

        ausencias = _obtener_ausencias_mes(vendedor, year, month)

        kms_totales = 0.0
        total = 0.0
        dias_ausente_descontados = 0

        for dia_semana, kms in kms_por_dia.items():
            kms = float(kms or 0)
            if kms <= 0 or dia_semana not in fechas_por_dia:
                continue
            for fecha in fechas_por_dia[dia_semana]:
                fecha_iso = fecha.isoformat()
                if fecha_iso in ausencias:
                    dias_ausente_descontados += 1
                else:
                    kms_totales += kms
                    total += kms * precio_nafta

        resultado[vendedor] = {
            "kms_totales":              kms_totales,
            "precio_nafta":             precio_nafta,
            "total":                    total,
            "dias_ausente_descontados": dias_ausente_descontados,
        }

    return resultado