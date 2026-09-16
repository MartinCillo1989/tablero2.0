"""
Consulta por consola de lo que ya está guardado del sistema de sueldo fijo
diario (monto diario por vendedor + ausencias + liquidación calculada).

Uso:
    python consultar_liquidacion.py            -> mes actual
    python consultar_liquidacion.py 2026 7      -> julio 2026
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from datetime import date

from logic.pagos_vendedores import (
    obtener_montos_diarios,
    obtener_ausencias_mes,
    dias_habiles_mes,
    calcular_liquidacion_mes,
)
from config import MONTOS_DIARIOS_VENDEDORES_FILE, AUSENCIAS_VENDEDORES_FILE


def _fmt(m: float) -> str:
    return f"${m:,.2f}".replace(",", "@").replace(".", ",").replace("@", ".")


def main():
    if len(sys.argv) >= 3:
        year, month = int(sys.argv[1]), int(sys.argv[2])
    else:
        hoy = date.today()
        year, month = hoy.year, hoy.month

    print(f"\n{'='*70}")
    print(f"  CONSULTA — {month:02d}/{year}")
    print(f"{'='*70}\n")

    print(f"Archivo de montos diarios: {MONTOS_DIARIOS_VENDEDORES_FILE}")
    print(f"  Existe: {os.path.exists(MONTOS_DIARIOS_VENDEDORES_FILE)}\n")

    print(f"Archivo de ausencias:      {AUSENCIAS_VENDEDORES_FILE}")
    print(f"  Existe: {os.path.exists(AUSENCIAS_VENDEDORES_FILE)}\n")

    montos = obtener_montos_diarios()

    if not montos:
        print("⚠️  No hay NINGÚN monto diario guardado (el archivo está vacío o no existe).")
        print("    Esto significa que nunca se cargó nada, o se cargó y después se borró.\n")
        return

    print(f"Vendedores con monto diario configurado: {len(montos)}\n")
    print(f"{'Vendedor':<40} {'Monto/día':>15}")
    print("-" * 56)
    for vendedor, monto in sorted(montos.items()):
        print(f"{vendedor:<40} {_fmt(monto):>15}")

    dias_hab = dias_habiles_mes(year, month)
    print(f"\nDías hábiles de {month:02d}/{year} (Lunes a Sábado): {len(dias_hab)}")

    print(f"\n{'-'*70}")
    print("AUSENCIAS MARCADAS ESTE MES, por vendedor:")
    print(f"{'-'*70}")
    for vendedor in sorted(montos.keys()):
        ausencias = obtener_ausencias_mes(vendedor, year, month)
        if ausencias:
            print(f"  {vendedor}: {len(ausencias)} día(s) -> {', '.join(sorted(ausencias))}")
        else:
            print(f"  {vendedor}: sin ausencias marcadas")

    print(f"\n{'-'*70}")
    print("LIQUIDACIÓN CALCULADA:")
    print(f"{'-'*70}")
    liquidacion = calcular_liquidacion_mes(year, month, montos)

    if not liquidacion:
        print("⚠️  calcular_liquidacion_mes no devolvió nada (raro, ya que hay montos cargados).")
        return

    print(f"{'Vendedor':<32} {'Hábiles':>8} {'Ausente':>8} {'Pagados':>8} {'Monto/día':>12} {'Total':>14}")
    print("-" * 86)
    total_general = 0.0
    for vendedor, info in sorted(liquidacion.items()):
        print(
            f"{vendedor:<32} {info['dias_habiles']:>8} {info['dias_ausente']:>8} "
            f"{info['dias_pagados']:>8} {_fmt(info['monto_diario']):>12} {_fmt(info['total']):>14}"
        )
        total_general += info["total"]

    print("-" * 86)
    print(f"{'TOTAL GENERAL':<70} {_fmt(total_general):>14}\n")


if __name__ == "__main__":
    main()