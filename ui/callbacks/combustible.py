import re
from io import BytesIO

import pandas as pd
from dash import Input, Output, State, dcc
from dash.exceptions import PreventUpdate
from flask import request as flask_request

from logic.pagos_combustible import (
    obtener_precio_nafta, guardar_precio_nafta,
    obtener_ruta_mes, guardar_ruta_mes,
    asegurar_rutas_mes,
    calcular_liquidacion_combustible_mes,
    DIAS_SEMANA,
)

COLUMNAS_DIA = {"Lunes": "lunes", "Martes": "martes", "Miercoles": "miercoles", "Jueves": "jueves", "Viernes": "viernes", "Sabado": "sabado"}


def _fmt_monto(m: float) -> str:
    return f"${m:,.2f}".replace(",", "@").replace(".", ",").replace("@", ".")


def register(app):

    def _usuario_actual() -> str:
        auth = flask_request.authorization
        return auth.username.lower() if auth else ""

    def _es_admin(usuario: str) -> bool:
        return usuario == getattr(app, "ADMIN_TELEGRAM_USUARIO", None)

    ESTILO_ERROR = {"fontSize": "12px", "fontFamily": "inherit", "color": "#f87171", "fontWeight": "600"}
    ESTILO_OK    = {"fontSize": "12px", "fontFamily": "inherit", "color": "#4ade80", "fontWeight": "600"}

    # ── Guardar / actualizar el precio de nafta del mes elegido ──────
    @app.callback(
        Output("combustible_precio_status_msg", "children"),
        Output("combustible_precio_status_msg", "style"),
        Input("btn_combustible_precio_guardar", "n_clicks"),
        State("combustible_precio_input", "value"),
        State("gastos_mes_store",         "data"),
        prevent_initial_call=True,
    )
    def guardar_precio_nafta_cb(n_clicks, precio, mes_data):
        usuario = _usuario_actual()
        if not _es_admin(usuario):
            raise PreventUpdate
        if not mes_data:
            return "⚠️ Elegí un mes primero (arriba).", ESTILO_ERROR
        if precio is None or float(precio) <= 0:
            return "⚠️ Poné un precio mayor a cero.", ESTILO_ERROR

        year, month = mes_data["year"], mes_data["month"]
        guardar_precio_nafta(year, month, float(precio))
        return f"✅ Precio de nafta guardado para {month:02d}/{year}: {_fmt_monto(float(precio))}.", ESTILO_OK

    # ── Precargar el precio de nafta al cambiar de mes ────────────────
    @app.callback(
        Output("combustible_precio_input", "value"),
        Input("gastos_mes_store", "data"),
    )
    def cargar_precio_nafta(mes_data):
        if not mes_data:
            raise PreventUpdate
        usuario = _usuario_actual()
        if not _es_admin(usuario):
            raise PreventUpdate
        year, month = mes_data["year"], mes_data["month"]
        precio = obtener_precio_nafta(year, month)
        return precio if precio > 0 else None

    # ── Cargar la tabla de rutas de TODOS los vendedores, copiando sola
    #    del mes anterior si un vendedor no tiene nada cargado este mes ──
    @app.callback(
        Output("combustible_tbl_rutas", "data"),
        Input("gastos_mes_store",                "data"),
        Input("combustible_ruta_status_msg",     "children"),
    )
    def cargar_tabla_rutas(mes_data, _status):
        if not mes_data:
            raise PreventUpdate
        usuario = _usuario_actual()
        if not _es_admin(usuario):
            raise PreventUpdate

        year, month = mes_data["year"], mes_data["month"]
        vendedores = sorted(app.VENDEDOR_MAP.values())

        asegurar_rutas_mes(vendedores, year, month)

        rows = []
        for vendedor in vendedores:
            kms_por_dia = obtener_ruta_mes(vendedor, year, month)
            row = {"vendedor": vendedor}
            for dia, col in COLUMNAS_DIA.items():
                row[col] = kms_por_dia.get(dia, 0) or None
            rows.append(row)
        return rows

    # ── Guardar toda la tabla de rutas de una sola vez ────────────────
    @app.callback(
        Output("combustible_ruta_status_msg", "children"),
        Output("combustible_ruta_status_msg", "style"),
        Input("btn_combustible_ruta_guardar", "n_clicks"),
        State("combustible_tbl_rutas", "data"),
        State("gastos_mes_store",      "data"),
        prevent_initial_call=True,
    )
    def guardar_tabla_rutas_cb(n_clicks, filas, mes_data):
        usuario = _usuario_actual()
        if not _es_admin(usuario):
            raise PreventUpdate
        if not mes_data:
            return "⚠️ Elegí un mes primero (arriba).", ESTILO_ERROR

        year, month = mes_data["year"], mes_data["month"]

        for fila in filas or []:
            vendedor = fila.get("vendedor")
            if not vendedor:
                continue
            kms_por_dia = {dia: fila.get(col) for dia, col in COLUMNAS_DIA.items()}
            guardar_ruta_mes(vendedor, year, month, kms_por_dia)

        return f"✅ Rutas guardadas para {month:02d}/{year}.", ESTILO_OK

    # ── Calcular y mostrar la tabla de liquidación de combustible ─────
    @app.callback(
        Output("combustible_tbl_liquidacion", "data"),
        Input("gastos_mes_store",             "data"),
        Input("combustible_ruta_status_msg",  "children"),
    )
    def refrescar_liquidacion_combustible(mes_data, _status):
        if not mes_data:
            raise PreventUpdate
        usuario = _usuario_actual()
        if not _es_admin(usuario):
            raise PreventUpdate

        year, month = mes_data["year"], mes_data["month"]
        liquidacion = calcular_liquidacion_combustible_mes(year, month)

        rows = []
        for vendedor, info in sorted(liquidacion.items()):
            rows.append({
                "vendedor":                    vendedor,
                "kms_totales":                 f"{info['kms_totales']:,.0f}",
                "dias_ausente_descontados":    info["dias_ausente_descontados"],
                "precio_nafta_fmt":            _fmt_monto(info["precio_nafta"]),
                "total_fmt":                   _fmt_monto(info["total"]),
            })
        return rows

    # ── Descarga Excel de la liquidación de combustible ────────────
    # Usa "derived_virtual_data": lo que está REALMENTE visible en la tabla
    # en ese momento (con los filtros/orden propios de la tabla aplicados),
    # igual que el patrón ya usado en dashboard.py.
    @app.callback(
        Output("download_combustible_excel", "data"),
        Input("btn_download_combustible", "n_clicks"),
        State("combustible_tbl_liquidacion", "derived_virtual_data"),
        State("combustible_tbl_liquidacion", "data"),
        State("gastos_mes_store", "data"),
        prevent_initial_call=True,
    )
    def download_combustible_excel(n_clicks, derived_data, data, mes_data):
        filas = derived_data if derived_data is not None else (data or [])
        df = pd.DataFrame(filas)
        if df.empty:
            df = pd.DataFrame(columns=[
                "vendedor", "kms_totales", "dias_ausente_descontados",
                "precio_nafta_fmt", "total_fmt",
            ])

        df = df.rename(columns={
            "vendedor":                 "Vendedor",
            "kms_totales":              "Kms totales",
            "dias_ausente_descontados": "Días ausente descontados",
            "precio_nafta_fmt":         "Precio nafta",
            "total_fmt":                "Total a liquidar",
        })

        output = BytesIO()
        with pd.ExcelWriter(output, engine="openpyxl") as writer:
            df.to_excel(writer, index=False, sheet_name="Combustible")
            ws = writer.book["Combustible"]
            for col_cells in ws.columns:
                max_len = max((len(str(c.value or "")) for c in col_cells), default=0)
                ws.column_dimensions[col_cells[0].column_letter].width = max_len + 2
        output.seek(0)

        parts = ["liquidacion_combustible"]
        if mes_data:
            parts.append(str(mes_data.get("year", "")))
            month = mes_data.get("month")
            if month:
                parts.append(f"{int(month):02d}")
        return dcc.send_bytes(output.getvalue(), "_".join(p for p in parts if p) + ".xlsx")