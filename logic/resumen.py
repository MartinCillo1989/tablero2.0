import re
from datetime import date, datetime

import pandas as pd
from dash import html

from config import FONT, LIMITE_INICIO_SEG
from utils.helpers import (
    apply_filters, hours_to_hhmm, monday_of, week_label, normalize_vendor,
    filter_inactivos_por_vendedor,
)
from logic.kpis import build_jornada_df


PLACEHOLDERS = {"", "NAN", "NONE", "<NA>", "SIN MOTIVO", "S/M", "SM", "N/A", "NA", "-", "--", "0", "NULL"}


# ======================================================
# INACTIVOS — comparativo
# ======================================================
def build_inactivos_comparativo(df_actual=None, df_anterior=None, vend=None) -> pd.DataFrame:
    # Si no se pasan, se obtienen desde el caller (no importamos CACHE aquí para evitar circular import)
    if df_actual is None or df_anterior is None:
        from data.cache import CACHE
        if df_actual  is None: df_actual  = CACHE.inact
        if df_anterior is None: df_anterior = CACHE.inact_ant

    df_a   = filter_inactivos_por_vendedor(df_actual,  vend)
    df_ant = filter_inactivos_por_vendedor(df_anterior, vend)
    if not isinstance(df_a, pd.DataFrame) or df_a.empty:
        return pd.DataFrame()

    result = df_a.copy()

    if isinstance(df_ant, pd.DataFrame) and not df_ant.empty and "Cod. Vendedor" in df_ant.columns:
        ant_map = {str(row.get("Cod. Vendedor", "")).zfill(2): row for _, row in df_ant.iterrows()}

        variaciones, inact_ant_list, pct_ant_list = [], [], []
        for _, row in result.iterrows():
            cod     = str(row.get("Cod. Vendedor", "")).zfill(2)
            ant_row = ant_map.get(cod)
            if ant_row is not None:
                try:
                    diff = float(row["Total inactivos"]) - float(ant_row["Total inactivos"])
                    variaciones.append(f"▲ +{int(diff)}" if diff > 0 else (f"▼ {int(diff)}" if diff < 0 else "→ 0"))
                    inact_ant_list.append(int(ant_row["Total inactivos"]))
                    pct_ant_list.append(ant_row.get("% Inactivos", ""))
                except Exception:
                    variaciones.append(""); inact_ant_list.append(""); pct_ant_list.append("")
            else:
                variaciones.append(""); inact_ant_list.append(""); pct_ant_list.append("")

        result["Inactivos mes ant."] = inact_ant_list
        result["Variación"]          = variaciones
        result["% Inact. ant."]      = pct_ant_list
    else:
        result["Inactivos mes ant."] = ""
        result["Variación"]          = ""
        result["% Inact. ant."]      = ""

    return result


