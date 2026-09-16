from datetime import date

from dash import Input, Output, State, html, ALL, ctx, no_update
from dash.exceptions import PreventUpdate
from flask import request as flask_request

from logic.planificacion import (
    agregar_entrada,
    eliminar_entrada,
    obtener_entradas_dia,
    lunes_de_la_semana,
    obtener_semana,
    obtener_mes,
    resumen_mes_equipo,
)

MESES_ES = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio",
            "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]
DIAS_HEADER = ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"]


def register(app):

    def _usuario_actual() -> str:
        auth = flask_request.authorization
        return auth.username.lower() if auth else ""

    def _es_admin(usuario: str) -> bool:
        return usuario == getattr(app, "ADMIN_TELEGRAM_USUARIO", None)

    # ── Poblar dropdown de vendedores con el equipo del supervisor logueado ──
    # (siempre es TU equipo, porque solo vos podés agregar entradas para vos)
    @app.callback(
        Output("planif_vendedor", "options"),
        Input("main_tabs", "value"),
    )
    def poblar_vendedores_planif(tab):
        if tab != "tab_planificacion":
            raise PreventUpdate
        usuario = _usuario_actual()
        usuarios_equipo = app.SUPERVISOR_VENDEDORES.get(usuario, [])
        opciones = [
            {"label": app.VENDEDOR_MAP[u], "value": app.VENDEDOR_MAP[u]}
            for u in usuarios_equipo if u in app.VENDEDOR_MAP
        ]
        return sorted(opciones, key=lambda o: o["label"])

    # ── Poblar el selector "Ver calendario de" — SOLO para el admin ──
    @app.callback(
        Output("planif_supervisor_wrapper", "style"),
        Output("planif_supervisor_ver",     "options"),
        Output("planif_supervisor_ver",     "value"),
        Input("main_tabs", "value"),
    )
    def poblar_selector_supervisor(tab):
        if tab != "tab_planificacion":
            raise PreventUpdate

        usuario = _usuario_actual()
        if not _es_admin(usuario):
            # No sos admin: el selector queda oculto, y tu "calendario a ver"
            # sos siempre vos mismo (no hace falta dropdown para eso).
            return {"display": "none"}, [], None

        # Sos admin: mostrás el selector con todos los supervisores conocidos
        supervisores = sorted(app.SUPERVISORES)
        opciones = [{"label": s.capitalize(), "value": s} for s in supervisores]
        return (
            {"display": "block", "maxWidth": "320px", "marginBottom": "16px"},
            opciones,
            usuario,  # por defecto, arranca viendo su propio calendario
        )

    # ── Mostrar/ocultar el formulario de agregar + aviso de solo lectura ──
    @app.callback(
        Output("planif_form_wrapper",       "style"),
        Output("planif_modo_lectura_aviso", "style"),
        Output("planif_tbl_dia",            "row_deletable"),
        Input("planif_supervisor_ver", "value"),
        Input("main_tabs",             "value"),
    )
    def toggle_modo_lectura(supervisor_ver, tab):
        if tab != "tab_planificacion":
            raise PreventUpdate

        usuario = _usuario_actual()
        usuario_objetivo = supervisor_ver or usuario
        es_propio = (usuario_objetivo == usuario)

        if es_propio:
            return {"display": "block"}, {"display": "none"}, True
        else:
            return (
                {"display": "none"},
                {"display": "block", "fontSize": "12px", "color": "#f59e0b",
                 "fontFamily": "inherit", "fontStyle": "italic", "marginBottom": "16px"},
                False,
            )

    # ── Agregar una entrada nueva (vendedor + motivo/nota) al día elegido ──
    # Solo agrega para VOS MISMO, nunca para el calendario de otro.
    @app.callback(
        Output("planif_nota",           "value"),
        Output("planif_motivo",         "value"),
        Output("planif_refresh_trg",    "data"),
        Output("planif_agregar_status", "children"),
        Output("planif_agregar_status", "style"),
        Input("btn_planif_agregar", "n_clicks"),
        State("planif_fecha",       "date"),
        State("planif_vendedor",    "value"),
        State("planif_motivo",      "value"),
        State("planif_nota",        "value"),
        State("planif_refresh_trg", "data"),
        prevent_initial_call=True,
    )
    def agregar(n_clicks, fecha_iso, vendedor, motivos, detalle, trg):
        estilo_base  = {"fontSize": "12px", "fontFamily": "inherit", "fontWeight": "600"}
        estilo_error = {**estilo_base, "color": "#f87171"}
        estilo_ok    = {**estilo_base, "color": "#4ade80"}

        usuario = _usuario_actual()
        if not usuario or not fecha_iso:
            raise PreventUpdate

        detalle = (detalle or "").strip()
        seleccionados = motivos or []
        if not isinstance(seleccionados, list):
            seleccionados = [seleccionados]

        es_otro = "__otro__" in seleccionados
        motivos_preset = [m for m in seleccionados if m and m != "__otro__"]

        if es_otro and not detalle:
            # Eligió "Otro" pero no escribió nada abajo: no hay nota que guardar.
            return (no_update, no_update, no_update,
                    "⚠️ Elegiste \"Otro\" pero no escribiste nada en Detalle.", estilo_error)

        partes = []
        if motivos_preset:
            partes.append(", ".join(motivos_preset))
        if detalle:
            partes.append(detalle)

        if not partes:
            return (no_update, no_update, no_update,
                    "⚠️ Elegí un motivo o escribí algo en Detalle antes de agregar.", estilo_error)

        nota_final = " — ".join(partes)

        agregar_entrada(usuario, fecha_iso, vendedor or "", nota_final)
        # limpia el textarea y el dropdown, dispara el refresh, muestra el ✅
        return "", None, (trg or 0) + 1, "✅ Entrada agregada correctamente.", estilo_ok

    # ── Cargar la tabla del día elegido + el resumen de la semana ──
    # Usa el calendario de "supervisor_ver" si el admin eligió ver el de otro,
    # o el propio en cualquier otro caso.
    @app.callback(
        Output("planif_tbl_dia",    "data"),
        Output("planif_tbl_semana", "data"),
        Output("planif_ids_store",  "data"),
        Input("planif_fecha",       "date"),
        Input("planif_refresh_trg", "data"),
        Input("planif_supervisor_ver", "value"),
    )
    def cargar_tablas(fecha_iso, _trg, supervisor_ver):
        usuario = _usuario_actual()
        usuario_objetivo = supervisor_ver or usuario
        if not usuario_objetivo or not fecha_iso:
            return [], [], []

        f = date.fromisoformat(fecha_iso)

        entradas_dia = obtener_entradas_dia(usuario_objetivo, fecha_iso)
        data_dia = [
            {"id": e["id"], "vendedor": e["vendedor"] or "— (tarea general)", "nota": e["nota"]}
            for e in entradas_dia
        ]
        ids_dia = [e["id"] for e in entradas_dia]

        lunes  = lunes_de_la_semana(f)
        semana = obtener_semana(usuario_objetivo, lunes)
        data_semana = []
        for dia in semana:
            for e in dia["entradas"]:
                data_semana.append({
                    "dia_semana":  dia["dia_semana"],
                    "fecha_corta": dia["fecha_corta"],
                    "vendedor":    e["vendedor"] or "— (tarea general)",
                    "nota":        e["nota"],
                })

        return data_dia, data_semana, ids_dia

    # ── Detectar filas borradas en la tabla del día (row_deletable) y
    #    reflejar el borrado en el almacenamiento. row_deletable está en
    #    False cuando mirás el calendario de otra persona, pero igual
    #    chequeamos acá por las dudas (salvaguarda extra) ──
    @app.callback(
        Output("planif_ids_store",   "data", allow_duplicate=True),
        Output("planif_refresh_trg", "data", allow_duplicate=True),
        Input("planif_tbl_dia",      "data"),
        State("planif_ids_store",    "data"),
        State("planif_fecha",        "date"),
        State("planif_supervisor_ver", "value"),
        State("planif_refresh_trg",  "data"),
        prevent_initial_call=True,
    )
    def detectar_borrado(data_actual, ids_previos, fecha_iso, supervisor_ver, trg):
        usuario = _usuario_actual()
        usuario_objetivo = supervisor_ver or usuario
        if not usuario or not fecha_iso or ids_previos is None:
            raise PreventUpdate
        if usuario_objetivo != usuario:
            # Nunca borrar entradas de otra persona.
            raise PreventUpdate

        ids_actuales = [row.get("id") for row in (data_actual or [])]
        borrados = [i for i in ids_previos if i not in ids_actuales]
        if not borrados:
            raise PreventUpdate

        for entrada_id in borrados:
            eliminar_entrada(usuario, fecha_iso, entrada_id)

        # Disparamos también el refresh general para que el resumen de la
        # semana (que no escucha directamente esta tabla) se actualice.
        return ids_actuales, (trg or 0) + 1

    # ── Determinar qué mes se está mostrando (navegación ← / →) ──
    @app.callback(
        Output("planif_mes_store", "data"),
        Input("main_tabs", "value"),
        Input("btn_planif_mes_anterior", "n_clicks"),
        Input("btn_planif_mes_siguiente", "n_clicks"),
        State("planif_mes_store", "data"),
    )
    def actualizar_mes(tab, n_prev, n_next, mes_actual):
        trig = ctx.triggered_id

        if trig == "main_tabs":
            if tab != "tab_planificacion" or mes_actual is not None:
                raise PreventUpdate
            hoy = date.today()
            return {"year": hoy.year, "month": hoy.month}

        if mes_actual is None:
            raise PreventUpdate
        y, m = mes_actual["year"], mes_actual["month"]

        if trig == "btn_planif_mes_anterior":
            return {"year": y, "month": m - 1} if m > 1 else {"year": y - 1, "month": 12}
        if trig == "btn_planif_mes_siguiente":
            return {"year": y, "month": m + 1} if m < 12 else {"year": y + 1, "month": 1}

        raise PreventUpdate

    # ── Dibujar la grilla del mes ──────────────────────────────────
    @app.callback(
        Output("planif_calendario_grid", "children"),
        Output("planif_mes_label",       "children"),
        Input("planif_mes_store",       "data"),
        Input("planif_supervisor_ver",  "value"),
        Input("planif_refresh_trg",     "data"),
        Input("planif_fecha",           "date"),
    )
    def renderizar_calendario(mes_data, supervisor_ver, _trg, fecha_seleccionada):
        if not mes_data:
            raise PreventUpdate

        usuario = _usuario_actual()
        usuario_objetivo = supervisor_ver or usuario
        year, month = mes_data["year"], mes_data["month"]

        semanas = obtener_mes(usuario_objetivo, year, month)
        label = f"{MESES_ES[month - 1]} {year}"

        header = html.Div(
            style={"display": "grid", "gridTemplateColumns": "repeat(7, 1fr)", "gap": "6px", "marginBottom": "6px"},
            children=[
                html.Div(d, style={"textAlign": "center", "fontSize": "11px", "color": "#64748b",
                                    "fontFamily": "inherit", "fontWeight": "700", "textTransform": "uppercase"})
                for d in DIAS_HEADER
            ],
        )

        filas = []
        for semana in semanas:
            celdas = []
            for dia in semana:
                es_hoy         = dia["es_hoy"]
                es_mes         = dia["es_mes_actual"]
                cantidad       = dia["cantidad"]
                es_seleccionado = (dia["fecha_iso"] == fecha_seleccionada)

                if es_seleccionado:
                    borde = "2px solid #4ade80"
                elif es_hoy:
                    borde = "2px solid #3b82f6"
                else:
                    borde = "1px solid rgba(255,255,255,0.06)"

                estilo_celda = {
                    "cursor": "pointer", "textAlign": "center", "padding": "10px 4px",
                    "borderRadius": "8px", "fontFamily": "inherit", "fontSize": "13px",
                    "minHeight": "44px", "display": "flex", "flexDirection": "column",
                    "alignItems": "center", "justifyContent": "center", "gap": "2px",
                    "backgroundColor": "rgba(74,222,128,0.08)" if es_seleccionado else ("#161b27" if es_mes else "transparent"),
                    "color": "#e2e8f0" if es_mes else "#334155",
                    "border": borde,
                    "opacity": "1" if es_mes else "0.5",
                }

                hijos_celda = [html.Span(str(dia["dia_numero"]), style={"fontWeight": "700" if (es_hoy or es_seleccionado) else "500"})]
                if cantidad > 0:
                    hijos_celda.append(html.Span(
                        f"● {cantidad}",
                        style={"fontSize": "10px", "color": "#4ade80" if es_mes else "#475569"},
                    ))

                celdas.append(html.Button(
                    hijos_celda,
                    id={"type": "planif_day_btn", "fecha": dia["fecha_iso"]},
                    n_clicks=0,
                    style=estilo_celda,
                ))
            filas.append(html.Div(
                style={"display": "grid", "gridTemplateColumns": "repeat(7, 1fr)", "gap": "6px", "marginBottom": "6px"},
                children=celdas,
            ))

        grid = html.Div([header] + filas)
        return grid, label

    # ── Etiqueta con la fecha seleccionada (chica, junto a "Entradas de ese
    #    día") + el cartel grande junto al selector de fecha ──
    @app.callback(
        Output("planif_dia_seleccionado_label", "children"),
        Output("planif_fecha_grande",           "children"),
        Input("planif_fecha", "date"),
    )
    def actualizar_label_dia(fecha_iso):
        if not fecha_iso:
            raise PreventUpdate
        f = date.fromisoformat(fecha_iso)
        dias_es = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
        texto = f"{dias_es[f.weekday()].capitalize()} {f.strftime('%d/%m/%Y')}"
        return f"— {texto}", f"📅 {texto}"

    # ── Click en un día del calendario: lo selecciona como "planif_fecha" ──
    @app.callback(
        Output("planif_fecha", "date"),
        Input({"type": "planif_day_btn", "fecha": ALL}, "n_clicks"),
        prevent_initial_call=True,
    )
    def click_dia_calendario(n_clicks_list):
        trig = ctx.triggered_id
        if not trig or not isinstance(trig, dict):
            raise PreventUpdate
        if not ctx.triggered or not ctx.triggered[0]["value"]:
            # Evita reaccionar cuando el grid se re-renderiza y los botones
            # "aparecen" con n_clicks=0 (eso también dispara el Input).
            raise PreventUpdate
        return trig.get("fecha")

    # ── Resumen: con quién del equipo ya se anotó actividad este mes ──
    @app.callback(
        Output("planif_resumen_equipo", "children"),
        Input("planif_refresh_trg",    "data"),
        Input("planif_supervisor_ver", "value"),
        Input("main_tabs",             "value"),
        Input("planif_mes_store",      "data"),
    )
    def actualizar_resumen_equipo(_trg, supervisor_ver, tab, mes_data):
        if tab != "tab_planificacion" or not mes_data:
            raise PreventUpdate

        usuario = _usuario_actual()
        usuario_objetivo = supervisor_ver or usuario

        usuarios_equipo = app.SUPERVISOR_VENDEDORES.get(usuario_objetivo, [])
        equipo_nombres = [app.VENDEDOR_MAP[u] for u in usuarios_equipo if u in app.VENDEDOR_MAP]

        if not equipo_nombres:
            return html.Div(
                "No hay vendedores asignados a este equipo.",
                style={"fontSize": "13px", "color": "#64748b", "fontFamily": "inherit"},
            )

        year, month = mes_data["year"], mes_data["month"]
        resumen = resumen_mes_equipo(usuario_objetivo, year, month, equipo_nombres)
        con = resumen["con_actividad"]
        sin = resumen["sin_actividad"]
        total = len(equipo_nombres)

        estilo_col_titulo_ok  = {"fontSize": "13px", "fontWeight": "700", "color": "#4ade80", "fontFamily": "inherit", "marginBottom": "8px"}
        estilo_col_titulo_no  = {"fontSize": "13px", "fontWeight": "700", "color": "#f87171", "fontFamily": "inherit", "marginBottom": "8px"}
        estilo_item           = {"fontSize": "13px", "color": "#e2e8f0", "fontFamily": "inherit", "padding": "3px 0"}
        estilo_vacio          = {"fontSize": "12px", "color": "#475569", "fontFamily": "inherit", "fontStyle": "italic"}

        return html.Div([
            html.Div(
                f"{MESES_ES[month - 1]} {year} — {len(con)} de {total} vendedores con actividad registrada",
                style={"fontSize": "13px", "color": "#94a3b8", "fontFamily": "inherit", "fontWeight": "600", "marginBottom": "16px"},
            ),
            html.Div(
                style={"display": "flex", "gap": "32px", "flexWrap": "wrap"},
                children=[
                    html.Div(style={"minWidth": "200px"}, children=[
                        html.Div(f"✅ Ya salieron / anotaron ({len(con)})", style=estilo_col_titulo_ok),
                        html.Div([
                            html.Div(f"{v} ({c})" if c > 1 else v, style=estilo_item)
                            for v, c in con
                        ]) if con
                        else html.Div("Todavía nadie este mes.", style=estilo_vacio),
                    ]),
                    html.Div(style={"minWidth": "200px"}, children=[
                        html.Div(f"❌ Todavía falta ({len(sin)})", style=estilo_col_titulo_no),
                        html.Div([html.Div(v, style=estilo_item) for v in sin]) if sin
                        else html.Div("¡Ya anotaste a todo el equipo!", style=estilo_vacio),
                    ]),
                ],
            ),
        ])









"""
Planificación semanal del SUPERVISOR: es su propio calendario. Para cada
día de la semana, el supervisor va agregando entradas — cada entrada es
"con qué vendedor" + "qué va a hacer / qué hizo". Un mismo día puede tener
varias entradas (varios vendedores distintos ese día).

Se guarda en un JSON simple (PLANIFICACION_FILE), organizado por supervisor
y por fecha:
    {
      "hugo": {
        "2026-08-05": [
          {"id": "a1b2c3", "vendedor": "21-FERREYRA MAURICIO EMANUEL",
           "nota": "Acompañar visita zona norte", "actualizado_at": "..."},
          {"id": "d4e5f6", "vendedor": "02-LAMPERT MATIAS",
           "nota": "Revisar objetivo Corona", "actualizado_at": "..."}
        ],
        "2026-08-06": [...]
      },
      "ariel": {...}
    }
"""