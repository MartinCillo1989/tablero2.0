from config import FONT

TBL_CELL = {
    "fontSize": 12,
    "padding": "10px 14px",
    "textAlign": "center",
    "border": "none",
    "borderBottom": "1px solid rgba(255,255,255,0.06)",
    "color": "#cbd5e1",
    "backgroundColor": "transparent",
    "fontFamily": FONT,
}

TBL_HEADER = {
    "fontWeight": "600",
    "fontSize": "11px",
    "letterSpacing": "0.06em",
    "textTransform": "uppercase",
    "backgroundColor": "#1e2535",
    "color": "#7ea3c4",
    "border": "none",
    "borderBottom": "2px solid rgba(59,130,246,0.3)",
    "fontFamily": FONT,
}

TBL_TABLE = {
    "overflowX": "auto",
    "backgroundColor": "transparent",
    "borderRadius": "10px",
}

DROPDOWN_STYLE = {
    "borderRadius": "10px",
    "fontSize": "13px",
    "fontFamily": FONT,
    "backgroundColor": "#0d1117",
    "border": "1px solid rgba(255,255,255,0.1)",
    "color": "#e2e8f0",
}

PLOTLY_LAYOUT = dict(
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    font=dict(family=FONT, color="#94a3b8"),
)

AXIS_STYLE = dict(
    gridcolor="rgba(255,255,255,0.05)",
    linecolor="rgba(255,255,255,0.08)",
    tickcolor="rgba(255,255,255,0.1)",
    showgrid=True,
)

DEFAULT_MARGIN = dict(t=30, b=40, l=20, r=20)

ACCENT_SEQUENCE = [
    "#3b82f6", "#22c55e", "#f59e0b", "#ec4899",
    "#8b5cf6", "#06b6d4", "#f97316", "#a3e635",
]

RANKING_CONDITIONAL = [
    {"if": {"row_index": "odd"}, "backgroundColor": "rgba(255,255,255,0.02)"},
    {"if": {"filter_query": '{Δ Importe} contains "▲"',    "column_id": "Δ Importe"},    "color": "#4ade80", "fontWeight": "700"},
    {"if": {"filter_query": '{Δ Importe} contains "▼"',    "column_id": "Δ Importe"},    "color": "#f87171", "fontWeight": "700"},
    {"if": {"filter_query": '{Δ Cantidades} contains "▲"', "column_id": "Δ Cantidades"}, "color": "#4ade80", "fontWeight": "700"},
    {"if": {"filter_query": '{Δ Cantidades} contains "▼"', "column_id": "Δ Cantidades"}, "color": "#f87171", "fontWeight": "700"},
    {"if": {"filter_query": '{Δ Visitas} contains "▲"',    "column_id": "Δ Visitas"},    "color": "#4ade80", "fontWeight": "700"},
    {"if": {"filter_query": '{Δ Visitas} contains "▼"',    "column_id": "Δ Visitas"},    "color": "#f87171", "fontWeight": "700"},
    {"if": {"column_id": "Pos."},     "fontWeight": "700", "color": "#7ea3c4", "width": "40px"},
    {"if": {"column_id": "Vendedor"}, "textAlign": "left", "fontWeight": "600", "color": "#e2e8f0"},
    {"if": {"state": "selected"},     "backgroundColor": "rgba(59,130,246,0.15)",
                                      "border": "1px solid rgba(59,130,246,0.4)"},
]
