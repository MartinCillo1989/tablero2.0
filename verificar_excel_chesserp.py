"""
verificar_excel_chesserp.py — Descarga el reporte de ChessERP, lo guarda
en disco para inspección manual, y muestra un diagnóstico del contenido:
columnas, tipos de comprobante, y una muestra del resultado final de
"última compra por cliente".

Correr desde la raíz del proyecto (tablero2.0):
    python verificar_excel_chesserp.py
"""
from __future__ import annotations

import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from utils.chesserp_ventas import login, descargar_reporte_ventas, _calcular_ultima_compra

DIAS_HACIA_ATRAS = 30  # ajustá si querés probar otro rango
ARCHIVO_SALIDA = "reporte_chesserp_descargado.xlsx"


def main():
    print("🔹 Login...")
    sess_data = login()
    session = sess_data["session"]
    print("✅ Login OK")

    hoy = date.today()
    fecha_desde = (hoy - timedelta(days=DIAS_HACIA_ATRAS)).isoformat()
    fecha_hasta = hoy.isoformat()

    print(f"\n🔹 Descargando reporte ({fecha_desde} a {fecha_hasta})...")
    df = descargar_reporte_ventas(session, fecha_desde, fecha_hasta)
    print(f"✅ Descargado: {len(df)} filas, {len(df.columns)} columnas")

    # Guardamos una copia en disco para que la abras manualmente en Excel
    df.to_excel(ARCHIVO_SALIDA, index=False)
    print(f"💾 Guardado en: {ARCHIVO_SALIDA} (abrilo para chequear a ojo)")

    print("\n" + "=" * 60)
    print("DIAGNÓSTICO DEL CONTENIDO")
    print("=" * 60)

    print(f"\nColumnas encontradas ({len(df.columns)}):")
    for col in df.columns:
        print(f"  - {col!r}")

    columnas_esperadas = ["Comprobante", "Cliente", "Anulado", "Fecha pedido", "Fecha Comprobante"]
    print("\nChequeo de columnas esperadas por el código:")
    for col in columnas_esperadas:
        estado = "✅ presente" if col in df.columns else "❌ FALTA"
        print(f"  - {col!r}: {estado}")

    if "Comprobante" in df.columns:
        print("\nValores únicos en 'Comprobante' (tipos de documento) y su cantidad:")
        print(df["Comprobante"].value_counts().to_string())

    if "Anulado" in df.columns:
        print("\nValores únicos en 'Anulado':")
        print(df["Anulado"].value_counts(dropna=False).to_string())

    print("\nPrimeras 5 filas crudas:")
    print(df.head(5).to_string())

    print("\n" + "=" * 60)
    print("RESULTADO: última compra calculada por cliente")
    print("=" * 60)
    resultado = _calcular_ultima_compra(df)
    print(f"\nClientes con última compra calculada: {len(resultado)}")

    if resultado:
        print("\nMuestra de 10 clientes (id -> fecha última compra):")
        for i, (cliente, fecha) in enumerate(resultado.items()):
            if i >= 10:
                break
            print(f"  Cliente {cliente} -> {fecha}")

        fechas = list(resultado.values())
        print(f"\nFecha de compra más reciente en el resultado: {max(fechas)}")
        print(f"Fecha de compra más antigua en el resultado:   {min(fechas)}")
    else:
        print("⚠️  El resultado quedó vacío — revisar nombres de columnas arriba,")
        print("   puede que 'Comprobante', 'Cliente' o la columna de fecha no")
        print("   coincidan exactamente con lo que espera _calcular_ultima_compra.")


if __name__ == "__main__":
    main()