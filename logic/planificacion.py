import calendar
import json
import os
import uuid
from collections import Counter
from datetime import date, datetime, timedelta

from config import PLANIFICACION_FILE

DIAS_ES = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]


def _cargar() -> dict:
    if not os.path.exists(PLANIFICACION_FILE):
        return {}
    try:
        with open(PLANIFICACION_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _guardar(data: dict):
    with open(PLANIFICACION_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def agregar_entrada(supervisor_usuario: str, fecha_iso: str, vendedor: str, nota: str) -> str:
    """Agrega una entrada (vendedor opcional + nota) a un día puntual del
    supervisor. Si 'vendedor' viene vacío, la entrada queda como una tarea
    general de ese día, sin vendedor asociado.
    Devuelve el id generado para esa entrada."""
    data = _cargar()
    dias = data.setdefault(supervisor_usuario, {})
    entradas = dias.setdefault(fecha_iso, [])

    entrada_id = uuid.uuid4().hex[:8]
    entradas.append({
        "id":             entrada_id,
        "vendedor":       vendedor,
        "nota":           (nota or "").strip(),
        "actualizado_at": datetime.now().isoformat(),
    })
    _guardar(data)
    return entrada_id


def editar_entrada(supervisor_usuario: str, fecha_iso: str, entrada_id: str, nota: str = None, vendedor: str = None):
    """Edita la nota y/o el vendedor de una entrada existente."""
    data = _cargar()
    entradas = data.get(supervisor_usuario, {}).get(fecha_iso, [])
    for e in entradas:
        if e["id"] == entrada_id:
            if nota is not None:
                e["nota"] = nota.strip()
            if vendedor is not None:
                e["vendedor"] = vendedor
            e["actualizado_at"] = datetime.now().isoformat()
            break
    _guardar(data)


def eliminar_entrada(supervisor_usuario: str, fecha_iso: str, entrada_id: str):
    """Borra una entrada puntual de un día."""
    data = _cargar()
    dias = data.get(supervisor_usuario, {})
    entradas = dias.get(fecha_iso, [])
    dias[fecha_iso] = [e for e in entradas if e["id"] != entrada_id]
    if not dias[fecha_iso]:
        del dias[fecha_iso]
    _guardar(data)


def obtener_entradas_dia(supervisor_usuario: str, fecha_iso: str) -> list:
    data = _cargar()
    return data.get(supervisor_usuario, {}).get(fecha_iso, [])


def lunes_de_la_semana(fecha: date) -> date:
    """Dado cualquier día, devuelve el lunes de esa semana."""
    return fecha - timedelta(days=fecha.weekday())


def obtener_semana(supervisor_usuario: str, lunes: date) -> list:
    """Devuelve 7 dicts (Lunes a Domingo) con las entradas de cada día para
    ese supervisor, y si el día ya pasó / es hoy / es futuro."""
    hoy = date.today()
    resultado = []
    for i in range(7):
        f = lunes + timedelta(days=i)
        f_iso = f.isoformat()
        resultado.append({
            "fecha":       f,
            "fecha_iso":   f_iso,
            "fecha_corta": f.strftime("%d/%m"),
            "dia_semana":  DIAS_ES[i],
            "entradas":    obtener_entradas_dia(supervisor_usuario, f_iso),
            "es_pasado":   f < hoy,
            "es_hoy":      f == hoy,
            "es_futuro":   f > hoy,
        })
    return resultado


def resumen_mes_equipo(supervisor_usuario: str, year: int, month: int, equipo_nombres: list) -> dict:
    """Para el mes (year, month), cuenta cuántas entradas tiene cada
    vendedor del equipo (cuántas veces el supervisor salió/anotó algo con
    él). Las entradas SIN vendedor (tareas generales) no cuentan para nadie.
    Devuelve {"con_actividad": [(nombre, cantidad), ...], "sin_actividad": [...]}
    ("con_actividad" ordenada alfabéticamente por nombre, "sin_actividad" también)."""
    data = _cargar()
    dias_usuario = data.get(supervisor_usuario, {}) if supervisor_usuario else {}
    prefijo = f"{year:04d}-{month:02d}"

    conteo_por_vendedor = Counter()
    for fecha_iso, entradas in dias_usuario.items():
        if not fecha_iso.startswith(prefijo):
            continue
        for e in entradas:
            v = (e.get("vendedor") or "").strip()
            if v:
                conteo_por_vendedor[v] += 1

    con = sorted(
        [(v, conteo_por_vendedor[v]) for v in equipo_nombres if v in conteo_por_vendedor],
        key=lambda par: par[0],
    )
    sin = sorted(v for v in equipo_nombres if v not in conteo_por_vendedor)
    return {"con_actividad": con, "sin_actividad": sin}


def label_semana(lunes: date) -> str:
    domingo = lunes + timedelta(days=6)
    return f"{lunes.strftime('%d/%m/%Y')} — {domingo.strftime('%d/%m/%Y')}"


def obtener_mes(supervisor_usuario: str, year: int, month: int) -> list:
    """Devuelve una lista de semanas (cada una, una lista de 7 días: Lunes a
    Domingo) que cubren el mes completo — incluyendo días de relleno del mes
    anterior/siguiente para completar semanas parciales al principio/final.
    Cada día es un dict: fecha_iso, dia_numero, es_mes_actual, es_hoy,
    cantidad (cuántas entradas tiene ese día)."""
    hoy = date.today()
    primer_dia = date(year, month, 1)
    lunes_inicio = lunes_de_la_semana(primer_dia)

    ultimo_dia_num = calendar.monthrange(year, month)[1]
    ultimo_dia = date(year, month, ultimo_dia_num)
    domingo_fin = ultimo_dia + timedelta(days=(6 - ultimo_dia.weekday()))

    data = _cargar()
    entradas_usuario = data.get(supervisor_usuario, {}) if supervisor_usuario else {}

    semanas = []
    actual = lunes_inicio
    while actual <= domingo_fin:
        semana = []
        for i in range(7):
            f = actual + timedelta(days=i)
            f_iso = f.isoformat()
            semana.append({
                "fecha_iso":     f_iso,
                "dia_numero":    f.day,
                "es_mes_actual": f.month == month,
                "es_hoy":        f == hoy,
                "cantidad":      len(entradas_usuario.get(f_iso, [])),
            })
        semanas.append(semana)
        actual += timedelta(days=7)
    return semanas

















def calcular_gastos_mes(year: int, month: int, viaticos: dict, supervisores: list = None) -> dict:
    """Para el mes (year, month), recorre las entradas YA PASADAS (fecha <
    hoy — o sea, gastos reales/confirmados, no lo planificado a futuro) de
    los supervisores, y calcula cuánto se les debe en viáticos: por cada
    entrada cuyo vendedor tenga un viático configurado, se suma ese monto
    (si vio a 2 vendedores con viático el mismo día, cuenta 2 veces).

    'viaticos' es el dict {nombre_vendedor: monto} de logic/viaticos.py.
    'supervisores' es una lista de usuarios a incluir (si es None, se
    calculan todos los que tengan datos guardados).

    Devuelve:
        {
          "hugo": {"total": 4500.0, "detalle": [
              {"fecha": "2026-08-05", "vendedor": "21-FERREYRA...", "monto": 1500.0},
              ...
          ]},
          "ariel": {...},
        }
    """
    data = _cargar()
    hoy = date.today()
    prefijo = f"{year:04d}-{month:02d}"

    resultado = {}
    supervisores_a_revisar = supervisores if supervisores else list(data.keys())

    for sup in supervisores_a_revisar:
        dias = data.get(sup, {})
        detalle = []
        total = 0.0

        for fecha_iso, entradas in dias.items():
            if not fecha_iso.startswith(prefijo):
                continue
            try:
                f = date.fromisoformat(fecha_iso)
            except ValueError:
                continue
            if f >= hoy:
                continue  # solo días ya pasados: gasto real, no proyectado

            for e in entradas:
                v = (e.get("vendedor") or "").strip()
                if v in viaticos:
                    monto = float(viaticos[v])
                    total += monto
                    detalle.append({"fecha": fecha_iso, "vendedor": v, "monto": monto})

        detalle.sort(key=lambda d: d["fecha"])
        resultado[sup] = {"total": total, "detalle": detalle}

    return resultado