"""
test_chesserp_timing.py — Script standalone para medir cuánto tarda
ChessERP en generar el reporte de ventas con distintos rangos de fechas.

Correr desde la carpeta del proyecto (TABLERO2.0) con:
    python test_chesserp_timing.py

Sirve para confirmar si el timeout de 60s es por volumen de datos
(rango muy amplio) o si el problema persiste incluso con rangos chicos.
"""
from __future__ import annotations

import sys
import time
from datetime import date, timedelta
from pathlib import Path

# Este script debe correrse parado en la carpeta raíz del proyecto
# (tablero2.0, al lado de app.py). chesserp_ventas.py vive en utils/,
# así que nos aseguramos de que la raíz esté en el path para poder
# importarlo como "utils.chesserp_ventas".
sys.path.insert(0, str(Path(__file__).resolve().parent))

from utils.chesserp_ventas import login, descargar_reporte_ventas

# Rangos a probar, de más chico a más grande (en días hacia atrás desde hoy)
RANGOS_A_PROBAR = [7, 30, 90, 180]

# Timeout generoso solo para este test, para ver cuánto tarda "de verdad"
# aunque supere los 60s normales de producción.
TIMEOUT_TEST_SEGUNDOS = 180


def probar_rango(session, dias_atras: int):
    hoy = date.today()
    fecha_desde = (hoy - timedelta(days=dias_atras)).isoformat()
    fecha_hasta = hoy.isoformat()

    print(f"\n=== Probando rango de {dias_atras} días ({fecha_desde} a {fecha_hasta}) ===")
    t0 = time.time()
    try:
        # Monkey-patch temporal del timeout solo para este test, sin tocar
        # el archivo original — llamamos directo con más margen.
        original_post = session.post

        def post_con_timeout_largo(*args, **kwargs):
            kwargs["timeout"] = TIMEOUT_TEST_SEGUNDOS
            return original_post(*args, **kwargs)

        session.post = post_con_timeout_largo
        session.get = session.get  # get ya tiene su propio timeout=60 en la función original

        df = descargar_reporte_ventas(session, fecha_desde, fecha_hasta)
        elapsed = time.time() - t0
        print(f"✅ OK en {elapsed:.1f}s — {len(df)} filas")
        session.post = original_post
        return elapsed, len(df)
    except Exception as e:
        elapsed = time.time() - t0
        print(f"❌ Falló después de {elapsed:.1f}s: {e}")
        return elapsed, None


def main():
    print("🔹 Login...")
    t0 = time.time()
    sess_data = login()
    print(f"✅ Login OK en {time.time() - t0:.1f}s")
    session = sess_data["session"]

    resultados = []
    for dias in RANGOS_A_PROBAR:
        elapsed, filas = probar_rango(session, dias)
        resultados.append((dias, elapsed, filas))

    print("\n" + "=" * 50)
    print("RESUMEN")
    print("=" * 50)
    for dias, elapsed, filas in resultados:
        estado = f"{filas} filas" if filas is not None else "FALLÓ"
        print(f"  {dias:>4} días atrás -> {elapsed:>6.1f}s -> {estado}")


if __name__ == "__main__":
    main()