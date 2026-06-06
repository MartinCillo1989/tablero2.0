from datetime import date, datetime

import pandas as pd

from utils.helpers import get_previous_year_month, apply_filters


# ======================================================
# HELPERS INTERNOS
# ======================================================
def _filter_ym(df, y, m):
    if not isinstance(df, pd.DataFrame) or df.empty:
        return pd.DataFrame()
    out = df.copy()
    if y is not None and "year" in out.columns:
        out = out[out["year"] == y]
    if m is not None and "month" in out.columns:
        out = out[out["month"] == m]
    return out


def _mix_por_vendedor(df: pd.DataFrame) -> pd.DataFrame:
    if not isinstance(df, pd.DataFrame) or df.empty or "vendedor" not in df.columns:
        return pd.DataFrame(columns=["vendedor", "base", "corona", "obj_corona", "pct"])

    art_u = df["articulo"].astype(str).str.upper() if "articulo" in df.columns else pd.Series([""] * len(df))
    m_pier   = art_u.str.contains(r"\(\s*010005\s*\)", regex=True, na=False) | art_u.str.contains("PIER ORIGINAL", na=False)
    m_livr   = art_u.str.contains(r"\(\s*010001\s*\)", regex=True, na=False) | (art_u.str.contains("LIVERPOOL", na=False) & art_u.str.contains("RED", na=False))
    m_corona = art_u.str.contains(r"\(\s*010008\s*\)", regex=True, na=False) | art_u.str.contains("CORONA", na=False)

    tmp = df.copy()
    tmp["_pier"]   = tmp["Cantidades Totales"].where(m_pier,   0)
    tmp["_livr"]   = tmp["Cantidades Totales"].where(m_livr,   0)
    tmp["_corona"] = tmp["Cantidades Totales"].where(m_corona, 0)

    agg = tmp.groupby("vendedor", as_index=False).agg(
        pier  =("_pier",   "sum"),
        livr  =("_livr",   "sum"),
        corona=("_corona", "sum"),
    )
    agg["base"]       = agg["pier"] + agg["livr"]
    agg["obj_corona"] = agg["base"] * 0.20
    agg["pct"]        = agg.apply(
        lambda r: (r["corona"] / r["obj_corona"] * 100) if r["obj_corona"] > 0 else 0.0, axis=1
    )
    return agg[["vendedor", "base", "corona", "obj_corona", "pct"]]


# ======================================================
# CORONA RANKING
# ======================================================
def build_corona_ranking(ven_df: pd.DataFrame, year=None, month=None) -> pd.DataFrame:
    today     = date.today()
    cur_year  = year  if year  is not None else today.year
    cur_month = month if month is not None else today.month
    prev_year, prev_month = get_previous_year_month(cur_year, cur_month)

    cur_mix  = _mix_por_vendedor(_filter_ym(ven_df, cur_year,  cur_month))
    prev_mix = _mix_por_vendedor(_filter_ym(ven_df, prev_year, prev_month))

    if cur_mix.empty:
        return pd.DataFrame()

    merged = cur_mix.merge(
        prev_mix[["vendedor", "pct"]].rename(columns={"pct": "pct_prev"}),
        on="vendedor", how="left"
    ).fillna(0)
    merged = merged[merged["vendedor"].str.strip() != ""]

    rows = []
    for i, (_, r) in enumerate(merged.sort_values("pct", ascending=False).iterrows(), start=1):
        cumple = r["corona"] >= r["obj_corona"] - 1e-9
        rows.append({
            "Pos.":               i,
            "Vendedor":           r["vendedor"],
            "Base (Pier+LivRed)": f"{r['base']:,.2f}",
            "Corona Vendido":     f"{r['corona']:,.2f}",
            "Obj. Corona (20%)":  f"{r['obj_corona']:,.2f}",
            "% Cumpl. Actual":    f"{r['pct']:.1f}%",
            "% Cumpl. Ant.":      f"{r['pct_prev']:.1f}%",
            "Cumple":             "✅" if cumple else "❌",
        })
    return pd.DataFrame(rows)


