from flask import request
from dash import Input, Output, html
from dash.exceptions import PreventUpdate

from config import FONT
from data.cache import CACHE
from logic.resumen import render_resumen_cards


def _get_current_user() -> str:
    """Devuelve el usuario logueado via HTTP Basic Auth."""
    auth = request.authorization
    if auth:
        return auth.username.lower()
    return ""


def _es_supervisor(usuario: str, app) -> bool:
    return usuario in app.SUPERVISORES


def _vendedor_de_usuario(usuario: str, app):
    """Devuelve el nombre completo del vendedor si el usuario es un vendedor, sino None."""
    return app.VENDEDOR_MAP.get(usuario)


def register(app):

    @app.callback(
        Output("f_vend_resumen", "options"),
        Output("f_vend_resumen", "value"),
        Input("main_tabs", "value"),
        Input("f_year",    "value"),
        Input("f_month",   "value"),
    )
    def update_vend_resumen(tab, year, month):
        if tab != "tab_resumen" or year is None or month is None:
            return [], None

        usuario  = _get_current_user()
        es_super = _es_supervisor(usuario, app)
        vend_fijo = _vendedor_de_usuario(usuario, app)

        resumen = CACHE.get_resumen(year, month)

        if es_super:
            opts = [{"label": v, "value": v} for v in sorted(resumen.keys())]
            val  = opts[0]["value"] if opts else None
        elif vend_fijo and vend_fijo in resumen:
            opts = [{"label": vend_fijo, "value": vend_fijo}]
            val  = vend_fijo
        else:
            opts = []
            val  = None

        return opts, val

    @app.callback(
        Output("resumen_cards", "children"),
        Input("main_tabs",      "value"),
        Input("btn_reload",     "n_clicks"),
        Input("f_year",         "value"),
        Input("f_month",        "value"),
        Input("f_vend_resumen", "value"),
    )
    def refresh_resumen(tab, n_clicks, year, month, vend):
        if tab != "tab_resumen":
            raise PreventUpdate

        if year is None or month is None:
            return [html.Div(
                "Seleccioná un Año y Mes para ver el resumen.",
                style={"color": "#64748b", "fontFamily": FONT, "padding": "40px",
                       "textAlign": "center", "fontSize": "14px"},
            )]

        usuario  = _get_current_user()
        es_super = _es_supervisor(usuario, app)
        vend_fijo = _vendedor_de_usuario(usuario, app)

        # Vendedor no puede ver otros vendedores
        if not es_super and vend_fijo:
            vend = vend_fijo
        elif not es_super and not vend_fijo:
            return [html.Div(
                "No tenés acceso a esta sección.",
                style={"color": "#64748b", "fontFamily": FONT, "padding": "40px",
                       "textAlign": "center", "fontSize": "14px"},
            )]

        if not vend:
            return [html.Div(
                "Seleccioná un vendedor del dropdown de arriba.",
                style={"color": "#64748b", "fontFamily": FONT, "padding": "40px",
                       "textAlign": "center", "fontSize": "14px"},
            )]

        resumen = CACHE.get_resumen(year, month)

        if vend not in resumen:
            return [html.Div(
                f"Sin datos para {vend} en {month:02d}/{year}.",
                style={"color": "#64748b", "fontFamily": FONT, "padding": "40px",
                       "textAlign": "center", "fontSize": "14px"},
            )]

        return render_resumen_cards({vend: resumen[vend]})