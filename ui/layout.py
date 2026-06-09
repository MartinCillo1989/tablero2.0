from datetime import date

from dash import dcc, html, dash_table

from config import FONT
from ui.styles import TBL_CELL, TBL_HEADER, TBL_TABLE, DROPDOWN_STYLE, RANKING_CONDITIONAL
from ui.components import panel, section_title, filter_label, ranking_table


INDEX_STRING = '''
<!DOCTYPE html>
<html>
<head>
  {%metas%}
  <title>{%title%}</title>
  {%favicon%}
  {%css%}
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=DM+Sans:wght@300;400;500;600;700;800&display=swap" rel="stylesheet">
  <style>
    *, *::before, *::after { box-sizing: border-box; }
    body { margin: 0; background: #0d1117; }
    ::-webkit-scrollbar { width: 6px; height: 6px; }
    ::-webkit-scrollbar-track { background: #0d1117; }
    ::-webkit-scrollbar-thumb { background: #2d3748; border-radius: 3px; }
    ::-webkit-scrollbar-thumb:hover { background: #3b82f6; }
    .Select-control { background-color: #0d1117 !important; border-color: rgba(255,255,255,0.1) !important; }
    .Select-menu-outer { background-color: #0d1117 !important; border-color: rgba(255,255,255,0.1) !important; }
    .Select-placeholder { color: #64748b !important; }
    .Select-value-label { color: #e2e8f0 !important; }
    .Select-input input { color: #e2e8f0 !important; background: transparent !important; }
    .Select-arrow-zone .Select-arrow { border-top-color: #64748b !important; }
    .is-open .Select-arrow { border-bottom-color: #64748b !important; }
    .Select-option { background-color: #0d1117 !important; color: #e2e8f0 !important; }
    .Select-option:hover, .Select-option.is-focused { background-color: #1a2035 !important; }
    .Select-option.is-selected { background-color: #1d3566 !important; color: #60a5fa !important; }
    .VirtualizedSelectOption { background-color: #0d1117 !important; color: #e2e8f0 !important; }
    .dash-spreadsheet-container .dash-spreadsheet-inner tr:hover td { background-color: rgba(59,130,246,0.06) !important; }
    @media (max-width: 600px) {
      h1 { font-size: 24px !important; }
      .dash-tab { padding: 8px 10px !important; font-size: 11px !important; }
    }
  </style>
</head>
<body>
  {%app_entry%}
  <footer>{%config%}{%scripts%}{%renderer%}</footer>
</body>
</html>
'''


