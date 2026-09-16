"""
Viáticos: monto que corresponde pagarle al SUPERVISOR cuando sale con un
vendedor puntual (algunos vendedores tienen viático, otros no).

Se guarda en un JSON simple (VIATICOS_FILE): {nombre_vendedor: monto}
"""

import json
import os

from config import VIATICOS_FILE


def _cargar() -> dict:
    if not os.path.exists(VIATICOS_FILE):
        return {}
    try:
        with open(VIATICOS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _guardar(data: dict):
    with open(VIATICOS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def obtener_viaticos() -> dict:
    """Devuelve {nombre_vendedor: monto} de todos los vendedores con
    viático configurado."""
    return _cargar()


def guardar_viatico(vendedor: str, monto: float):
    """Crea o actualiza el viático de un vendedor."""
    data = _cargar()
    data[vendedor] = float(monto)
    _guardar(data)


def eliminar_viatico(vendedor: str):
    """Saca el viático de un vendedor (deja de contar en los cálculos)."""
    data = _cargar()
    if vendedor in data:
        del data[vendedor]
        _guardar(data)