# ======================================================
# RANKINGS GENERALES
# ======================================================
def build_rankings(vis_df: pd.DataFrame, ven_df: pd.DataFrame, year=None, month=None) -> dict:
    today     = date.today()
    cur_year  = year  if year  is not None else today.year
    cur_month = month if month is not None else today.month
    prev_year, prev_month = get_previous_year_month(cur_year, cur_month)

    ven_cur  = _filter_ym(ven_df, cur_year,  cur_month)
    ven_prev = _filter_ym(ven_df, prev_year, prev_month)
    vis_cur  = _filter_ym(vis_df, cur_year,  cur_month)
    vis_prev = _filter_ym(vis_df, prev_year, prev_month)

    def agg_ventas(df):
        if not isinstance(df, pd.DataFrame) or df.empty or "vendedor" not in df.columns:
            return pd.DataFrame(columns=["vendedor", "importe", "cantidades"])
        tmp = df.copy()
        tmp["Importes Finales"]   = pd.to_numeric(tmp.get("Importes Finales",   0), errors="coerce").fillna(0)
        tmp["Cantidades Totales"] = pd.to_numeric(tmp.get("Cantidades Totales", 0), errors="coerce").fillna(0)
        return tmp.groupby("vendedor", as_index=False).agg(
            importe   =("Importes Finales",  "sum"),
            cantidades=("Cantidades Totales","sum"),
        )

    def agg_visitas(df):
        if not isinstance(df, pd.DataFrame) or df.empty or "vendedor" not in df.columns:
            return pd.DataFrame(columns=["vendedor", "visitas"])
        return df.groupby("vendedor", as_index=False).size().rename(columns={"size": "visitas"})

    merged = (
        agg_ventas(ven_cur)
        .merge(agg_ventas(ven_prev),   on="vendedor", how="outer", suffixes=("_cur", "_prev"))
        .merge(agg_visitas(vis_cur),   on="vendedor", how="outer")
        .merge(agg_visitas(vis_prev),  on="vendedor", how="outer", suffixes=("_cur", "_prev"))
    )
    for col in ["importe_cur", "importe_prev", "cantidades_cur", "cantidades_prev", "visitas_cur", "visitas_prev"]:
        if col not in merged.columns:
            merged[col] = 0.0
    merged = merged.fillna(0)
    merged = merged[merged["vendedor"].astype(str).str.strip() != ""]

    merged["Δ Importe"]     = merged["importe_cur"]    - merged["importe_prev"]
    merged["Δ% Importe"]    = merged.apply(lambda r: r["Δ Importe"]    / r["importe_prev"]    * 100 if r["importe_prev"]    > 0 else 0.0, axis=1)
    merged["Δ Cantidades"]  = merged["cantidades_cur"] - merged["cantidades_prev"]
    merged["Δ% Cantidades"] = merged.apply(lambda r: r["Δ Cantidades"] / r["cantidades_prev"] * 100 if r["cantidades_prev"] > 0 else 0.0, axis=1)
    merged["Δ Visitas"]     = merged["visitas_cur"]    - merged["visitas_prev"]
    merged["Δ% Visitas"]    = merged.apply(lambda r: r["Δ Visitas"]    / r["visitas_prev"]    * 100 if r["visitas_prev"]    > 0 else 0.0, axis=1)

    def fmt_row(row):
        return {
            "Vendedor":       row["vendedor"],
            "Importe Actual": f"$ {row['importe_cur']:,.0f}",
            "Importe Ant.":   f"$ {row['importe_prev']:,.0f}",
            "Δ Importe":      f"{'▲' if row['Δ Importe'] >= 0 else '▼'} $ {abs(row['Δ Importe']):,.0f} ({row['Δ% Importe']:+.1f}%)",
            "Cant. Actual":   f"{row['cantidades_cur']:,.2f}",
            "Cant. Ant.":     f"{row['cantidades_prev']:,.2f}",
            "Δ Cantidades":   f"{'▲' if row['Δ Cantidades'] >= 0 else '▼'} {abs(row['Δ Cantidades']):,.2f} ({row['Δ% Cantidades']:+.1f}%)",
            "Visitas Actual": int(row["visitas_cur"]),
            "Visitas Ant.":   int(row["visitas_prev"]),
            "Δ Visitas":      f"{'▲' if row['Δ Visitas'] >= 0 else '▼'} {abs(int(row['Δ Visitas']))} ({row['Δ% Visitas']:+.1f}%)",
            "_importe_cur":   row["importe_cur"],
            "_delta_importe": row["Δ Importe"],
        }

    rows   = [fmt_row(r) for _, r in merged.iterrows()]
    empty  = {k: pd.DataFrame() for k in ["mejores", "peores", "mejoraron", "empeoraron", "cur_label", "prev_label"]}
    if not rows:
        return empty

    df_all = pd.DataFrame(rows)
    disp   = ["Vendedor", "Importe Actual", "Importe Ant.", "Δ Importe",
              "Cant. Actual", "Cant. Ant.", "Δ Cantidades",
              "Visitas Actual", "Visitas Ant.", "Δ Visitas"]

    def mk(df, col, asc):
        out = df.sort_values(col, ascending=asc).reset_index(drop=True)
        out.index += 1
        out.index.name = "Pos."
        return out[disp].reset_index()

    return {
        "mejores":    mk(df_all, "_importe_cur", False),
        "peores":     mk(df_all[df_all["_importe_cur"] > 0], "_importe_cur", True),
        "mejoraron":  mk(df_all[df_all["_delta_importe"] > 0], "_delta_importe", False),
        "empeoraron": mk(df_all[df_all["_delta_importe"] < 0], "_delta_importe", True),
        "cur_label":  f"{cur_month:02d}/{cur_year}",
        "prev_label": f"{prev_month:02d}/{prev_year}" if prev_month else "—",
    }