# ======================================================
# RESUMEN POR VENDEDOR (vectorizado)
# ======================================================
def build_resumen_vendedores(
    vis_df: pd.DataFrame,
    ven_df: pd.DataFrame,
    inactivos_df: pd.DataFrame,
    inactivos_ant_df: pd.DataFrame,
    altas_count: dict,
    year,
    month,
    jornada_all=None,
) -> dict:
    vis_m = apply_filters(vis_df, year, month)
    ven_m = apply_filters(ven_df, year, month)
    if not isinstance(vis_m, pd.DataFrame) or vis_m.empty:
        return {}

    vis_m     = vis_m[vis_m["vendedor"].notna() & (vis_m["vendedor"] != "")].copy()
    vendedores = sorted(vis_m["vendedor"].unique())

    # ── KPIs de visitas vectorizados ─────────────────
    mot      = vis_m["Motivo"] if "Motivo" in vis_m.columns else pd.Series([pd.NA] * len(vis_m), index=vis_m.index)
    mot_str  = mot.astype(str).str.replace("\u00a0", " ", regex=False).str.strip().str.upper()
    sin_texto = mot.isna() | mot_str.isin(PLACEHOLDERS)

    hv_na   = vis_m["Hora visita"].isna() if "Hora visita" in vis_m.columns else pd.Series(True, index=vis_m.index)
    hven_na = vis_m["Hora venta"].isna()  if "Hora venta"  in vis_m.columns else pd.Series(True, index=vis_m.index)
    hmot_na = vis_m["Hora motivo"].isna() if "Hora motivo" in vis_m.columns else pd.Series(True, index=vis_m.index)

    vis_m["_venta"]       = ~hven_na
    vis_m["_no_venta"]    = ~hmot_na
    vis_m["_sin_motivo"]  = hven_na & hmot_na & sin_texto
    vis_m["_no_visit"]    = hv_na & hven_na & hmot_na & sin_texto

    kpi_vis = vis_m.groupby("vendedor", sort=False).agg(
        visitas     =("vendedor",    "count"),
        ventas      =("_venta",      "sum"),
        no_ventas   =("_no_venta",   "sum"),
        sin_motivo  =("_sin_motivo", "sum"),
        no_visitados=("_no_visit",   "sum"),
    )

    # ── KPIs de ventas vectorizados ──────────────────
    if isinstance(ven_m, pd.DataFrame) and not ven_m.empty and "vendedor" in ven_m.columns:
        ven_m2  = ven_m[ven_m["vendedor"].notna() & (ven_m["vendedor"] != "")]
        kpi_ven = ven_m2.groupby("vendedor", sort=False).agg(
            importe   =("Importes Finales",  "sum"),
            cantidades=("Cantidades Totales","sum"),
        )
    else:
        kpi_ven = pd.DataFrame(columns=["importe","cantidades"])

    # ── Jornada desde parámetro o CACHE ──────────────────
    if jornada_all is None:
        from data.cache import CACHE
        jornada_all = CACHE.jornada_all
    jornada_all = apply_filters(jornada_all, year, month)
    if not jornada_all.empty:
        jornada_all = jornada_all[jornada_all["vendedor"].isin(vendedores)].copy()
        jornada_all["_ok"] = (jornada_all["inicio_obj"] == "✅").astype(int)
        jorn_kpi = jornada_all.groupby("vendedor", sort=False).agg(
            dias_trabajados=("date",    "count"),
            hs_prom        =("hs_trab", "mean"),
            ok_inicio      =("_ok",     "sum"),
        )
    else:
        jornada_all = pd.DataFrame()
        jorn_kpi    = pd.DataFrame(columns=["dias_trabajados","hs_prom","ok_inicio"])

    # ── Mix vectorizado ───────────────────────────────
    mix_result = {}
    if isinstance(ven_m, pd.DataFrame) and not ven_m.empty and "articulo" in ven_m.columns:
        art_u    = ven_m["articulo"].astype(str).str.upper()
        m_pier   = art_u.str.contains(r"\(\s*010005\s*\)", regex=True, na=False) | art_u.str.contains("PIER ORIGINAL", na=False)
        m_livr   = art_u.str.contains(r"\(\s*010001\s*\)", regex=True, na=False) | (art_u.str.contains("LIVERPOOL", na=False) & art_u.str.contains("RED", na=False))
        m_corona = art_u.str.contains(r"\(\s*010008\s*\)", regex=True, na=False) | art_u.str.contains("CORONA", na=False)
        tmp_mix  = ven_m[ven_m["vendedor"].notna() & (ven_m["vendedor"] != "")].copy()
        tmp_mix["_pier"]   = tmp_mix["Cantidades Totales"].where(m_pier,   0)
        tmp_mix["_livr"]   = tmp_mix["Cantidades Totales"].where(m_livr,   0)
        tmp_mix["_corona"] = tmp_mix["Cantidades Totales"].where(m_corona, 0)
        mix_agg = tmp_mix.groupby("vendedor", sort=False).agg(
            pier  =("_pier",   "sum"),
            livr  =("_livr",   "sum"),
            corona=("_corona", "sum"),
        )
        mix_agg["base"]       = mix_agg["pier"] + mix_agg["livr"]
        mix_agg["obj_corona"] = mix_agg["base"] * 0.20
        mix_agg["pct_corona"] = mix_agg.apply(
            lambda r: (r["corona"] / r["obj_corona"] * 100) if r["obj_corona"] > 0 else 0.0, axis=1
        )
        mix_result = mix_agg.to_dict("index")

    # ── Inactivos ─────────────────────────────────────
    def _inact_map(df):
        m = {}
        if not isinstance(df, pd.DataFrame) or df.empty or "Cod. Vendedor" not in df.columns:
            return m
        for _, row in df.iterrows():
            cod = str(row["Cod. Vendedor"]).zfill(2)
            m[cod] = row
        return m
    inact_map     = _inact_map(inactivos_df)
    inact_ant_map = _inact_map(inactivos_ant_df)

    # ── Semanas vectorizadas ─────────────────────────
    semanas_por_vend = {v: [] for v in vendedores}

    if not jornada_all.empty and "week_label" in jornada_all.columns:
        jorn_sem = jornada_all.groupby(["vendedor","week_label"], sort=False).agg(
            dias  =("date",    "count"),
            hs_med=("hs_trab", "mean"),
            ok    =("_ok",     "sum"),
        ).reset_index()

        vis_sem = pd.DataFrame()
        if "week_label" in vis_m.columns:
            vis_sem = vis_m.groupby(["vendedor","week_label"], sort=False).agg(
                visitas    =("vendedor",    "count"),
                ventas     =("_venta",      "sum"),
                no_ventas  =("_no_venta",   "sum"),
                sin_motivo =("_sin_motivo", "sum"),
            ).reset_index()

        ven_sem = pd.DataFrame()
        if isinstance(ven_m, pd.DataFrame) and not ven_m.empty and "week_label" in ven_m.columns:
            ven_sem = ven_m[ven_m["vendedor"].notna() & (ven_m["vendedor"] != "")].groupby(
                ["vendedor","week_label"], sort=False
            ).agg(importe=("Importes Finales","sum"), cantidades=("Cantidades Totales","sum")).reset_index()

        sem_merged = jorn_sem.copy()
        if not vis_sem.empty:
            sem_merged = sem_merged.merge(vis_sem, on=["vendedor","week_label"], how="left")
        if not ven_sem.empty:
            sem_merged = sem_merged.merge(ven_sem, on=["vendedor","week_label"], how="left")
        for col in ["visitas","ventas","no_ventas","sin_motivo","importe","cantidades"]:
            if col not in sem_merged.columns:
                sem_merged[col] = 0
        sem_merged = sem_merged.fillna(0)

        def _week_dt(lbl):
            try:
                return datetime.strptime(str(lbl).split(" - ")[0].strip(), "%d/%m/%Y")
            except Exception:
                return datetime(1900, 1, 1)

        for vend in vendedores:
            vrows = sem_merged[sem_merged["vendedor"] == vend].copy()
            vrows = vrows.sort_values("week_label", key=lambda s: s.map(_week_dt))
            for _, sr in vrows.iterrows():
                semanas_por_vend[vend].append({
                    "label":      sr["week_label"],
                    "visitas":    int(sr["visitas"]),
                    "ventas":     int(sr["ventas"]),
                    "no_ventas":  int(sr["no_ventas"]),
                    "sin_motivo": int(sr["sin_motivo"]),
                    "importe":    float(sr["importe"]),
                    "cantidades": float(sr["cantidades"]),
                    "hs_prom":    hours_to_hhmm(sr["hs_med"]) if pd.notna(sr["hs_med"]) and sr["hs_med"] > 0 else "—",
                    "inicio_ok":  int(sr["ok"]),
                    "dias":       int(sr["dias"]),
                })

    # ── Ensamblar resultado ───────────────────────────
    result = {}
    for vend in vendedores:
        kv  = kpi_vis.loc[vend]  if vend in kpi_vis.index  else None
        kve = kpi_ven.loc[vend]  if vend in kpi_ven.index  else None
        jk  = jorn_kpi.loc[vend] if vend in jorn_kpi.index else None
        mx  = mix_result.get(vend, {})

        visitas      = int(kv["visitas"])       if kv is not None else 0
        ventas       = int(kv["ventas"])        if kv is not None else 0
        no_ventas    = int(kv["no_ventas"])     if kv is not None else 0
        sin_motivo   = int(kv["sin_motivo"])    if kv is not None else 0
        no_visitados = int(kv["no_visitados"])  if kv is not None else 0
        importe      = float(kve["importe"])    if kve is not None else 0.0
        cantidades   = float(kve["cantidades"]) if kve is not None else 0.0

        dias_trabajados = int(jk["dias_trabajados"])                              if jk is not None else 0
        hs_prom_val     = float(jk["hs_prom"]) if jk is not None and pd.notna(jk["hs_prom"]) else None
        hs_prom_str     = hours_to_hhmm(hs_prom_val)                              if hs_prom_val is not None else "—"
        ok_inicio       = int(jk["ok_inicio"])                                    if jk is not None else 0
        pct_inicio      = round(ok_inicio / dias_trabajados * 100)               if dias_trabajados > 0 else 0

        pct_corona = float(mx.get("pct_corona", 0.0))
        corona     = float(mx.get("corona",     0.0))
        obj_corona = float(mx.get("obj_corona", 0.0))
        mix_ok     = corona >= obj_corona - 1e-9

        nums     = re.findall(r"\d+", str(vend))
        vend_cod = f"{int(nums[0]):02d}" if nums else "?"
        altas    = altas_count.get(vend_cod, 0)

        pct_inact, total_inact, inact_var = "—", "—", ""
        ir = inact_map.get(vend_cod)
        if ir is not None:
            try:
                pct_inact   = f"{float(ir['% Inactivos']) * 100:.1f}%"
                total_inact = int(ir["Total inactivos"])
            except Exception:
                pass
            iar = inact_ant_map.get(vend_cod)
            if iar is not None:
                try:
                    diff      = float(ir["Total inactivos"]) - float(iar["Total inactivos"])
                    inact_var = f"▲ +{int(diff)}" if diff > 0 else (f"▼ {int(diff)}" if diff < 0 else "→ 0")
                except Exception:
                    pass

        result[vend] = {
            "visitas": visitas, "ventas": ventas, "no_ventas": no_ventas,
            "sin_motivo": sin_motivo, "no_visitados": no_visitados,
            "importe": importe, "cantidades": cantidades,
            "dias_trabajados": dias_trabajados, "hs_prom": hs_prom_str,
            "pct_inicio": pct_inicio, "ok_inicio": ok_inicio, "total_dias": dias_trabajados,
            "pct_inactivos": pct_inact, "total_inactivos": total_inact, "inact_var": inact_var,
            "mix_pct_corona": pct_corona, "mix_ok_corona": mix_ok,
            "altas": altas,
            "semanas": semanas_por_vend.get(vend, []),
        }
    return result