def _tab_dashboard():
    return dcc.Tab(label="📊  Dashboard", value="tab_dashboard", children=[
        html.Div(style={"marginTop": "20px"}, children=[
            html.Div(id="kpis", style={"display": "grid", "gridTemplateColumns": "repeat(auto-fit, minmax(140px, 1fr))", "gap": "12px", "marginBottom": "24px"}),
            html.Div(
                style={"display": "grid", "gridTemplateColumns": "repeat(auto-fit, minmax(300px, 1fr))", "gap": "20px"},
                children=[
                    panel([section_title("Motivos de No Venta"),
                           dcc.Graph(id="motivos_bar", style={"height": "360px"}, config={"displayModeBar": False})]),
                    panel([section_title("Mix por Marca — Cantidades Totales"),
                           dcc.Graph(id="mix_bar", style={"height": "360px"}, config={"displayModeBar": False}),
                           html.Div(id="mix_obj_box", style={
                               "marginTop": "14px", "backgroundColor": "#1a2035",
                               "border": "1px solid rgba(59,130,246,0.15)",
                               "borderRadius": "12px", "padding": "14px 16px",
                           })]),
                ],
            ),
            html.Div(style={"marginTop": "20px"}),
            panel([
                section_title("Resumen de Ventas por Vendedor / Semana"),
                dash_table.DataTable(
                    id="ventas_sem_tbl", page_size=20, sort_action="native",
                    sort_mode="multi", filter_action="native",
                    style_table=TBL_TABLE, style_cell=TBL_CELL, style_header=TBL_HEADER,
                    style_data_conditional=[
                        {"if": {"row_index": "odd"}, "backgroundColor": "rgba(255,255,255,0.02)"},
                        {"if": {"column_id": "Importe Final"}, "fontWeight": "700", "color": "#22c55e"},
                        {"if": {"state": "selected"}, "backgroundColor": "rgba(59,130,246,0.15)", "border": "1px solid rgba(59,130,246,0.4)"},
                    ],
                ),
            ]),
            html.Div(style={"marginTop": "20px"}),
            html.Div(
                style={"display": "flex", "justifyContent": "space-between", "alignItems": "center", "marginBottom": "12px"},
                children=[
                    section_title("Jornada por Día — desde Visitas", style={"color": "#e2e8f0", "marginBottom": "0", "fontSize": "14px"}),
                    html.Button("⬇  Descargar Excel", id="btn_download_jornada", n_clicks=0, style={
                        "height": "36px", "cursor": "pointer",
                        "background": "linear-gradient(135deg, #14532d 0%, #166534 100%)",
                        "color": "#86efac", "border": "1px solid rgba(34,197,94,0.35)",
                        "borderRadius": "10px", "padding": "0 16px",
                        "fontWeight": "600", "fontSize": "12px", "fontFamily": FONT,
                    }),
                ],
            ),
            dcc.Download(id="download_jornada_excel"),
            panel([
                dash_table.DataTable(
                    id="jornada_tbl", page_size=15, sort_action="native", sort_mode="multi",
                    style_table=TBL_TABLE, style_cell=TBL_CELL, style_header=TBL_HEADER,
                    style_data_conditional=[
                        {"if": {"row_index": "odd"}, "backgroundColor": "rgba(255,255,255,0.02)"},
                        {"if": {"filter_query": "{hs_trab} < 8", "column_id": "hs_trab_hhmm"}, "backgroundColor": "rgba(239,68,68,0.12)", "color": "#fca5a5", "fontWeight": "700"},
                        {"if": {"filter_query": '{inicio_obj} = "✅"', "column_id": "inicio_obj"}, "color": "#4ade80", "fontWeight": "700", "fontSize": "16px"},
                        {"if": {"filter_query": '{inicio_obj} = "❌"', "column_id": "inicio_obj"}, "color": "#f87171", "fontWeight": "700", "fontSize": "16px"},
                        {"if": {"filter_query": '{inicio_obj} = "—"', "column_id": "inicio_obj"}, "color": "#64748b"},
                        {"if": {"state": "selected"}, "backgroundColor": "rgba(59,130,246,0.15)", "border": "1px solid rgba(59,130,246,0.4)"},
                    ],
                ),
            ]),
            html.Div(style={"marginTop": "20px"}),
            html.Div(
                style={"display": "flex", "justifyContent": "space-between", "alignItems": "center", "marginBottom": "12px"},
                children=[
                    section_title("Clientes Inactivos — Último Mes", style={"color": "#e2e8f0", "marginBottom": "0", "fontSize": "14px"}),
                    html.Div("Fuente: control_clientes_inactivos.xlsx", style={"fontSize": "11px", "color": "#475569", "fontFamily": FONT}),
                ],
            ),
            panel([
                dash_table.DataTable(
                    id="inactivos_tbl", page_size=20, sort_action="native", sort_mode="multi", filter_action="native",
                    style_table=TBL_TABLE, style_cell=TBL_CELL, style_header=TBL_HEADER,
                    style_data_conditional=[
                        {"if": {"row_index": "odd"}, "backgroundColor": "rgba(255,255,255,0.02)"},
                        {"if": {"column_id": "Total inactivos"}, "fontWeight": "700", "color": "#fbbf24"},
                        {"if": {"state": "selected"}, "backgroundColor": "rgba(59,130,246,0.15)", "border": "1px solid rgba(59,130,246,0.4)"},
                    ],
                ),
            ], {"marginBottom": "40px"}),
        ]),
    ])


