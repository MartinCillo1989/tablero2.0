import traceback
from io import BytesIO

import pandas as pd
from dash import Input, Output, State, dcc

from data.cache import CACHE
from logic.rankings import build_rankings, build_corona_ranking, build_pier_roll_ranking
from logic.resumen import build_inactivos_comparativo


def register(app):

    @app.callback(
        Output("tbl_mejores",        "data"),    Output("tbl_mejores",        "columns"),
        Output("tbl_peores",         "data"),    Output("tbl_peores",         "columns"),
        Output("tbl_mejoraron",      "data"),    Output("tbl_mejoraron",      "columns"),
        Output("tbl_empeoraron",     "data"),    Output("tbl_empeoraron",     "columns"),
        Output("tbl_inactivos_todos","data"),    Output("tbl_inactivos_todos","columns"),
        Output("tbl_corona",         "data"),    Output("tbl_corona",         "columns"),
        Output("tbl_pier_roll",      "data"),    Output("tbl_pier_roll",      "columns"),
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

            df_pier_roll     = build_pier_roll_ranking(CACHE.ven, year, month)
            d_pr, c_pr        = to_table(df_pier_roll)

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

            return (d_mej, c_mej, d_peo, c_peo, d_mjo, c_mjo, d_emp, c_emp,
                    d_inact, c_inact, d_cor, c_cor, d_pr, c_pr, label)

        except Exception as e:
            traceback.print_exc()
            empty = []
            return (empty, empty, empty, empty, empty, empty, empty, empty,
                    empty, empty, empty, empty, empty, empty, f"ERROR: {e}")

    # ── Descarga Excel unificado: Corona + Pier & Roll ──────────
    @app.callback(
        Output("download_objetivos_excel", "data"),
        Input("btn_download_objetivos", "n_clicks"),
        State("f_year",  "value"),
        State("f_month", "value"),
        prevent_initial_call=True,
    )
    def download_objetivos_excel(n_clicks, year, month):
        df_corona    = build_corona_ranking(CACHE.ven, year, month)
        df_pier_roll = build_pier_roll_ranking(CACHE.ven, year, month)

        if not isinstance(df_corona, pd.DataFrame):
            df_corona = pd.DataFrame()
        if not isinstance(df_pier_roll, pd.DataFrame):
            df_pier_roll = pd.DataFrame()

        output = BytesIO()
        with pd.ExcelWriter(output, engine="openpyxl") as writer:
            sheet_name = "Objetivos"
            # Escribimos una hoja vacía primero para poder ubicar los bloques a mano
            pd.DataFrame().to_excel(writer, sheet_name=sheet_name, index=False)
            ws = writer.book[sheet_name]

            row = 1  # openpyxl es 1-indexado

            # ── Bloque Corona ────────────────────────────────────
            ws.cell(row=row, column=1, value="OBJETIVO CORONA — Cumplimiento por Vendedor")
            row += 2
            if not df_corona.empty:
                df_corona.to_excel(writer, sheet_name=sheet_name, index=False, startrow=row - 1)
                row += len(df_corona) + 1  # +1 por la fila de encabezados
            else:
                ws.cell(row=row, column=1, value="Sin datos para el período seleccionado.")
                row += 1

            row += 2  # espacio en blanco entre tablas

            # ── Bloque Pier & Roll ───────────────────────────────
            ws.cell(row=row, column=1, value="OBJETIVO PIER & ROLL — Cumplimiento por Vendedor (20 blisters/mes, sin bonificado 100%)")
            row += 2
            if not df_pier_roll.empty:
                df_pier_roll.to_excel(writer, sheet_name=sheet_name, index=False, startrow=row - 1)
                row += len(df_pier_roll) + 1
            else:
                ws.cell(row=row, column=1, value="Sin datos para el período seleccionado.")
                row += 1

            # Autoajustar ancho de columnas
            for col_cells in ws.columns:
                max_len = max((len(str(c.value or "")) for c in col_cells), default=0)
                ws.column_dimensions[col_cells[0].column_letter].width = max_len + 2

        output.seek(0)
        parts = ["objetivos_corona_pier_roll"]
        if year:  parts.append(str(year))
        if month: parts.append(f"{int(month):02d}")
        return dcc.send_bytes(output.getvalue(), "_".join(parts) + ".xlsx")