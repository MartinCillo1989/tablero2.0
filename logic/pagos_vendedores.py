"""
Liquidación de vendedores: cada vendedor tiene un monto fijo por día hábil
trabajado (Lunes a Sábado). A fin de mes, el admin marca a mano (en un
calendario/checklist) los días en que NO salió — esos días se descuentan
del total a pagar.

Dos archivos JSON:
- MONTOS_DIARIOS_VENDEDORES_FILE: {nombre_vendedor: monto_diario}
- AUSENCIAS_VENDEDORES_FILE: {nombre_vendedor: {"2026-08": ["2026-08-05", "2026-08-12", ...]}}
"""

import calendar as calendar_mod
import json
import os
from datetime import date

from config import MONTOS_DIARIOS_VENDEDORES_FILE, AUSENCIAS_VENDEDORES_FILE


# ======================================================
# MONTOS DIARIOS
# ======================================================
def _cargar_montos() -> dict:
    if not os.path.exists(MONTOS_DIARIOS_VENDEDORES_FILE):
        return {}
    try:
        with open(MONTOS_DIARIOS_VENDEDORES_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _guardar_montos(data: dict):
    with open(MONTOS_DIARIOS_VENDEDORES_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def obtener_montos_diarios() -> dict:
    """Devuelve {nombre_vendedor: monto_diario}."""
    return _cargar_montos()


def guardar_monto_diario(vendedor: str, monto: float):
    data = _cargar_montos()
    data[vendedor] = float(monto)
    _guardar_montos(data)


def eliminar_monto_diario(vendedor: str):
    data = _cargar_montos()
    if vendedor in data:
        del data[vendedor]
        _guardar_montos(data)


# ======================================================
# AUSENCIAS (marcadas a mano)
# ======================================================
def _cargar_ausencias() -> dict:
    if not os.path.exists(AUSENCIAS_VENDEDORES_FILE):
        return {}
    try:
        with open(AUSENCIAS_VENDEDORES_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _guardar_ausencias(data: dict):
    with open(AUSENCIAS_VENDEDORES_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def obtener_ausencias_mes(vendedor: str, year: int, month: int) -> list:
    """Devuelve la lista de fechas (iso) marcadas como 'no salió' para ese
    vendedor en ese mes."""
    data = _cargar_ausencias()
    clave_mes = f"{year:04d}-{month:02d}"
    return data.get(vendedor, {}).get(clave_mes, [])


def guardar_ausencias_mes(vendedor: str, year: int, month: int, fechas: list):
    """Pisa por completo la lista de ausencias de ese vendedor para ese mes
    con la lista nueva que se pasa (así el checklist del mes queda como
    única fuente de verdad, sin ir sumando/restando una por una)."""
    data = _cargar_ausencias()
    clave_mes = f"{year:04d}-{month:02d}"
    data.setdefault(vendedor, {})
    data[vendedor][clave_mes] = sorted(set(fechas))
    _guardar_ausencias(data)


# ======================================================
# CÁLCULO DE LIQUIDACIÓN
# ======================================================
def dias_habiles_mes(year: int, month: int) -> list:
    """Lista de objetos date de todos los días hábiles (Lunes a Sábado)
    de ese mes."""
    ultimo_dia = calendar_mod.monthrange(year, month)[1]
    dias = []
    for d in range(1, ultimo_dia + 1):
        f = date(year, month, d)
        if f.weekday() < 6:  # 0=lunes ... 5=sábado (6=domingo queda afuera)
            dias.append(f)
    return dias


def calcular_liquidacion_mes(year: int, month: int, montos: dict) -> dict:
    """Para cada vendedor con monto diario configurado, calcula cuánto le
    corresponde cobrar ese mes: (días hábiles - días ausente marcados) *
    monto diario.

    Devuelve:
        {
          "21-FERREYRA MAURICIO EMANUEL": {
              "dias_habiles": 21, "dias_ausente": 2, "dias_pagados": 19,
              "monto_diario": 5000.0, "total": 95000.0,
          },
          ...
        }
    """
    dias_habiles = dias_habiles_mes(year, month)
    habiles_iso = {f.isoformat() for f in dias_habiles}
    total_habiles = len(dias_habiles)

    resultado = {}
    for vendedor, monto in montos.items():
        ausencias = obtener_ausencias_mes(vendedor, year, month)
        # Solo contamos como ausencia los días que realmente son hábiles
        # de ese mes (por si quedó algo marcado de un mes con distinta
        # cantidad de días hábiles, o un domingo colado).
        dias_ausente = len([f for f in ausencias if f in habiles_iso])
        dias_pagados = total_habiles - dias_ausente

        resultado[vendedor] = {
            "dias_habiles":  total_habiles,
            "dias_ausente":  dias_ausente,
            "dias_pagados":  dias_pagados,
            "monto_diario":  float(monto),
            "total":         dias_pagados * float(monto),
        }
    return resultado