import traceback

import pandas as pd
from dash import Input, Output

from data.cache import CACHE
from logic.rankings import build_rankings, build_corona_ranking
from logic.resumen import build_inactivos_comparativo


def register(app):

    @app.callback(
        Output("tbl_mejores",        "data"),    Output("tbl_mejores",        "columns"),
        Output("tbl_peores",         "data"),    Output("tbl_peores",         "columns"),
        Output("tbl_mejoraron",      "data"),    Output("tbl_mejoraron",      "columns"),
        Output("tbl_empeoraron",     "data"),    Output("tbl_empeoraron",     "columns"),
        Output("tbl_inactivos_todos","data"),    Output("tbl_inactivos_todos","columns"),
        Output("tbl_corona",         "data"),    Output("tbl_corona",         "columns"),
        Output("ranking_periodo_label","children"),
        Input("btn_reload", "n_clicks"),
        Input("f_year",     "value"),
        Input("f_month",    "value"),
    )
    def update_rankings(n_clicks, year, month):
        try:
            # BUG FIX: pasar vis_df y ven_df correctamente
            rankings = build_rankings(CACHE.vis, CACHE.ven, year, month)

            cur  = rankings.get("cur_label",  "—")
            prev = rankings.get("prev_label", "—")
            label = f"Período actual: {cur}  ·  Comparando contra: {prev}  ·  (filtro de vendedor no aplica al ranking)"

            def to_table(df):
                if not isinstance(df, pd.DataFrame) or df.empty:
                    return [], []
                return df.to_dict("records"), [{"name": c, "id": c} for c in df.columns]

            d_mej, c_mej = to_table(rankings.get("mejores",    pd.DataFrame()))
            d_peo, c_peo = to_table(rankings.get("peores",     pd.DataFrame()))
            d_mjo, c_mjo = to_table(rankings.get("mejoraron",  pd.DataFrame()))
            d_emp, c_emp = to_table(rankings.get("empeoraron", pd.DataFrame()))

            # BUG FIX: pasar ven_df correctamente
            df_corona    = build_corona_ranking(CACHE.ven, year, month)
            d_cor, c_cor = to_table(df_corona)

            df_inact = build_inactivos_comparativo()
            if isinstance(df_inact, pd.DataFrame) and not df_inact.empty:
                orden = ["Cod. Vendedor", "Clientes en cartera", "Clientes con venta",
                         "Total inactivos", "Inactivos mes ant.", "Variación", "% Inactivos", "% Inact. ant.",
                         "Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
                cols  = [c for c in orden if c in df_inact.columns]
                otros = [c for c in df_inact.columns if c not in cols]
                df_inact = df_inact[cols + otros]
                for pct_col in ["% Inactivos", "% Inact. ant."]:
                    if pct_col in df_inact.columns:
                        df_inact[pct_col] = df_inact[pct_col].apply(
                            lambda x: f"{float(x) * 100:.2f}%" if pd.notna(x) and str(x) != "" else ""
                        )
            d_inact, c_inact = to_table(df_inact)

            return d_mej, c_mej, d_peo, c_peo, d_mjo, c_mjo, d_emp, c_emp, d_inact, c_inact, d_cor, c_cor, label

        except Exception as e:
            traceback.print_exc()
            empty = []
            return empty, empty, empty, empty, empty, empty, empty, empty, empty, empty, empty, empty, f"ERROR: {e}"