def _tab_rankings():
    return dcc.Tab(label="🏆  Rankings", value="tab_rankings", children=[
        html.Div(style={"marginTop": "20px"}, children=[
            html.Div(id="ranking_periodo_label", style={"fontSize": "12px", "color": "#64748b", "fontFamily": FONT, "marginBottom": "20px"}),
            _rank_section("🏆", "Mejores Vendedores",         "#fbbf24", "tbl_mejores"),
            _rank_section("💀", "Peores Vendedores",          "#f87171", "tbl_peores"),
            _rank_section("📈", "Mejoraron vs Mes Anterior",  "#4ade80", "tbl_mejoraron"),
            _rank_section("📉", "Empeoraron vs Mes Anterior", "#f87171", "tbl_empeoraron"),
            html.Div(style={"display": "flex", "alignItems": "center", "gap": "10px", "marginBottom": "12px"},
                     children=[html.Span("👥", style={"fontSize": "20px"}),
                               section_title("Clientes Inactivos — Todos los Vendedores", style={"color": "#94a3b8", "marginBottom": "0", "fontSize": "14px"})]),
            panel([
                dash_table.DataTable(
                    id="tbl_inactivos_todos", page_size=30, sort_action="native", sort_mode="multi", filter_action="native",
                    style_table=TBL_TABLE, style_cell=TBL_CELL, style_header=TBL_HEADER,
                    style_data_conditional=[
                        {"if": {"row_index": "odd"}, "backgroundColor": "rgba(255,255,255,0.02)"},
                        {"if": {"column_id": "Total inactivos"},    "fontWeight": "700", "color": "#fbbf24"},
                        {"if": {"column_id": "Inactivos mes ant."}, "color": "#94a3b8"},
                        {"if": {"filter_query": '{Variación} contains "▲"', "column_id": "Variación"}, "color": "#f87171", "fontWeight": "700"},
                        {"if": {"filter_query": '{Variación} contains "▼"', "column_id": "Variación"}, "color": "#4ade80", "fontWeight": "700"},
                        {"if": {"filter_query": '{Variación} = "→ 0"',       "column_id": "Variación"}, "color": "#94a3b8"},
                        {"if": {"column_id": "% Inactivos"}, "color": "#f59e0b"},
                        {"if": {"state": "selected"}, "backgroundColor": "rgba(59,130,246,0.15)", "border": "1px solid rgba(59,130,246,0.4)"},
                    ],
                ),
            ], {"marginBottom": "24px"}),
            html.Div(style={"display": "flex", "alignItems": "center", "gap": "10px", "marginBottom": "12px"},
                     children=[html.Span("🚬", style={"fontSize": "20px"}),
                               section_title("Objetivo Corona — Cumplimiento por Vendedor", style={"color": "#f59e0b", "marginBottom": "0", "fontSize": "14px"})]),
            panel([
                dash_table.DataTable(
                    id="tbl_corona", page_size=30, sort_action="native", sort_mode="multi",
                    style_table=TBL_TABLE, style_cell=TBL_CELL, style_header=TBL_HEADER,
                    style_data_conditional=[
                        {"if": {"row_index": "odd"}, "backgroundColor": "rgba(255,255,255,0.02)"},
                        {"if": {"filter_query": '{Cumple} = "✅"', "column_id": "Cumple"}, "color": "#4ade80", "fontWeight": "700", "fontSize": "16px"},
                        {"if": {"filter_query": '{Cumple} = "❌"', "column_id": "Cumple"}, "color": "#f87171", "fontWeight": "700", "fontSize": "16px"},
                        {"if": {"column_id": "% Cumpl. Actual"}, "fontWeight": "700", "color": "#fbbf24"},
                        {"if": {"column_id": "Corona Vendido"},  "color": "#f59e0b"},
                        {"if": {"column_id": "Vendedor"},        "textAlign": "left", "fontWeight": "600", "color": "#e2e8f0"},
                        {"if": {"column_id": "Pos."},            "fontWeight": "700", "color": "#7ea3c4", "width": "40px"},
                        {"if": {"state": "selected"}, "backgroundColor": "rgba(59,130,246,0.15)", "border": "1px solid rgba(59,130,246,0.4)"},
                    ],
                ),
            ], {"marginBottom": "40px"}),
        ]),
    ])


