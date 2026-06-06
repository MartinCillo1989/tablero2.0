from dash import Input, Output, html
from dash.exceptions import PreventUpdate

from config import FONT
from data.cache import CACHE
from logic.resumen import render_resumen_cards


def register(app):

    # ── Poblar dropdown de vendedores del tab resumen ────
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
        resumen = CACHE.get_resumen(year, month)
        opts = [{"label": v, "value": v} for v in sorted(resumen.keys())]
        # Preseleccionar el primero
        val = opts[0]["value"] if opts else None
        return opts, val

    # ── Mostrar card del vendedor seleccionado ───────────
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

        # Mostrar solo la card del vendedor seleccionado
        return render_resumen_cards({vend: resumen[vend]})