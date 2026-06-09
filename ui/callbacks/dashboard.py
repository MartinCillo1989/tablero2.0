import re
from io import BytesIO

import pandas as pd
import plotly.express as px
from dash import Input, Output, State, dcc

from config import FONT
from data.cache import CACHE
from logic.kpis import compute_kpis, build_jornada_df, build_ventas_semanales_df
from logic.mix import compute_mix_progress, render_mix_objective_box
from utils.helpers import filter_inactivos_por_vendedor
from utils.helpers import apply_filters, get_previous_year_month
from ui.styles import PLOTLY_LAYOUT, AXIS_STYLE, DEFAULT_MARGIN, ACCENT_SEQUENCE
from ui.components import kpi_card


def register(app):

    # ── Tabs según rol ───────────────────────────────────────
    @app.callback(
        Output("tabs_container", "children"),
        Input("btn_reload", "n_clicks"),
    )
    def build_tabs(n):
        from flask import request as flask_request
        from ui.layout import _tab_dashboard, _tab_rankings, _tab_resumen
        auth = flask_request.authorization
        usuario = auth.username.lower() if auth else ""
        es_super = usuario in app.SUPERVISORES

        if es_super:
            tabs = [_tab_dashboard(), _tab_rankings(), _tab_resumen()]
            default = "tab_dashboard"
        else:
            tabs = [_tab_resumen()]
            default = "tab_resumen"

        return dcc.Tabs(
            id="main_tabs", value=default,
            colors={"border": "rgba(255,255,255,0.07)", "primary": "#3b82f6", "background": "#0d1117"},
            children=tabs,
        )


    @app.callback(
        Output("f_year", "options"),
        Output("f_year", "value"),
        Output("reload_status", "children"),
        Input("btn_reload", "n_clicks"),
    )
    def init_year(n):
        if n and n > 0:
            CACHE.reload()
        opts = [{"label": str(y), "value": int(y)} for y in CACHE.years]
        val  = CACHE.years[-1] if CACHE.years else None
        ts   = CACHE.loaded_at.strftime("%H:%M:%S") if CACHE.loaded_at else ""
        return opts, val, f"Cargado a las {ts}" if ts else ""

    # ── Semanas + Vendedores ─────────────────────────────────────
    @app.callback(
        Output("f_week", "options"),
        Output("f_week", "value"),
        Output("f_vend", "options"),
        Input("f_year",  "value"),
        Input("f_month", "value"),
    )
    def update_week_and_vendor(year, month):
        if year is None:
            return [], None, []
        from datetime import datetime
        weeks_set = set()
        for df in [CACHE.vis, CACHE.ven]:
            if isinstance(df, pd.DataFrame) and not df.empty and "week_label" in df.columns:
                tmp = df
                if "year"  in tmp.columns: tmp = tmp[tmp["year"]  == year]  if year  is not None else tmp
                if "month" in tmp.columns: tmp = tmp[tmp["month"] == month] if month is not None else tmp
                weeks_set |= set(tmp["week_label"].dropna().unique())

        weeks = sorted([w for w in weeks_set if str(w).strip() != ""],
                       key=lambda lbl: _week_dt(lbl))
        week_opts = [{"label": w, "value": w} for w in weeks]

        # Vendedores
        vset = set()
        for df in [CACHE.vis, CACHE.ven]:
            if isinstance(df, pd.DataFrame) and not df.empty and "vendedor" in df.columns:
                tmp = df
                if year  is not None and "year"  in tmp.columns: tmp = tmp[tmp["year"]  == year]
                if month is not None and "month" in tmp.columns: tmp = tmp[tmp["month"] == month]
                vset |= set(tmp["vendedor"].dropna().unique())
        v = sorted([x for x in vset if str(x).strip() != ""])
        vend_opts = [{"label": x, "value": x} for x in v]

        return week_opts, None, vend_opts

    # ── Dashboard principal ──────────────────────────────────────
    @app.callback(
        Output("kpis",           "children"),
        Output("motivos_bar",    "figure"),
        Output("mix_bar",        "figure"),
        Output("mix_obj_box",    "children"),
        Output("ventas_sem_tbl", "data"),
        Output("ventas_sem_tbl", "columns"),
        Output("jornada_tbl",    "data"),
        Output("jornada_tbl",    "columns"),
        Output("inactivos_tbl",  "data"),
        Output("inactivos_tbl",  "columns"),
        Input("btn_reload", "n_clicks"),
        Input("f_year",     "value"),
        Input("f_month",    "value"),
        Input("f_week",     "value"),
        Input("f_vend",     "value"),
    )
    def refresh(n_clicks, year, month, week, vend):
        empty_fig = px.bar(pd.DataFrame({"x": [], "y": []}), x="x", y="y")
        empty_fig.update_layout(**PLOTLY_LAYOUT, margin=DEFAULT_MARGIN, xaxis=AXIS_STYLE, yaxis=AXIS_STYLE)

        vis_f = apply_filters(CACHE.vis, year, month, week, vend)
        ven_f = apply_filters(CACHE.ven, year, month, week, vend)

        vis_f = vis_f if isinstance(vis_f, pd.DataFrame) else pd.DataFrame()
        ven_f = ven_f if isinstance(ven_f, pd.DataFrame) else pd.DataFrame()

        k     = compute_kpis(vis_f, ven_f)
        kpis  = [
            kpi_card("Visitas",      k["Visitas"]),
            kpi_card("Ventas",       k["Ventas"]),
            kpi_card("No Ventas",    k["No ventas"]),
            kpi_card("Sin Motivo",   k["No ventas sin motivo"]),
            kpi_card("No Visitados", k["No visitados"]),
            kpi_card("Cantidades",   f"{k['Cantidades']:,.2f}"),
        ]

        # ── Gráfico motivos ──────────────────────────────────────
        fig_motivos = empty_fig
        if len(vis_f) > 0 and "Hora motivo" in vis_f.columns and "Motivo" in vis_f.columns:
            mdf = vis_f[vis_f["Hora motivo"].notna()].copy()
            mdf["Motivo"] = mdf["Motivo"].astype(str).str.strip().replace({"": "SIN MOTIVO", "nan": "SIN MOTIVO", "None": "SIN MOTIVO"})
            if len(mdf) > 0:
                motivos = mdf.groupby("Motivo", as_index=False).size().sort_values("size", ascending=False)
                fig_motivos = px.bar(motivos, x="Motivo", y="size", text="size", color_discrete_sequence=["#3b82f6"])
                fig_motivos.update_traces(textposition="outside", cliponaxis=False,
                                          textfont=dict(color="#e2e8f0", size=13, family=FONT),
                                          marker=dict(color="#3b82f6", opacity=0.85, line=dict(width=0)))
                ymax = motivos["size"].max() * 1.18
                fig_motivos.update_layout(**PLOTLY_LAYOUT, margin=DEFAULT_MARGIN,
                                          xaxis=AXIS_STYLE, yaxis={**AXIS_STYLE, "range": [0, ymax], "automargin": True},
                                          uniformtext_minsize=11, uniformtext_mode="hide", bargap=0.35)

        # ── Gráfico mix ──────────────────────────────────────────
        fig_mix = empty_fig
        mix_obj_children = render_mix_objective_box(compute_mix_progress(pd.DataFrame()))

        if len(ven_f) > 0 and "articulo" in ven_f.columns:
            art_u        = ven_f["articulo"].astype(str).str.upper()
            CIG_IDS      = {1003, 1004, 1005, 1006, 1028}
            marca_series = ven_f.get("marca_id", pd.Series([pd.NA] * len(ven_f)))
            mask_cig     = pd.to_numeric(marca_series, errors="coerce").isin(CIG_IDS)
            mask_mix     = art_u.str.contains(r"\(\s*001002\s*\)", regex=True, na=False)
            cig = ven_f[mask_cig | mask_mix].copy()
            if len(cig) > 0:
                rep = (cig.groupby("articulo", as_index=False)["Cantidades Totales"]
                       .sum().sort_values("Cantidades Totales", ascending=True).tail(15))
                bar_colors = [ACCENT_SEQUENCE[i % len(ACCENT_SEQUENCE)] for i in range(len(rep))]
                fig_mix = px.bar(rep, x="Cantidades Totales", y="articulo", orientation="h", text="Cantidades Totales")
                fig_mix.update_traces(textposition="auto", cliponaxis=False, texttemplate="%{text:.2f}",
                                      textfont=dict(size=11, color="#e2e8f0", family=FONT),
                                      marker=dict(color=bar_colors, line=dict(width=0)))
                xmax = rep["Cantidades Totales"].max() * 1.15
                fig_mix.update_layout(**PLOTLY_LAYOUT, margin=dict(l=300, r=40, t=30, b=40),
                                      xaxis={**AXIS_STYLE, "range": [0, xmax], "title": "Cantidades Totales"},
                                      yaxis={**AXIS_STYLE, "title": "", "automargin": True,
                                             "tickfont": dict(size=11, family=FONT, color="#94a3b8")},
                                      height=400, bargap=0.25)

            vals      = compute_mix_progress(ven_f)
            prev_vals = None
            if month is not None and year is not None:
                prev_year, prev_month = get_previous_year_month(year, month)
                ven_prev  = apply_filters(CACHE.ven, prev_year, prev_month, None, vend)
                prev_vals = compute_mix_progress(ven_prev)
            mix_obj_children = render_mix_objective_box(vals, prev_vals)

        # ── Ventas semanales ─────────────────────────────────────
        ventas_sem_data, ventas_sem_cols = [], []
        ventas_sem = build_ventas_semanales_df(ven_f)
        if not ventas_sem.empty:
            show = ventas_sem.copy()
            show["Cantidades Totales"] = show["Cantidades Totales"].apply(lambda x: f"{float(x):,.2f}")
            show["Importe Final"]      = show["Importe Final"].apply(lambda x: f"$ {float(x):,.0f}".replace(",", "."))
            ventas_sem_data = show.to_dict("records")
            ventas_sem_cols = [{"name": c, "id": c} for c in show.columns]

        # ── Jornada (desde CACHE) ────────────────────────────────
        jornada_data, jornada_cols = [], []
        jornada = apply_filters(CACHE.jornada_all, year, month, week, vend)
        if not jornada.empty:
            JHDRS = {
                "vendedor": "Vendedor", "date": "Fecha", "dia": "Día",
                "primera_visita": "Primera Visita", "inicio_obj": "Inicio ≤ 9:30",
                "ultima_visita": "Última Visita", "hs_trab_hhmm": "Hs. Trabajadas",
                "ventas": "Ventas", "no_ventas": "No Ventas", "sin_motivo": "Sin Motivo",
            }
            SCOLS = ["vendedor", "date", "dia", "primera_visita", "inicio_obj",
                     "ultima_visita", "hs_trab_hhmm", "ventas", "no_ventas", "sin_motivo"]
            show  = [c for c in SCOLS if c in jornada.columns]
            jornada_data = jornada[show].to_dict("records")
            jornada_cols = [{"name": JHDRS.get(c, c), "id": c} for c in show]

        # ── Inactivos ────────────────────────────────────────────
        inactivos_data, inactivos_cols = [], []
        inactivos_f = filter_inactivos_por_vendedor(CACHE.inact, vend)
        if isinstance(inactivos_f, pd.DataFrame) and not inactivos_f.empty:
            orden = ["Cod. Vendedor", "Clientes en cartera", "Clientes con venta",
                     "Total inactivos", "% Inactivos", "Lunes", "Martes",
                     "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
            cols  = [c for c in orden if c in inactivos_f.columns]
            otros = [c for c in inactivos_f.columns if c not in cols]
            inactivos_f = inactivos_f[cols + otros]
            if "% Inactivos" in inactivos_f.columns:
                inactivos_f["% Inactivos"] = inactivos_f["% Inactivos"].apply(
                    lambda x: f"{float(x) * 100:.2f}%" if pd.notna(x) and str(x) != "" else ""
                )
            inactivos_data = inactivos_f.to_dict("records")
            inactivos_cols = [{"name": c, "id": c} for c in inactivos_f.columns]

        return (kpis, fig_motivos, fig_mix, mix_obj_children,
                ventas_sem_data, ventas_sem_cols, jornada_data, jornada_cols,
                inactivos_data, inactivos_cols)

    # ── Descarga Excel jornada ───────────────────────────────────
    @app.callback(
        Output("download_jornada_excel", "data"),
        Input("btn_download_jornada", "n_clicks"),
        State("f_year",  "value"),
        State("f_month", "value"),
        State("f_week",  "value"),
        State("f_vend",  "value"),
        prevent_initial_call=True,
    )
    def download_jornada_excel(n_clicks, year, month, week, vend):
        # Usa la jornada del CACHE filtrada, sin recalcular
        jornada = apply_filters(CACHE.jornada_all, year, month, week, vend)
        if jornada.empty:
            jornada = pd.DataFrame(columns=["Vendedor", "Fecha", "Día", "Primera visita",
                                             "Última visita", "Horas trabajadas", "Horas numéricas",
                                             "Ventas", "No ventas", "No ventas sin motivo"])
        else:
            jornada = jornada.rename(columns={
                "vendedor": "Vendedor", "date": "Fecha", "dia": "Día",
                "primera_visita": "Primera visita", "ultima_visita": "Última visita",
                "hs_trab_hhmm": "Horas trabajadas", "hs_trab": "Horas numéricas",
                "ventas": "Ventas", "no_ventas": "No ventas", "sin_motivo": "No ventas sin motivo",
            })
        output = BytesIO()
        with pd.ExcelWriter(output, engine="openpyxl") as writer:
            jornada.to_excel(writer, index=False, sheet_name="Jornada")
            ws = writer.book["Jornada"]
            for col_cells in ws.columns:
                max_len = max((len(str(c.value or "")) for c in col_cells), default=0)
                ws.column_dimensions[col_cells[0].column_letter].width = max_len + 2
        output.seek(0)
        parts = ["jornada"]
        if year:  parts.append(str(year))
        if month: parts.append(f"{int(month):02d}")
        if vend:  parts.append(re.sub(r"[^A-Z0-9]+", "_", str(vend).upper()).strip("_"))
        return dcc.send_bytes(output.getvalue(), "_".join(parts) + ".xlsx")


def _week_dt(label):
    from datetime import datetime
    try:
        return datetime.strptime(str(label).split(" - ")[0].strip(), "%d/%m/%Y")
    except Exception:
        from datetime import datetime
        return datetime(1900, 1, 1)