def _tab_resumen():
    return dcc.Tab(label="👤  Resumen por Vendedor", value="tab_resumen", children=[
        html.Div(style={"marginTop": "20px"}, children=[
            html.Div([
                filter_label("Seleccioná un vendedor"),
                dcc.Dropdown(
                    id="f_vend_resumen",
                    options=[],
                    value=None,
                    clearable=True,
                    placeholder="Elegí un vendedor...",
                    style=DROPDOWN_STYLE,
                ),
            ], style={"maxWidth": "400px", "marginBottom": "24px"}),
            html.Div(id="resumen_cards", style={"display": "flex", "flexDirection": "column"}),
        ]),
    ])


def _rank_section(emoji, title_text, color, table_id):
    return html.Div([
        html.Div(
            style={"display": "flex", "alignItems": "center", "gap": "10px", "marginBottom": "12px"},
            children=[html.Span(emoji, style={"fontSize": "20px"}),
                      section_title(title_text, style={"color": color, "marginBottom": "0", "fontSize": "14px"})],
        ),
        panel([ranking_table(table_id)], {"marginBottom": "24px"}),
    ])


def build_layout():
    return html.Div(
        style={
            "fontFamily": FONT,
            "padding": "16px",
            "backgroundColor": "#0d1117",
            "minHeight": "100vh",
            "color": "#e2e8f0",
        },
        children=[
            # ── Header ──────────────────────────────────────
            html.Div(
                style={
                    "display": "flex", "alignItems": "center", "justifyContent": "space-between",
                    "marginBottom": "24px", "paddingBottom": "20px",
                    "borderBottom": "1px solid rgba(255,255,255,0.07)",
                },
                children=[
                    html.Div([
                        html.Div("SUPERVISIÓN", style={
                            "fontSize": "11px", "fontWeight": "700", "letterSpacing": "0.2em",
                            "color": "#3b82f6", "marginBottom": "2px", "fontFamily": FONT,
                        }),
                        html.H1("Aloma", style={
                            "margin": "0", "fontSize": "32px", "fontWeight": "800",
                            "color": "#e2e8f0", "letterSpacing": "-0.03em",
                            "fontFamily": FONT, "lineHeight": "1",
                        }),
                    ]),
                    html.Div(style={"display": "flex", "alignItems": "center", "gap": "10px"}, children=[
                        html.Div(id="reload_status", style={"fontSize": "12px", "color": "#64748b", "fontFamily": FONT}),
                        html.Button("↺  Recargar datos", id="btn_reload", n_clicks=0, style={
                            "height": "38px", "cursor": "pointer",
                            "background": "linear-gradient(135deg, #1d3566 0%, #1e4080 100%)",
                            "color": "#93c5fd", "border": "1px solid rgba(59,130,246,0.4)",
                            "borderRadius": "10px", "padding": "0 18px",
                            "fontWeight": "600", "fontSize": "13px", "fontFamily": FONT,
                        }),
                    ]),
                ],
            ),

            # ── Filtros ─────────────────────────────────────
            html.Div(
                style={
                    "display": "grid",
                    "gridTemplateColumns": "repeat(auto-fit, minmax(140px, 1fr))",
                    "gap": "12px", "marginBottom": "24px",
                    "backgroundColor": "#161b27",
                    "border": "1px solid rgba(255,255,255,0.07)",
                    "borderRadius": "16px", "padding": "16px 18px",
                    "boxShadow": "0 4px 20px rgba(0,0,0,0.35)",
                },
                children=[
                    html.Div([filter_label("Año"),   dcc.Dropdown(id="f_year",  options=[], value=None, clearable=True, style=DROPDOWN_STYLE)]),
                    html.Div([filter_label("Mes"),   dcc.Dropdown(id="f_month", options=[{"label": f"{m:02d}", "value": m} for m in range(1, 13)], value=date.today().month, clearable=True, style=DROPDOWN_STYLE)]),
                    html.Div([filter_label("Semana"), dcc.Dropdown(id="f_week", options=[], value=None, clearable=True, style=DROPDOWN_STYLE)]),
                    html.Div([filter_label("Vendedor"), dcc.Dropdown(id="f_vend", options=[], value=None, clearable=True, style=DROPDOWN_STYLE)]),
                ],
            ),

            # ── Tabs (se renderizan según el rol del usuario) ─
            html.Div(id="tabs_container"),
        ],
    )