# ======================================================
# RENDER CARDS
# ======================================================
def render_resumen_cards(resumen: dict) -> list:
    if not resumen:
        return [html.Div(
            "No hay datos para el período seleccionado.",
            style={"color": "#64748b", "fontFamily": FONT, "padding": "40px",
                   "textAlign": "center", "fontSize": "14px"},
        )]

    cards = []
    for vend, m in resumen.items():

        def stat_row(label, value, color=None, bold=False):
            return html.Div([
                html.Span(label, style={"color": "#64748b", "fontSize": "12px", "fontFamily": FONT}),
                html.Span(str(value), style={
                    "fontWeight": "700" if bold else "500",
                    "fontSize": "13px",
                    "color": color or "#e2e8f0",
                    "fontFamily": FONT,
                }),
            ], style={"display": "flex", "justifyContent": "space-between",
                      "padding": "5px 0", "borderBottom": "1px solid rgba(255,255,255,0.04)"})

        pct_i        = m["pct_inicio"]
        inicio_color = "#4ade80" if pct_i >= 80 else "#f59e0b" if pct_i >= 50 else "#f87171"

        inact_color = "#e2e8f0"
        try:
            pct_n = float(str(m["pct_inactivos"]).replace("%", ""))
            inact_color = "#4ade80" if pct_n < 20 else "#f59e0b" if pct_n < 35 else "#f87171"
        except Exception:
            pass

        var_col   = "#f87171" if "▲" in str(m["inact_var"]) else "#4ade80" if "▼" in str(m["inact_var"]) else "#94a3b8"
        mix_color = "#4ade80" if m["mix_ok_corona"] else "#f87171"

        sem_rows = []
        for s in m["semanas"]:
            lbl = s["label"].split(" - ")[0] if " - " in s["label"] else s["label"]
            sem_rows.append(html.Div([
                html.Div(f"Sem. {lbl}", style={"fontSize": "10px", "color": "#475569",
                                               "fontFamily": FONT, "fontWeight": "600", "marginBottom": "4px"}),
                html.Div([
                    html.Div([html.Div(str(s["visitas"]),              style={"fontSize": "15px", "fontWeight": "700", "color": "#e2e8f0", "fontFamily": FONT}),
                              html.Div("visitas",                       style={"fontSize": "9px",  "color": "#64748b",  "fontFamily": FONT})], style={"textAlign": "center"}),
                    html.Div([html.Div(str(s["ventas"]),               style={"fontSize": "15px", "fontWeight": "700", "color": "#22c55e", "fontFamily": FONT}),
                              html.Div("ventas",                        style={"fontSize": "9px",  "color": "#64748b",  "fontFamily": FONT})], style={"textAlign": "center"}),
                    html.Div([html.Div(str(s["no_ventas"]),            style={"fontSize": "15px", "fontWeight": "700", "color": "#f87171", "fontFamily": FONT}),
                              html.Div("no ventas",                     style={"fontSize": "9px",  "color": "#64748b",  "fontFamily": FONT})], style={"textAlign": "center"}),
                    html.Div([html.Div(f"${s['importe']:,.0f}",        style={"fontSize": "12px", "fontWeight": "700", "color": "#a78bfa", "fontFamily": FONT}),
                              html.Div("importe",                       style={"fontSize": "9px",  "color": "#64748b",  "fontFamily": FONT})], style={"textAlign": "center"}),
                    html.Div([html.Div(s["hs_prom"],                   style={"fontSize": "12px", "fontWeight": "700", "color": "#38bdf8", "fontFamily": FONT}),
                              html.Div("hs prom",                       style={"fontSize": "9px",  "color": "#64748b",  "fontFamily": FONT})], style={"textAlign": "center"}),
                    html.Div([html.Div(f"{s['inicio_ok']}/{s['dias']}", style={"fontSize": "12px", "fontWeight": "700", "color": "#4ade80", "fontFamily": FONT}),
                              html.Div("a tiempo",                      style={"fontSize": "9px",  "color": "#64748b",  "fontFamily": FONT})], style={"textAlign": "center"}),
                ], style={"display": "grid", "gridTemplateColumns": "repeat(6, 1fr)", "gap": "8px",
                          "padding": "8px", "backgroundColor": "rgba(255,255,255,0.02)", "borderRadius": "8px"}),
            ], style={"backgroundColor": "#0d1117", "borderRadius": "10px", "padding": "10px 12px",
                      "marginBottom": "8px", "border": "1px solid rgba(255,255,255,0.05)"}))

        card = html.Div([
            html.Div([
                html.Div([
                    html.Div("VENDEDOR", style={"fontSize": "10px", "fontWeight": "700", "letterSpacing": "0.12em",
                                                "color": "#3b82f6", "marginBottom": "2px", "fontFamily": FONT}),
                    html.Div(vend, style={"fontSize": "18px", "fontWeight": "800", "color": "#e2e8f0", "fontFamily": FONT}),
                ]),
                html.Div([
                    html.Div(f"${m['importe']:,.0f}", style={"fontSize": "20px", "fontWeight": "800",
                                                             "color": "#22c55e", "fontFamily": FONT, "textAlign": "right"}),
                    html.Div("importe total", style={"fontSize": "10px", "color": "#64748b",
                                                     "fontFamily": FONT, "textAlign": "right"}),
                ]),
            ], style={"display": "flex", "justifyContent": "space-between",
                      "alignItems": "flex-start", "marginBottom": "16px"}),

            html.Div([
                html.Div([html.Div(str(m["visitas"]),        style={"fontSize": "22px", "fontWeight": "800", "color": "#e2e8f0", "fontFamily": FONT, "lineHeight": "1"}),
                          html.Div("visitas",                 style={"fontSize": "10px", "color": "#64748b", "fontFamily": FONT})],
                         style={"textAlign": "center", "padding": "10px", "backgroundColor": "rgba(59,130,246,0.08)", "borderRadius": "10px"}),
                html.Div([html.Div(str(m["ventas"]),         style={"fontSize": "22px", "fontWeight": "800", "color": "#22c55e", "fontFamily": FONT, "lineHeight": "1"}),
                          html.Div("ventas",                  style={"fontSize": "10px", "color": "#64748b", "fontFamily": FONT})],
                         style={"textAlign": "center", "padding": "10px", "backgroundColor": "rgba(34,197,94,0.08)", "borderRadius": "10px"}),
                html.Div([html.Div(str(m["no_ventas"]),      style={"fontSize": "22px", "fontWeight": "800", "color": "#f87171", "fontFamily": FONT, "lineHeight": "1"}),
                          html.Div("no ventas",               style={"fontSize": "10px", "color": "#64748b", "fontFamily": FONT})],
                         style={"textAlign": "center", "padding": "10px", "backgroundColor": "rgba(248,113,113,0.08)", "borderRadius": "10px"}),
                html.Div([html.Div(str(m["sin_motivo"]),     style={"fontSize": "22px", "fontWeight": "800", "color": "#fbbf24", "fontFamily": FONT, "lineHeight": "1"}),
                          html.Div("sin motivo",              style={"fontSize": "10px", "color": "#64748b", "fontFamily": FONT})],
                         style={"textAlign": "center", "padding": "10px", "backgroundColor": "rgba(251,191,36,0.08)", "borderRadius": "10px"}),
                html.Div([html.Div(f"{m['cantidades']:,.1f}", style={"fontSize": "18px", "fontWeight": "800", "color": "#a78bfa", "fontFamily": FONT, "lineHeight": "1"}),
                          html.Div("cantidades",               style={"fontSize": "10px", "color": "#64748b", "fontFamily": FONT})],
                         style={"textAlign": "center", "padding": "10px", "backgroundColor": "rgba(167,139,250,0.08)", "borderRadius": "10px"}),
                html.Div([html.Div(str(m["altas"]),          style={"fontSize": "22px", "fontWeight": "800", "color": "#38bdf8", "fontFamily": FONT, "lineHeight": "1"}),
                          html.Div("altas",                   style={"fontSize": "10px", "color": "#64748b", "fontFamily": FONT})],
                         style={"textAlign": "center", "padding": "10px", "backgroundColor": "rgba(56,189,248,0.08)", "borderRadius": "10px"}),
            ], style={"display": "grid", "gridTemplateColumns": "repeat(6, 1fr)", "gap": "8px", "marginBottom": "16px"}),

            html.Div([
                html.Div([
                    html.Div("JORNADA", style={"fontSize": "10px", "fontWeight": "700", "letterSpacing": "0.1em",
                                               "color": "#7ea3c4", "marginBottom": "8px", "fontFamily": FONT}),
                    stat_row("Días trabajados",  m["dias_trabajados"]),
                    stat_row("Hs. promedio/día", m["hs_prom"], color="#38bdf8"),
                    stat_row("Inicio a tiempo",  f"{m['ok_inicio']}/{m['total_dias']} ({pct_i}%)", color=inicio_color, bold=True),
                ], style={"flex": "1", "backgroundColor": "rgba(255,255,255,0.02)", "borderRadius": "10px",
                          "padding": "12px", "border": "1px solid rgba(255,255,255,0.05)"}),
                html.Div([
                    html.Div("INACTIVOS", style={"fontSize": "10px", "fontWeight": "700", "letterSpacing": "0.1em",
                                                 "color": "#7ea3c4", "marginBottom": "8px", "fontFamily": FONT}),
                    stat_row("Total inactivos", m["total_inactivos"], color=inact_color, bold=True),
                    stat_row("% Inactividad",   m["pct_inactivos"],   color=inact_color),
                    stat_row("Vs mes anterior", m["inact_var"] if m["inact_var"] else "—", color=var_col, bold=True),
                ], style={"flex": "1", "backgroundColor": "rgba(255,255,255,0.02)", "borderRadius": "10px",
                          "padding": "12px", "border": "1px solid rgba(255,255,255,0.05)"}),
                html.Div([
                    html.Div("MIX CORONA", style={"fontSize": "10px", "fontWeight": "700", "letterSpacing": "0.1em",
                                                  "color": "#7ea3c4", "marginBottom": "8px", "fontFamily": FONT}),
                    stat_row("% objetivo corona", f"{m['mix_pct_corona']:.0f}%", color=mix_color, bold=True),
                    html.Div("✅ Objetivo cumplido" if m["mix_ok_corona"] else "❌ Objetivo no cumplido",
                             style={"marginTop": "8px", "fontSize": "12px", "fontWeight": "700",
                                    "color": mix_color, "fontFamily": FONT}),
                ], style={"flex": "1", "backgroundColor": "rgba(255,255,255,0.02)", "borderRadius": "10px",
                          "padding": "12px", "border": "1px solid rgba(255,255,255,0.05)"}),
            ], style={"display": "flex", "gap": "10px", "marginBottom": "16px"}),

            html.Div(
                [html.Div("DESGLOSE POR SEMANA", style={"fontSize": "10px", "fontWeight": "700", "letterSpacing": "0.1em",
                                                         "color": "#7ea3c4", "marginBottom": "10px", "fontFamily": FONT})]
                + (sem_rows if sem_rows else [html.Div("Sin datos semanales",
                                                       style={"color": "#475569", "fontSize": "12px", "fontFamily": FONT})])
            ),
        ], style={
            "backgroundColor": "#161b27",
            "border": "1px solid rgba(255,255,255,0.07)",
            "borderRadius": "18px",
            "padding": "22px 24px",
            "boxShadow": "0 8px 32px rgba(0,0,0,0.45)",
            "marginBottom": "20px",
        })
        cards.append(card)

    return cards

    if not resumen:
        return [html.Div(
            "No hay datos para el período seleccionado.",
            style={"color": "#64748b", "fontFamily": FONT, "padding": "40px",
                   "textAlign": "center", "fontSize": "14px"},
        )]

    cards = []
    for vend, m in resumen.items():

        def stat_row(label, value, color=None, bold=False):
            return html.Div([
                html.Span(label, style={"color": "#64748b", "fontSize": "12px", "fontFamily": FONT}),
                html.Span(str(value), style={
                    "fontWeight": "700" if bold else "500",
                    "fontSize": "13px",
                    "color": color or "#e2e8f0",
                    "fontFamily": FONT,
                }),
            ], style={"display": "flex", "justifyContent": "space-between",
                      "padding": "5px 0", "borderBottom": "1px solid rgba(255,255,255,0.04)"})

        pct_i        = m["pct_inicio"]
        inicio_color = "#4ade80" if pct_i >= 80 else "#f59e0b" if pct_i >= 50 else "#f87171"

        inact_color = "#e2e8f0"
        try:
            pct_n = float(str(m["pct_inactivos"]).replace("%", ""))
            inact_color = "#4ade80" if pct_n < 20 else "#f59e0b" if pct_n < 35 else "#f87171"
        except Exception:
            pass

        var_col   = "#f87171" if "▲" in str(m["inact_var"]) else "#4ade80" if "▼" in str(m["inact_var"]) else "#94a3b8"
        mix_color = "#4ade80" if m["mix_ok_corona"] else "#f87171"

        # ── Semanas ──────────────────────────────────────
        sem_rows = []
        for s in m["semanas"]:
            lbl = s["label"].split(" - ")[0] if " - " in s["label"] else s["label"]
            sem_rows.append(html.Div([
                html.Div(f"Sem. {lbl}", style={"fontSize": "10px", "color": "#475569",
                                               "fontFamily": FONT, "fontWeight": "600", "marginBottom": "4px"}),
                html.Div([
                    html.Div([html.Div(str(s["visitas"]),          style={"fontSize": "15px", "fontWeight": "700", "color": "#e2e8f0", "fontFamily": FONT}),
                              html.Div("visitas",                   style={"fontSize": "9px",  "color": "#64748b",  "fontFamily": FONT})], style={"textAlign": "center"}),
                    html.Div([html.Div(str(s["ventas"]),            style={"fontSize": "15px", "fontWeight": "700", "color": "#22c55e", "fontFamily": FONT}),
                              html.Div("ventas",                    style={"fontSize": "9px",  "color": "#64748b",  "fontFamily": FONT})], style={"textAlign": "center"}),
                    html.Div([html.Div(str(s["no_ventas"]),         style={"fontSize": "15px", "fontWeight": "700", "color": "#f87171", "fontFamily": FONT}),
                              html.Div("no ventas",                 style={"fontSize": "9px",  "color": "#64748b",  "fontFamily": FONT})], style={"textAlign": "center"}),
                    html.Div([html.Div(f"${s['importe']:,.0f}",     style={"fontSize": "12px", "fontWeight": "700", "color": "#a78bfa", "fontFamily": FONT}),
                              html.Div("importe",                   style={"fontSize": "9px",  "color": "#64748b",  "fontFamily": FONT})], style={"textAlign": "center"}),
                    html.Div([html.Div(s["hs_prom"],                style={"fontSize": "12px", "fontWeight": "700", "color": "#38bdf8", "fontFamily": FONT}),
                              html.Div("hs prom",                   style={"fontSize": "9px",  "color": "#64748b",  "fontFamily": FONT})], style={"textAlign": "center"}),
                    html.Div([html.Div(f"{s['inicio_ok']}/{s['dias']}", style={"fontSize": "12px", "fontWeight": "700", "color": "#4ade80", "fontFamily": FONT}),
                              html.Div("a tiempo",                  style={"fontSize": "9px",  "color": "#64748b",  "fontFamily": FONT})], style={"textAlign": "center"}),
                ], style={"display": "grid", "gridTemplateColumns": "repeat(6, 1fr)", "gap": "8px",
                          "padding": "8px", "backgroundColor": "rgba(255,255,255,0.02)", "borderRadius": "8px"}),
            ], style={"backgroundColor": "#0d1117", "borderRadius": "10px", "padding": "10px 12px",
                      "marginBottom": "8px", "border": "1px solid rgba(255,255,255,0.05)"}))

        # ── Header siempre visible ────────────────────────
        header = html.Div([
            html.Div([
                html.Div("VENDEDOR", style={"fontSize": "10px", "fontWeight": "700", "letterSpacing": "0.12em",
                                            "color": "#3b82f6", "marginBottom": "2px", "fontFamily": FONT}),
                html.Div(vend, style={"fontSize": "18px", "fontWeight": "800", "color": "#e2e8f0", "fontFamily": FONT}),
            ]),
            # Mini KPIs en el header (siempre visibles)
            html.Div([
                html.Div([html.Div(str(m["visitas"]),  style={"fontSize": "16px", "fontWeight": "800", "color": "#e2e8f0", "fontFamily": FONT, "lineHeight": "1"}),
                          html.Div("visitas",           style={"fontSize": "9px",  "color": "#64748b", "fontFamily": FONT})],
                         style={"textAlign": "center", "padding": "6px 10px", "backgroundColor": "rgba(59,130,246,0.08)", "borderRadius": "8px"}),
                html.Div([html.Div(str(m["ventas"]),   style={"fontSize": "16px", "fontWeight": "800", "color": "#22c55e", "fontFamily": FONT, "lineHeight": "1"}),
                          html.Div("ventas",            style={"fontSize": "9px",  "color": "#64748b", "fontFamily": FONT})],
                         style={"textAlign": "center", "padding": "6px 10px", "backgroundColor": "rgba(34,197,94,0.08)", "borderRadius": "8px"}),
                html.Div([html.Div(str(m["no_ventas"]), style={"fontSize": "16px", "fontWeight": "800", "color": "#f87171", "fontFamily": FONT, "lineHeight": "1"}),
                          html.Div("no ventas",          style={"fontSize": "9px",  "color": "#64748b", "fontFamily": FONT})],
                         style={"textAlign": "center", "padding": "6px 10px", "backgroundColor": "rgba(248,113,113,0.08)", "borderRadius": "8px"}),
                html.Div([html.Div(f"${m['importe']:,.0f}", style={"fontSize": "14px", "fontWeight": "800", "color": "#22c55e", "fontFamily": FONT, "lineHeight": "1"}),
                          html.Div("importe",               style={"fontSize": "9px",  "color": "#64748b", "fontFamily": FONT})],
                         style={"textAlign": "center", "padding": "6px 10px", "backgroundColor": "rgba(34,197,94,0.06)", "borderRadius": "8px"}),
                html.Div(f"{mix_color[1:3]}{'✅' if m['mix_ok_corona'] else '❌'} corona",
                         style={"fontSize": "12px", "fontWeight": "700", "color": mix_color,
                                "padding": "6px 10px", "backgroundColor": "rgba(255,255,255,0.04)",
                                "borderRadius": "8px", "fontFamily": FONT}),
                html.Div("▼ ver detalle", style={"fontSize": "11px", "color": "#475569",
                                                  "padding": "6px 10px", "fontFamily": FONT,
                                                  "alignSelf": "center"}),
            ], style={"display": "flex", "gap": "8px", "alignItems": "center", "flexWrap": "wrap"}),
        ], style={"display": "flex", "justifyContent": "space-between", "alignItems": "center",
                  "gap": "16px", "cursor": "pointer"})

        # ── Detalle colapsable ────────────────────────────
        detalle = html.Div([
            html.Hr(style={"margin": "16px 0 12px", "borderColor": "rgba(255,255,255,0.06)"}),

            # Jornada + Inactivos + Mix
            html.Div([
                html.Div([
                    html.Div("JORNADA", style={"fontSize": "10px", "fontWeight": "700", "letterSpacing": "0.1em",
                                               "color": "#7ea3c4", "marginBottom": "8px", "fontFamily": FONT}),
                    stat_row("Días trabajados",  m["dias_trabajados"]),
                    stat_row("Hs. promedio/día", m["hs_prom"], color="#38bdf8"),
                    stat_row("Inicio a tiempo",  f"{m['ok_inicio']}/{m['total_dias']} ({pct_i}%)", color=inicio_color, bold=True),
                ], style={"flex": "1", "backgroundColor": "rgba(255,255,255,0.02)", "borderRadius": "10px",
                          "padding": "12px", "border": "1px solid rgba(255,255,255,0.05)"}),
                html.Div([
                    html.Div("INACTIVOS", style={"fontSize": "10px", "fontWeight": "700", "letterSpacing": "0.1em",
                                                 "color": "#7ea3c4", "marginBottom": "8px", "fontFamily": FONT}),
                    stat_row("Total inactivos", m["total_inactivos"], color=inact_color, bold=True),
                    stat_row("% Inactividad",   m["pct_inactivos"],   color=inact_color),
                    stat_row("Vs mes anterior", m["inact_var"] if m["inact_var"] else "—", color=var_col, bold=True),
                ], style={"flex": "1", "backgroundColor": "rgba(255,255,255,0.02)", "borderRadius": "10px",
                          "padding": "12px", "border": "1px solid rgba(255,255,255,0.05)"}),
                html.Div([
                    html.Div("MIX CORONA", style={"fontSize": "10px", "fontWeight": "700", "letterSpacing": "0.1em",
                                                  "color": "#7ea3c4", "marginBottom": "8px", "fontFamily": FONT}),
                    stat_row("% objetivo corona", f"{m['mix_pct_corona']:.0f}%", color=mix_color, bold=True),
                    html.Div("✅ Objetivo cumplido" if m["mix_ok_corona"] else "❌ Objetivo no cumplido",
                             style={"marginTop": "8px", "fontSize": "12px", "fontWeight": "700",
                                    "color": mix_color, "fontFamily": FONT}),
                ], style={"flex": "1", "backgroundColor": "rgba(255,255,255,0.02)", "borderRadius": "10px",
                          "padding": "12px", "border": "1px solid rgba(255,255,255,0.05)"}),
            ], style={"display": "flex", "gap": "10px", "marginBottom": "16px"}),

            # Desglose semanal
            html.Div(
                [html.Div("DESGLOSE POR SEMANA", style={"fontSize": "10px", "fontWeight": "700",
                                                         "letterSpacing": "0.1em", "color": "#7ea3c4",
                                                         "marginBottom": "10px", "fontFamily": FONT})]
                + (sem_rows if sem_rows else [html.Div("Sin datos semanales",
                                                       style={"color": "#475569", "fontSize": "12px", "fontFamily": FONT})])
            ),
        ], style={
            "backgroundColor": "#161b27",
            "border": "1px solid rgba(255,255,255,0.07)",
            "borderRadius": "18px",
            "padding": "22px 24px",
            "boxShadow": "0 8px 32px rgba(0,0,0,0.45)",
            "marginBottom": "20px",
        })
        cards.append(card)

    return cards