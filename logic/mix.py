import pandas as pd
from dash import html

from config import FONT
from utils.helpers import _fmt_qty, _badge, get_previous_year_month


# ======================================================
# CÁLCULOS
# ======================================================
def compute_mix_objective(ven_f: pd.DataFrame) -> dict:
    empty = {"base": 0.0, "pier_original": 0.0, "liverpool_red": 0.0, "corona": 0.0, "pier_caps": 0.0}
    if not isinstance(ven_f, pd.DataFrame) or ven_f.empty or "articulo" not in ven_f.columns:
        return empty

    art_u = ven_f["articulo"].astype(str).str.upper()

    def sum_mask(mask):
        if mask is None or mask.sum() == 0:
            return 0.0
        return float(ven_f.loc[mask, "Cantidades Totales"].sum())

    m_pier_original = (
        art_u.str.contains(r"\(\s*010005\s*\)", regex=True, na=False) |
        art_u.str.contains("PIER ORIGINAL", na=False)
    )
    m_liv_red = (
        art_u.str.contains(r"\(\s*010001\s*\)", regex=True, na=False) |
        (art_u.str.contains("LIVERPOOL", na=False) & art_u.str.contains("RED", na=False))
    )
    m_corona = (
        art_u.str.contains(r"\(\s*010008\s*\)", regex=True, na=False) |
        art_u.str.contains("CORONA", na=False)
    )
    m_pier_caps = (
        art_u.str.contains(r"\(\s*010010\s*\)", regex=True, na=False) |
        art_u.str.contains("PIER CAPS", na=False)
    )

    pier_original = sum_mask(m_pier_original)
    liverpool_red = sum_mask(m_liv_red)
    corona        = sum_mask(m_corona)
    pier_caps     = sum_mask(m_pier_caps)
    base          = pier_original + liverpool_red

    return {"base": base, "pier_original": pier_original, "liverpool_red": liverpool_red,
            "corona": corona, "pier_caps": pier_caps}


def compute_mix_progress(ven_f: pd.DataFrame) -> dict:
    vals  = compute_mix_objective(ven_f)
    base  = float(vals.get("base",  0.0) or 0.0)
    corona = float(vals.get("corona", 0.0) or 0.0)

    if base <= 0:
        return {**vals, "obj_corona": 0.0, "pct_corona": 0.0, "pct_promedio": 0.0}

    obj_corona  = base * 0.20
    pct_corona  = (corona / obj_corona * 100) if obj_corona > 0 else 0.0
    return {**vals, "obj_corona": obj_corona, "pct_corona": pct_corona, "pct_promedio": pct_corona}


# ======================================================
# RENDER BOX
# ======================================================
def render_mix_objective_box(vals: dict, prev_vals=None) -> html.Div:
    base        = float(vals.get("base",        0.0) or 0.0)
    pier_original = float(vals.get("pier_original", 0.0) or 0.0)
    liverpool_red = float(vals.get("liverpool_red", 0.0) or 0.0)
    corona      = float(vals.get("corona",      0.0) or 0.0)
    obj_corona  = float(vals.get("obj_corona",  0.0) or 0.0)
    pct_corona  = float(vals.get("pct_corona",  0.0) or 0.0)
    pct_promedio = float(vals.get("pct_promedio", 0.0) or 0.0)

    title = html.Div("OBJETIVO MIX", style={
        "fontWeight": "700", "fontSize": "11px", "letterSpacing": "0.1em",
        "color": "#7ea3c4", "marginBottom": "10px", "fontFamily": FONT,
    })

    def row(left, right, highlight=False):
        return html.Div([
            html.Div(left,  style={"color": "#94a3b8", "fontSize": "12px", "fontFamily": FONT}),
            html.Div(right, style={"fontWeight": "700", "fontSize": "13px",
                                   "color": "#3b82f6" if highlight else "#e2e8f0", "fontFamily": FONT}),
        ], style={"display": "flex", "justifyContent": "space-between", "alignItems": "center",
                  "gap": "12px", "marginTop": "6px", "padding": "4px 0",
                  "borderBottom": "1px solid rgba(255,255,255,0.04)"})

    if base <= 0:
        extra = []
        if prev_vals is not None:
            prev_prom = float(prev_vals.get("pct_promedio", 0.0) or 0.0)
            extra = [html.Hr(style={"margin": "10px 0", "borderColor": "rgba(255,255,255,0.08)"}),
                     row("Promedio mes anterior", f"{prev_prom:.0f}%")]
        return html.Div([title, html.Div("Sin base (Pier Original + Liverpool Red = 0).",
            style={"color": "#64748b", "fontSize": "12px", "fontFamily": FONT}), *extra])

    ok_corona       = corona >= obj_corona - 1e-9
    comparison_block = []

    if prev_vals is not None:
        prev_prom = float(prev_vals.get("pct_promedio", 0.0) or 0.0)
        dif       = pct_promedio - prev_prom
        if dif > 0.01:
            estado, color, dif_txt = "↑ Mejoró vs mes anterior", "#22c55e", f"+{dif:.0f}%"
        elif dif < -0.01:
            estado, color, dif_txt = "↓ Cayó vs mes anterior",   "#ef4444", f"{dif:.0f}%"
        else:
            estado, color, dif_txt = "→ Sin cambios vs mes anterior", "#94a3b8", "0%"

        comparison_block = [
            html.Hr(style={"margin": "10px 0", "borderColor": "rgba(255,255,255,0.08)"}),
            row("Promedio actual",       f"{pct_promedio:.0f}%", highlight=True),
            row("Promedio mes anterior", f"{prev_prom:.0f}%"),
            html.Div(f"{estado} ({dif_txt})", style={
                "marginTop": "10px", "fontWeight": "700", "color": color,
                "backgroundColor": "rgba(255,255,255,0.04)",
                "padding": "8px 12px", "borderRadius": "8px",
                "border": f"1px solid {color}33",
                "fontSize": "12px", "fontFamily": FONT, "letterSpacing": "0.02em",
            }),
        ]

    return html.Div([
        title,
        row("Base (Pier Original + Liverpool Red)", _fmt_qty(base)),
        row("Pier Original",  _fmt_qty(pier_original)),
        row("Liverpool Red",  _fmt_qty(liverpool_red)),
        html.Hr(style={"margin": "10px 0", "borderColor": "rgba(255,255,255,0.08)"}),
        row(f"Corona vendido / objetivo (20%) {_badge(ok_corona)}",
            f"{_fmt_qty(corona)} / {_fmt_qty(obj_corona)}  ({pct_corona:.0f}%)"),
        *comparison_block,
    ])
