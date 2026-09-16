from datetime import date

from dash import Input, Output, State, html, ctx
from dash.exceptions import PreventUpdate
from flask import request as flask_request

from logic.viaticos import obtener_viaticos, guardar_viatico, eliminar_viatico
from logic.planificacion import calcular_gastos_mes
from logic.pagos_vendedores import (
    obtener_montos_diarios,
    obtener_ausencias_mes, guardar_ausencias_mes,
    dias_habiles_mes, calcular_liquidacion_mes,
)

DIAS_ES_CORTO = ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb"]

MESES_ES = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio",
            "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]


def _fmt_monto(m: float) -> str:
    return f"${m:,.2f}".replace(",", "@").replace(".", ",").replace("@", ".")


def register(app):

    def _usuario_actual() -> str:
        auth = flask_request.authorization
        return auth.username.lower() if auth else ""

    def _es_admin(usuario: str) -> bool:
        return usuario == getattr(app, "ADMIN_TELEGRAM_USUARIO", None)

    # ── Poblar dropdown de vendedores (todos, sin restricción de equipo,
    #    porque el admin puede cargar viático para cualquiera) ──
    @app.callback(
        Output("gastos_vendedor", "options"),
        Input("main_tabs", "value"),
    )
    def poblar_vendedores_gastos(tab):
        if tab != "tab_gastos":
            raise PreventUpdate
        usuario = _usuario_actual()
        if not _es_admin(usuario):
            raise PreventUpdate
        opciones = [{"label": nombre, "value": nombre} for nombre in app.VENDEDOR_MAP.values()]
        return sorted(opciones, key=lambda o: o["label"])

    # ── Guardar (crear/actualizar) un viático ──────────────────────
    @app.callback(
        Output("gastos_vendedor",     "value"),
        Output("gastos_monto",        "value"),
        Output("gastos_status_msg",   "children"),
        Output("gastos_status_msg",   "style"),
        Output("gastos_ids_store",    "data"),
        Input("btn_gastos_guardar", "n_clicks"),
        State("gastos_vendedor",    "value"),
        State("gastos_monto",       "value"),
        prevent_initial_call=True,
    )
    def guardar_viatico_cb(n_clicks, vendedor, monto):
        usuario = _usuario_actual()
        estilo_error = {"fontSize": "12px", "fontFamily": "inherit", "color": "#f87171", "fontWeight": "600"}
        estilo_ok    = {"fontSize": "12px", "fontFamily": "inherit", "color": "#4ade80", "fontWeight": "600"}

        if not _es_admin(usuario):
            raise PreventUpdate

        if not vendedor:
            return vendedor, monto, "⚠️ Elegí un vendedor primero.", estilo_error, list(obtener_viaticos().keys())
        if monto is None or float(monto) <= 0:
            return vendedor, monto, "⚠️ Poné un monto mayor a cero.", estilo_error, list(obtener_viaticos().keys())

        guardar_viatico(vendedor, float(monto))
        return None, None, f"✅ Viático de {vendedor} guardado.", estilo_ok, list(obtener_viaticos().keys())

    # ── Cargar la tabla de viáticos configurados ────────────────────
    @app.callback(
        Output("gastos_tbl_viaticos", "data"),
        Input("gastos_ids_store", "data"),
        Input("main_tabs",        "value"),
    )
    def cargar_tabla_viaticos(_ids, tab):
        if tab != "tab_gastos":
            raise PreventUpdate
        usuario = _usuario_actual()
        if not _es_admin(usuario):
            raise PreventUpdate
        viaticos = obtener_viaticos()
        data = [
            {"vendedor": v, "monto_fmt": _fmt_monto(m)}
            for v, m in sorted(viaticos.items())
        ]
        return data

    # ── Detectar filas borradas en la tabla de viáticos (row_deletable) ──
    @app.callback(
        Output("gastos_ids_store", "data", allow_duplicate=True),
        Input("gastos_tbl_viaticos", "data"),
        State("gastos_ids_store",    "data"),
        prevent_initial_call=True,
    )
    def detectar_borrado_viatico(data_actual, ids_previos):
        usuario = _usuario_actual()
        if not _es_admin(usuario) or ids_previos is None:
            raise PreventUpdate

        vendedores_actuales = {row.get("vendedor") for row in (data_actual or [])}
        borrados = [v for v in ids_previos if v not in vendedores_actuales]
        if not borrados:
            raise PreventUpdate

        for v in borrados:
            eliminar_viatico(v)

        return list(obtener_viaticos().keys())

    # ── Navegación de mes (para el resumen) ─────────────────────────
    @app.callback(
        Output("gastos_mes_store", "data"),
        Input("main_tabs",              "value"),
        Input("btn_gastos_mes_anterior",  "n_clicks"),
        Input("btn_gastos_mes_siguiente", "n_clicks"),
        State("gastos_mes_store", "data"),
    )
    def actualizar_mes_gastos(tab, n_prev, n_next, mes_actual):
        trig = ctx.triggered_id

        if trig == "main_tabs":
            if tab != "tab_gastos" or mes_actual is not None:
                raise PreventUpdate
            hoy = date.today()
            return {"year": hoy.year, "month": hoy.month}

        if mes_actual is None:
            raise PreventUpdate
        y, m = mes_actual["year"], mes_actual["month"]

        if trig == "btn_gastos_mes_anterior":
            return {"year": y, "month": m - 1} if m > 1 else {"year": y - 1, "month": 12}
        if trig == "btn_gastos_mes_siguiente":
            return {"year": y, "month": m + 1} if m < 12 else {"year": y + 1, "month": 1}

        raise PreventUpdate

    # ── Calcular y mostrar el resumen del mes ───────────────────────
    @app.callback(
        Output("gastos_mes_label",      "children"),
        Output("gastos_resumen_cards",  "children"),
        Output("gastos_tbl_detalle",    "data"),
        Input("gastos_mes_store",   "data"),
        Input("gastos_ids_store",  "data"),
    )
    def refrescar_resumen_gastos(mes_data, _ids):
        if not mes_data:
            raise PreventUpdate

        usuario = _usuario_actual()
        if not _es_admin(usuario):
            raise PreventUpdate

        year, month = mes_data["year"], mes_data["month"]
        label = f"{MESES_ES[month - 1]} {year}"

        viaticos = obtener_viaticos()
        supervisores = sorted(app.SUPERVISORES)
        gastos = calcular_gastos_mes(year, month, viaticos, supervisores)

        # ── Tarjetas por supervisor ──
        cards = []
        for sup in supervisores:
            info  = gastos.get(sup, {"total": 0.0, "detalle": []})
            total = info["total"]
            cant  = len(info["detalle"])
            cards.append(html.Div(style={
                "backgroundColor": "#161b27", "border": "1px solid rgba(255,255,255,0.07)",
                "borderRadius": "12px", "padding": "16px 20px", "minWidth": "200px", "flex": "1",
            }, children=[
                html.Div(sup.capitalize(), style={"fontSize": "12px", "color": "#94a3b8", "fontFamily": "inherit", "fontWeight": "600", "marginBottom": "6px"}),
                html.Div(_fmt_monto(total), style={"fontSize": "24px", "color": "#4ade80", "fontFamily": "inherit", "fontWeight": "800"}),
                html.Div(f"{cant} salida{'s' if cant != 1 else ''} con viático", style={"fontSize": "11px", "color": "#64748b", "fontFamily": "inherit", "marginTop": "4px"}),
            ]))

        resumen_children = html.Div(cards, style={"display": "flex", "gap": "16px", "flexWrap": "wrap"}) if cards \
            else html.Div("No hay supervisores con datos.", style={"fontSize": "13px", "color": "#64748b", "fontFamily": "inherit"})

        # ── Tabla de detalle, todos los supervisores juntos ──
        detalle_rows = []
        for sup in supervisores:
            info = gastos.get(sup, {"detalle": []})
            for item in info["detalle"]:
                detalle_rows.append({
                    "supervisor": sup.capitalize(),
                    "fecha":      item["fecha"],
                    "vendedor":   item["vendedor"],
                    "monto_fmt":  _fmt_monto(item["monto"]),
                })

        return label, resumen_children, detalle_rows

    # ══════════════════════════════════════════════════════════════
    # LIQUIDACIÓN DE VENDEDORES (monto diario + ausencias marcadas)
    # ══════════════════════════════════════════════════════════════

    # ── Poblar el dropdown de vendedor de la sección de ausencias ──────
    @app.callback(
        Output("pagos_vend_ausencias", "options"),
        Input("main_tabs", "value"),
    )
    def poblar_vendedores_pagos(tab):
        if tab != "tab_gastos":
            raise PreventUpdate
        usuario = _usuario_actual()
        if not _es_admin(usuario):
            raise PreventUpdate
        opciones = sorted(
            [{"label": nombre, "value": nombre} for nombre in app.VENDEDOR_MAP.values()],
            key=lambda o: o["label"],
        )
        return opciones

    # ── Armar el checklist de días hábiles del mes elegido, precargado
    #    con las ausencias ya guardadas del vendedor elegido ──────────
    @app.callback(
        Output("pagos_ausencias_checklist", "options"),
        Output("pagos_ausencias_checklist", "value"),
        Input("gastos_mes_store",      "data"),
        Input("pagos_vend_ausencias",  "value"),
    )
    def cargar_checklist_ausencias(mes_data, vendedor):
        if not mes_data or not vendedor:
            return [], []
        usuario = _usuario_actual()
        if not _es_admin(usuario):
            raise PreventUpdate

        year, month = mes_data["year"], mes_data["month"]
        dias = dias_habiles_mes(year, month)

        opciones = [
            {"label": f"{DIAS_ES_CORTO[f.weekday()]} {f.strftime('%d/%m')}", "value": f.isoformat()}
            for f in dias
        ]
        ausencias_guardadas = obtener_ausencias_mes(vendedor, year, month)
        return opciones, ausencias_guardadas

    # ── Guardar las ausencias marcadas para el vendedor elegido ──────
    @app.callback(
        Output("pagos_ausencias_status_msg", "children"),
        Output("pagos_ausencias_status_msg", "style"),
        Input("btn_pagos_ausencias_guardar", "n_clicks"),
        State("pagos_vend_ausencias",         "value"),
        State("gastos_mes_store",             "data"),
        State("pagos_ausencias_checklist",    "value"),
        prevent_initial_call=True,
    )
    def guardar_ausencias_cb(n_clicks, vendedor, mes_data, dias_marcados):
        usuario = _usuario_actual()
        estilo_error = {"fontSize": "12px", "fontFamily": "inherit", "color": "#f87171", "fontWeight": "600"}
        estilo_ok    = {"fontSize": "12px", "fontFamily": "inherit", "color": "#4ade80", "fontWeight": "600"}

        if not _es_admin(usuario):
            raise PreventUpdate
        if not vendedor:
            return "⚠️ Elegí un vendedor primero.", estilo_error
        if not mes_data:
            return "⚠️ Elegí un mes primero (arriba).", estilo_error

        year, month = mes_data["year"], mes_data["month"]
        guardar_ausencias_mes(vendedor, year, month, dias_marcados or [])
        cant = len(dias_marcados or [])
        return f"✅ Guardado: {cant} día{'s' if cant != 1 else ''} marcado{'s' if cant != 1 else ''} sin salir para {vendedor}.", estilo_ok

    # ── Calcular y mostrar la tabla de liquidación de todos los
    #    vendedores con monto diario configurado ─────────────────────
    @app.callback(
        Output("pagos_tbl_liquidacion", "data"),
        Input("gastos_mes_store",       "data"),
        Input("pagos_montos_ids_store", "data"),
        Input("pagos_ausencias_status_msg", "children"),
    )
    def refrescar_liquidacion(mes_data, _ids, _status):
        if not mes_data:
            raise PreventUpdate
        usuario = _usuario_actual()
        if not _es_admin(usuario):
            raise PreventUpdate

        year, month = mes_data["year"], mes_data["month"]
        montos = obtener_montos_diarios()
        liquidacion = calcular_liquidacion_mes(year, month, montos)

        rows = []
        for vendedor, info in sorted(liquidacion.items()):
            rows.append({
                "vendedor":          vendedor,
                "dias_habiles":      info["dias_habiles"],
                "dias_ausente":      info["dias_ausente"],
                "dias_pagados":      info["dias_pagados"],
                "monto_diario_fmt":  _fmt_monto(info["monto_diario"]),
                "total_fmt":         _fmt_monto(info["total"]),
            })
        return rows