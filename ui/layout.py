from datetime import date

from dash import dcc, html, dash_table

from config import FONT, COBERTURA_OBJETIVO_PCT
from ui.styles import TBL_CELL, TBL_HEADER, TBL_TABLE, DROPDOWN_STYLE, RANKING_CONDITIONAL
from ui.components import panel, section_title, filter_label, ranking_table

try:
    from secrets_config import GOOGLE_MAPS_API_KEY
except ImportError:
    GOOGLE_MAPS_API_KEY = None


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
    .Select-clear-zone { color: #64748b !important; opacity: 1 !important; }
    .Select-clear-zone:hover { color: #f87171 !important; }
    .Select-clear { font-size: 16px !important; }
    .Select-arrow-zone { opacity: 1 !important; }
    .dash-spreadsheet-container .dash-spreadsheet-inner tr:hover td { background-color: #1c2333 !important; color: #e2e8f0 !important; }
    .dash-spreadsheet td[data-dash-column="Nota"] { background-color: rgba(59,130,246,0.05) !important; cursor: text !important; }

    /* DatePickerSingle (react-dates) — retematizado para el modo oscuro */
    .SingleDatePickerInput { background-color: #0d1117 !important; border: 1px solid rgba(255,255,255,0.1) !important; border-radius: 10px !important; overflow: hidden; }
    .SingleDatePickerInput_calendarIcon { padding: 6px !important; }
    .DateInput { background-color: #0d1117 !important; }
    .DateInput_input { background-color: #0d1117 !important; color: #e2e8f0 !important; font-family: 'DM Sans', sans-serif !important; font-size: 13px !important; font-weight: 600 !important; border-bottom: none !important; padding: 8px 11px !important; }
    .DateInput_input__focused { border-bottom: 2px solid #3b82f6 !important; }
    .DateInput_fang { display: none !important; }
    .SingleDatePicker_picker { background-color: #0d1117 !important; border: 1px solid rgba(255,255,255,0.1) !important; border-radius: 10px !important; overflow: hidden; }
    .DayPicker, .DayPicker_transitionContainer, .CalendarMonth, .CalendarMonth_table, .DayPicker_weekHeader { background-color: #0d1117 !important; }
    .CalendarMonth_caption { color: #e2e8f0 !important; font-family: 'DM Sans', sans-serif !important; }
    .DayPicker_weekHeader_li small { color: #64748b !important; }
    .CalendarDay { background: #161b27 !important; border: 1px solid rgba(255,255,255,0.05) !important; color: #e2e8f0 !important; }
    .CalendarDay:hover { background: #1c2333 !important; }
    .CalendarDay__selected, .CalendarDay__selected:hover { background: #3b82f6 !important; border-color: #3b82f6 !important; color: #ffffff !important; }
    .CalendarDay__today { color: #4ade80 !important; font-weight: 700 !important; }
    .CalendarDay__blocked_out_of_range, .CalendarDay__blocked_out_of_range:hover { background: transparent !important; color: #334155 !important; }
    .DayPickerNavigation_button__horizontal { border: 1px solid rgba(255,255,255,0.1) !important; background-color: #161b27 !important; }
    .DayPickerNavigation_svg__horizontal { fill: #94a3b8 !important; }
    .SingleDatePickerInput_clearDate { background: transparent !important; }
    .SingleDatePickerInput_clearDate_svg { fill: #64748b !important; }
    @media (max-width: 600px) {
      h1 { font-size: 24px !important; }
      .dash-tab { padding: 8px 10px !important; font-size: 11px !important; }
    }
  </style>
  __GOOGLE_MAPS_SCRIPT_TAG__
</head>
<body>
  {%app_entry%}
  <footer>{%config%}{%scripts%}{%renderer%}</footer>
</body>
</html>
'''

if GOOGLE_MAPS_API_KEY:
    INDEX_STRING = INDEX_STRING.replace(
        "__GOOGLE_MAPS_SCRIPT_TAG__",
        f'<script src="https://maps.googleapis.com/maps/api/js?key={GOOGLE_MAPS_API_KEY}&libraries=marker"></script>',
    )
else:
    INDEX_STRING = INDEX_STRING.replace("__GOOGLE_MAPS_SCRIPT_TAG__", "")


def _tab_dashboard():
    return dcc.Tab(label="📊  Dashboard", value="tab_dashboard", children=[
        html.Div(style={"marginTop": "20px"}, children=[
            html.Div(id="kpis", style={"display": "grid", "gridTemplateColumns": "repeat(auto-fit, minmax(140px, 1fr))", "gap": "12px", "marginBottom": "24px"}),
            html.Div(
                style={"display": "grid", "gridTemplateColumns": "repeat(auto-fit, minmax(300px, 1fr))", "gap": "20px"},
                children=[
                    panel([section_title("Mix por Marca — Cantidades Totales"),
                           dcc.Graph(id="mix_bar", style={"height": "360px"}, config={"displayModeBar": False}),
                           html.Div(id="mix_obj_box", style={
                               "marginTop": "14px", "backgroundColor": "#1a2035",
                               "border": "1px solid rgba(59,130,246,0.15)",
                               "borderRadius": "12px", "padding": "14px 16px",
                           })]),
                    panel([
                        section_title("Ventas por Vendedor — de un Artículo puntual", style={"marginBottom": "4px"}),
                        html.Div("Usá los filtros de Año/Mes/Semana de arriba para acotar el período.", style={"fontSize": "11px", "color": "#475569", "fontFamily": FONT, "marginBottom": "12px"}),
                        html.Div([
                            filter_label("Filtrar por artículo"),
                            dcc.Dropdown(
                                id="f_articulo_ventas", options=[], value=None, clearable=True,
                                placeholder="Elegí un artículo...",
                                style={**DROPDOWN_STYLE, "marginBottom": "12px"},
                            ),
                        ]),
                        dash_table.DataTable(
                            id="ventas_articulo_tbl", page_size=21, sort_action="native",
                            sort_mode="multi", filter_action="native",
                            style_table={**TBL_TABLE, "height": "620px", "overflowY": "auto"}, style_cell=TBL_CELL, style_header=TBL_HEADER,
                            style_data_conditional=[
                                {"if": {"row_index": "odd"}, "backgroundColor": "rgba(255,255,255,0.02)"},
                                {"if": {"column_id": "Vendedor"}, "textAlign": "left", "fontWeight": "600", "color": "#e2e8f0"},
                                {"if": {"column_id": "Cantidades Totales"}, "color": "#4ade80", "fontWeight": "700"},
                                {"if": {"state": "selected"}, "backgroundColor": "rgba(59,130,246,0.15)", "border": "1px solid rgba(59,130,246,0.4)"},
                            ],
                        ),
                    ]),
                    panel([section_title("Mix Varios — Cantidades Totales"),
                           dcc.Graph(id="mix_varios_bar", style={"height": "360px"}, config={"displayModeBar": False})]),
                ],
            ),

            html.Div(style={"marginTop": "20px"}),
            html.Div(
                style={"display": "flex", "justifyContent": "space-between", "alignItems": "flex-end", "flexWrap": "wrap", "gap": "16px", "marginBottom": "12px"},
                children=[
                    html.Div([
                        section_title("Detalle de Motivos de No Venta — por cliente", style={"color": "#e2e8f0", "marginBottom": "4px", "fontSize": "14px"}),
                        html.Div("Usá los filtros de Año/Mes/Semana/Vendedor de arriba para acotar.", style={"fontSize": "11px", "color": "#475569", "fontFamily": FONT}),
                    ]),
                    html.Div([
                        filter_label("Filtrar por motivo"),
                        dcc.Dropdown(
                            id="f_motivos_filtro", options=[], value=[], multi=True, clearable=True,
                            placeholder="Todos los motivos",
                            style={**DROPDOWN_STYLE, "minWidth": "320px"},
                        ),
                    ]),
                    html.Div([
                        filter_label("Filtrar por día de ruta"),
                        dcc.Dropdown(
                            id="f_ruta_filtro",
                            options=[
                                {"label": "Lunes",     "value": "LUNES"},
                                {"label": "Martes",    "value": "MARTES"},
                                {"label": "Miércoles", "value": "MIERCOLES"},
                                {"label": "Jueves",    "value": "JUEVES"},
                                {"label": "Viernes",   "value": "VIERNES"},
                            ],
                            value=[], multi=True, clearable=True,
                            placeholder="Todos los días",
                            style={**DROPDOWN_STYLE, "minWidth": "260px"},
                        ),
                    ]),
                    html.Div([
                        filter_label(""),
                        html.Button("⬇  Descargar Excel", id="btn_download_motivos", n_clicks=0, style={
                            "height": "38px", "cursor": "pointer",
                            "background": "linear-gradient(135deg, #14532d 0%, #166534 100%)",
                            "color": "#86efac", "border": "1px solid rgba(34,197,94,0.35)",
                            "borderRadius": "10px", "padding": "0 16px",
                            "fontWeight": "600", "fontSize": "12px", "fontFamily": FONT,
                        }),
                    ]),
                ],
            ),
            dcc.Download(id="download_motivos_excel"),
            panel([
                dash_table.DataTable(
                    id="motivos_detalle_tbl", page_size=20, sort_action="native",
                    sort_mode="multi", filter_action="native",
                    style_table=TBL_TABLE, style_cell=TBL_CELL, style_header=TBL_HEADER,
                    style_data_conditional=[
                        {"if": {"row_index": "odd"}, "backgroundColor": "rgba(255,255,255,0.02)"},
                        {"if": {"column_id": "Motivo"}, "color": "#f59e0b", "fontWeight": "600"},
                        {"if": {"column_id": "Cliente"}, "textAlign": "left", "fontWeight": "600", "color": "#e2e8f0"},
                        {"if": {"state": "selected"}, "backgroundColor": "rgba(59,130,246,0.15)", "border": "1px solid rgba(59,130,246,0.4)"},
                    ],
                ),
            ]),

            html.Div(style={"marginTop": "20px"}),
            panel([
                section_title("Resumen de Ventas por Vendedor / Semana"),
                dash_table.DataTable(
                    id="ventas_sem_tbl", page_size=20, sort_action="native",
                    sort_mode="multi", filter_action="native",
                    style_table=TBL_TABLE, style_cell=TBL_CELL, style_header=TBL_HEADER,
                    style_data_conditional=[
                        {"if": {"row_index": "odd"}, "backgroundColor": "rgba(255,255,255,0.02)"},
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
                html.Div("Hacé doble click en la columna ✏️ Nota para agregar una justificación.", style={
                    "fontSize": "11px", "color": "#475569", "fontFamily": FONT,
                    "marginBottom": "10px", "fontStyle": "italic",
                }),
                dash_table.DataTable(
                    id="jornada_tbl",
                    page_size=15,
                    sort_action="native",
                    sort_mode="multi",
                    editable=True,
                    style_table=TBL_TABLE,
                    style_cell=TBL_CELL,
                    style_header=TBL_HEADER,
                    style_data_conditional=[
                        {"if": {"row_index": "odd"}, "backgroundColor": "rgba(255,255,255,0.02)"},
                        {"if": {"filter_query": "{hs_trab} < 8", "column_id": "hs_trab_hhmm"}, "backgroundColor": "rgba(239,68,68,0.12)", "color": "#fca5a5", "fontWeight": "700"},
                        {"if": {"filter_query": '{inicio_obj} = "✅"', "column_id": "inicio_obj"}, "color": "#4ade80", "fontWeight": "700", "fontSize": "16px"},
                        {"if": {"filter_query": '{inicio_obj} = "❌"', "column_id": "inicio_obj"}, "color": "#f87171", "fontWeight": "700", "fontSize": "16px"},
                        {"if": {"filter_query": '{inicio_obj} = "—"', "column_id": "inicio_obj"}, "color": "#64748b"},
                        {"if": {"column_id": "Nota"}, "backgroundColor": "rgba(59,130,246,0.06)", "color": "#93c5fd", "fontStyle": "italic"},
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
            html.Div(
                style={"display": "flex", "justifyContent": "space-between", "alignItems": "center", "marginBottom": "4px"},
                children=[
                    html.Div(id="ranking_periodo_label", style={"fontSize": "12px", "color": "#64748b", "fontFamily": FONT}),
                    html.Div(style={"display": "flex", "gap": "10px", "alignItems": "center"}, children=[
                        html.Div(id="telegram_status_msg", style={"fontSize": "11px", "color": "#64748b", "fontFamily": FONT}),
                        html.Button("📨  Enviar por Telegram", id="btn_enviar_telegram", n_clicks=0, style={
                            "height": "36px", "cursor": "pointer",
                            "background": "linear-gradient(135deg, #1d3566 0%, #1e4080 100%)",
                            "color": "#93c5fd", "border": "1px solid rgba(59,130,246,0.4)",
                            "borderRadius": "10px", "padding": "0 16px",
                            "fontWeight": "600", "fontSize": "12px", "fontFamily": FONT,
                        }),
                        html.Button("📋  Resumen a Supervisores", id="btn_enviar_supervisores", n_clicks=0, style={
                            "height": "36px", "cursor": "pointer",
                            "background": "linear-gradient(135deg, #5b21b6 0%, #6d28d9 100%)",
                            "color": "#ddd6fe", "border": "1px solid rgba(139,92,246,0.4)",
                            "borderRadius": "10px", "padding": "0 16px",
                            "fontWeight": "600", "fontSize": "12px", "fontFamily": FONT,
                        }),
                        html.Button("⬇  Descargar Objetivos (Excel)", id="btn_download_objetivos", n_clicks=0, style={
                            "height": "36px", "cursor": "pointer",
                            "background": "linear-gradient(135deg, #14532d 0%, #166534 100%)",
                            "color": "#86efac", "border": "1px solid rgba(34,197,94,0.35)",
                            "borderRadius": "10px", "padding": "0 16px",
                            "fontWeight": "600", "fontSize": "12px", "fontFamily": FONT,
                        }),
                    ]),
                ],
            ),
            html.Div(
                "💡 Si elegís un vendedor en el filtro de arriba, el envío por Telegram va solo a esa persona. Si lo dejás vacío, va a todos.",
                style={"fontSize": "11px", "color": "#475569", "fontFamily": FONT, "fontStyle": "italic", "marginBottom": "12px"},
            ),
            html.Div(
                style={
                    "display": "flex", "alignItems": "center", "gap": "10px",
                    "marginBottom": "20px", "backgroundColor": "#161b27",
                    "border": "1px solid rgba(255,255,255,0.07)", "borderRadius": "12px",
                    "padding": "10px 14px",
                },
                children=[
                    html.Div("🔓 Resetear registro Telegram:", style={"fontSize": "12px", "color": "#94a3b8", "fontFamily": FONT, "whiteSpace": "nowrap"}),
                    dcc.Dropdown(
                        id="f_reset_telegram_usuario",
                        options=[], value=None, clearable=True,
                        placeholder="Elegí a quién resetear...",
                        style={**DROPDOWN_STYLE, "minWidth": "260px", "flex": "1"},
                    ),
                    html.Button("Resetear", id="btn_reset_telegram", n_clicks=0, style={
                        "height": "36px", "cursor": "pointer",
                        "background": "linear-gradient(135deg, #7c2d12 0%, #9a3412 100%)",
                        "color": "#fed7aa", "border": "1px solid rgba(249,115,22,0.4)",
                        "borderRadius": "10px", "padding": "0 16px",
                        "fontWeight": "600", "fontSize": "12px", "fontFamily": FONT,
                        "whiteSpace": "nowrap",
                    }),
                    html.Div(id="reset_telegram_status_msg", style={"fontSize": "11px", "color": "#64748b", "fontFamily": FONT}),
                ],
            ),
            dcc.Download(id="download_objetivos_excel"),

            html.Div([
                filter_label("Ver ranking"),
                dcc.Dropdown(
                    id="f_ranking_tipo",
                    options=[
                        {"label": "🏆  Mejores Vendedores",         "value": "mejores"},
                        {"label": "💀  Peores Vendedores",          "value": "peores"},
                        {"label": "📈  Mejoraron vs Mes Anterior",  "value": "mejoraron"},
                        {"label": "📉  Empeoraron vs Mes Anterior", "value": "empeoraron"},
                        {"label": "👥  Clientes Inactivos",         "value": "inactivos"},
                        {"label": "🚬  Objetivo Corona",            "value": "corona"},
                        {"label": "🍬  Objetivo Pier & Roll",       "value": "pier_roll"},
                        {"label": "🗺️  Objetivo Cobertura",         "value": "cobertura"},
                    ],
                    value="mejores", clearable=False,
                    style={**DROPDOWN_STYLE, "maxWidth": "360px"},
                ),
            ], style={"marginBottom": "20px"}),

            html.Div(id="rank_wrap_mejores", style={"display": "block"}, children=[
                _rank_section("🏆", "Mejores Vendedores", "#fbbf24", "tbl_mejores"),
            ]),
            html.Div(id="rank_wrap_peores", style={"display": "none"}, children=[
                _rank_section("💀", "Peores Vendedores", "#f87171", "tbl_peores"),
            ]),
            html.Div(id="rank_wrap_mejoraron", style={"display": "none"}, children=[
                _rank_section("📈", "Mejoraron vs Mes Anterior", "#4ade80", "tbl_mejoraron"),
            ]),
            html.Div(id="rank_wrap_empeoraron", style={"display": "none"}, children=[
                _rank_section("📉", "Empeoraron vs Mes Anterior", "#f87171", "tbl_empeoraron"),
            ]),
            html.Div(id="rank_wrap_inactivos", style={"display": "none"}, children=[
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
            ]),
            html.Div(id="rank_wrap_corona", style={"display": "none"}, children=[
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
                ], {"marginBottom": "24px"}),
            ]),
            html.Div(id="rank_wrap_pier_roll", style={"display": "none"}, children=[
                html.Div(style={"display": "flex", "alignItems": "center", "gap": "10px", "marginBottom": "12px"},
                         children=[html.Span("🍬", style={"fontSize": "20px"}),
                                   section_title("Objetivo Pier & Roll — Cumplimiento por Vendedor (20 u./mes, sin bonificado 100%)", style={"color": "#a78bfa", "marginBottom": "0", "fontSize": "14px"})]),
                panel([
                    dash_table.DataTable(
                        id="tbl_pier_roll", page_size=30, sort_action="native", sort_mode="multi",
                        style_table=TBL_TABLE, style_cell=TBL_CELL, style_header=TBL_HEADER,
                        style_data_conditional=[
                            {"if": {"row_index": "odd"}, "backgroundColor": "rgba(255,255,255,0.02)"},
                            {"if": {"filter_query": '{Cumple} = "✅"', "column_id": "Cumple"}, "color": "#4ade80", "fontWeight": "700", "fontSize": "16px"},
                            {"if": {"filter_query": '{Cumple} = "❌"', "column_id": "Cumple"}, "color": "#f87171", "fontWeight": "700", "fontSize": "16px"},
                            {"if": {"column_id": "% Cumpl. Actual"}, "fontWeight": "700", "color": "#fbbf24"},
                            {"if": {"column_id": "Pier & Roll Vendido"}, "color": "#a78bfa"},
                            {"if": {"column_id": "Vendedor"},        "textAlign": "left", "fontWeight": "600", "color": "#e2e8f0"},
                            {"if": {"column_id": "Pos."},            "fontWeight": "700", "color": "#7ea3c4", "width": "40px"},
                            {"if": {"state": "selected"}, "backgroundColor": "rgba(59,130,246,0.15)", "border": "1px solid rgba(59,130,246,0.4)"},
                        ],
                    ),
                ], {"marginBottom": "24px"}),
            ]),
            html.Div(id="rank_wrap_cobertura", style={"display": "none"}, children=[
                html.Div(style={"display": "flex", "alignItems": "center", "gap": "10px", "marginBottom": "12px"},
                         children=[html.Span("🗺️", style={"fontSize": "20px"}),
                                   section_title(f"Objetivo Cobertura — Cumplimiento por Vendedor (mínimo {COBERTURA_OBJETIVO_PCT:.0f}% de clientes visitados)", style={"color": "#38bdf8", "marginBottom": "0", "fontSize": "14px"})]),
                panel([
                    dash_table.DataTable(
                        id="tbl_cobertura", page_size=30, sort_action="native", sort_mode="multi",
                        style_table=TBL_TABLE, style_cell=TBL_CELL, style_header=TBL_HEADER,
                        style_data_conditional=[
                            {"if": {"row_index": "odd"}, "backgroundColor": "rgba(255,255,255,0.02)"},
                            {"if": {"filter_query": '{Cumple} = "✅"', "column_id": "Cumple"}, "color": "#4ade80", "fontWeight": "700", "fontSize": "16px"},
                            {"if": {"filter_query": '{Cumple} = "❌"', "column_id": "Cumple"}, "color": "#f87171", "fontWeight": "700", "fontSize": "16px"},
                            {"if": {"column_id": "% Cobertura Actual"}, "fontWeight": "700", "color": "#fbbf24"},
                            {"if": {"column_id": "Visitados"},       "color": "#38bdf8"},
                            {"if": {"column_id": "Planificados"},    "color": "#94a3b8"},
                            {"if": {"column_id": "Vendedor"},        "textAlign": "left", "fontWeight": "600", "color": "#e2e8f0"},
                            {"if": {"column_id": "Pos."},            "fontWeight": "700", "color": "#7ea3c4", "width": "40px"},
                            {"if": {"state": "selected"}, "backgroundColor": "rgba(59,130,246,0.15)", "border": "1px solid rgba(59,130,246,0.4)"},
                        ],
                    ),
                ], {"marginBottom": "40px"}),
            ]),
        ]),
    ])


def _tab_mapa():
    return dcc.Tab(label="🗺️  Mapa", value="tab_mapa", children=[
        html.Div(style={"marginTop": "20px"}, children=[
            html.Div(
                "💡 Mapa de todas las visitas (con y sin venta). Usá los filtros de Año/Mes/Semana/Vendedor "
                "de arriba, más los de acá abajo, para acotar. El color de cada punto indica si hubo venta "
                "o cuál fue el motivo de no venta.",
                style={"fontSize": "11px", "color": "#475569", "fontFamily": FONT, "fontStyle": "italic", "marginBottom": "16px"},
            ),
            html.Div(
                style={"display": "flex", "gap": "16px", "flexWrap": "wrap", "alignItems": "flex-end", "marginBottom": "12px"},
                children=[
                    html.Div([
                        filter_label("Filtrar por motivo / venta"),
                        dcc.Dropdown(
                            id="f_motivos_mapa", options=[], value=[], multi=True, clearable=True,
                            placeholder="Todos (venta + motivos + no visitado)",
                            style={**DROPDOWN_STYLE, "minWidth": "340px"},
                        ),
                    ]),
                    html.Div([
                        filter_label("Filtrar por día de ruta"),
                        dcc.Dropdown(
                            id="f_ruta_mapa",
                            options=[
                                {"label": "Lunes",     "value": "LUNES"},
                                {"label": "Martes",    "value": "MARTES"},
                                {"label": "Miércoles", "value": "MIERCOLES"},
                                {"label": "Jueves",    "value": "JUEVES"},
                                {"label": "Viernes",   "value": "VIERNES"},
                            ],
                            value=[], multi=True, clearable=True,
                            placeholder="Todos los días",
                            style={**DROPDOWN_STYLE, "minWidth": "260px"},
                        ),
                    ]),
                ],
            ),
            html.Div(id="mapa_kpi_label", style={"fontSize": "12px", "color": "#94a3b8", "fontFamily": FONT, "marginBottom": "10px"}),
            panel([
                html.Div(
                    id="mapa_google_container",
                    style={"height": "650px", "width": "100%", "borderRadius": "12px", "overflow": "hidden"},
                ),
                dcc.Store(id="mapa_google_data"),
                html.Div(id="mapa_google_dummy_output", style={"display": "none"}),
            ]),

            html.Div(style={"marginTop": "24px"}),
            html.Div(
                "💡 Resumen rápido de todos los vendedores a la vez (usa los filtros de Año/Mes/Semana de "
                "arriba, sin importar el vendedor elegido) — para no tener que entrar uno por uno al mapa.",
                style={"fontSize": "11px", "color": "#475569", "fontFamily": FONT, "fontStyle": "italic", "marginBottom": "12px"},
            ),
            section_title("Resumen por vendedor — todos juntos", style={"color": "#e2e8f0", "marginBottom": "8px", "fontSize": "14px"}),
            panel([
                dash_table.DataTable(
                    id="mapa_resumen_tbl", page_size=30, sort_action="native", sort_mode="multi",
                    style_table=TBL_TABLE, style_cell=TBL_CELL, style_header=TBL_HEADER,
                    style_data_conditional=[
                        {"if": {"row_index": "odd"}, "backgroundColor": "rgba(255,255,255,0.02)"},
                        {"if": {"column_id": "Vendedor"}, "textAlign": "left", "fontWeight": "600", "color": "#e2e8f0"},
                        {"if": {"column_id": "Clientes con venta"}, "color": "#4ade80", "fontWeight": "700"},
                        {"if": {"column_id": "Inactivos"}, "color": "#f43f5e", "fontWeight": "700"},
                        {"if": {"column_id": "Nunca visitado"}, "color": "#f87171"},
                    ],
                ),
            ], {"marginBottom": "40px"}),
        ]),
    ])


def _tab_gastos():
    return dcc.Tab(label="💰  Gastos", value="tab_gastos", children=[
        html.Div(style={"marginTop": "20px"}, children=[
            html.Div(
                "💡 Acá cargás cuánto viático corresponde por salir con cada vendedor, y el sistema calcula "
                "solo lo que ya gastaron los supervisores (días ya pasados de su Planificación), cruzando "
                "con quién salieron realmente cada día.",
                style={"fontSize": "11px", "color": "#475569", "fontFamily": FONT, "fontStyle": "italic", "marginBottom": "20px"},
            ),

            html.Div(style={"display": "flex", "alignItems": "center", "gap": "10px", "marginBottom": "12px"},
                     children=[html.Span("🚗", style={"fontSize": "20px"}),
                               section_title("Viáticos por vendedor", style={"color": "#a78bfa", "marginBottom": "0", "fontSize": "14px"})]),
            panel([
                html.Div(
                    style={"display": "flex", "gap": "16px", "flexWrap": "wrap", "alignItems": "flex-end", "marginBottom": "16px"},
                    children=[
                        html.Div([
                            filter_label("Vendedor"),
                            dcc.Dropdown(
                                id="gastos_vendedor", options=[], value=None, clearable=True,
                                placeholder="Elegí un vendedor...",
                                className="filtro-ancho",
                                style={**DROPDOWN_STYLE, "minWidth": "280px"},
                            ),
                        ], style={"flex": "1", "minWidth": "280px"}),
                        html.Div([
                            filter_label("Monto del viático ($)"),
                            dcc.Input(
                                id="gastos_monto", type="number", min=0, step=100,
                                placeholder="Ej: 1500",
                                style={
                                    "backgroundColor": "#0d1117", "color": "#e2e8f0",
                                    "border": "1px solid rgba(255,255,255,0.1)", "borderRadius": "10px",
                                    "padding": "9px 12px", "fontFamily": FONT, "fontSize": "13px",
                                    "height": "38px", "width": "160px",
                                },
                            ),
                        ]),
                        html.Button("💾  Guardar", id="btn_gastos_guardar", n_clicks=0, style={
                            "height": "38px", "cursor": "pointer",
                            "background": "linear-gradient(135deg, #14532d 0%, #166534 100%)",
                            "color": "#86efac", "border": "1px solid rgba(34,197,94,0.35)",
                            "borderRadius": "10px", "padding": "0 18px",
                            "fontWeight": "600", "fontSize": "13px", "fontFamily": FONT,
                        }),
                    ],
                ),
                html.Div(id="gastos_status_msg", style={"fontSize": "12px", "fontFamily": FONT, "marginBottom": "12px"}),
                html.Div(
                    "Para sacarle el viático a un vendedor, hacé click en la ✕ que aparece a la izquierda de la fila.",
                    style={"fontSize": "11px", "color": "#475569", "fontFamily": FONT, "fontStyle": "italic", "marginBottom": "10px"},
                ),
                dash_table.DataTable(
                    id="gastos_tbl_viaticos",
                    row_deletable=True,
                    page_size=15,
                    columns=[
                        {"name": "Vendedor",           "id": "vendedor"},
                        {"name": "Viático",            "id": "monto_fmt"},
                    ],
                    style_table=TBL_TABLE, style_cell=TBL_CELL, style_header=TBL_HEADER,
                    style_data_conditional=[
                        {"if": {"row_index": "odd"}, "backgroundColor": "rgba(255,255,255,0.02)"},
                        {"if": {"column_id": "vendedor"}, "fontWeight": "600", "color": "#e2e8f0", "textAlign": "left"},
                        {"if": {"column_id": "monto_fmt"}, "color": "#4ade80", "fontWeight": "700"},
                    ],
                ),
            ], {"marginBottom": "28px"}),

            dcc.Store(id="gastos_ids_store", data=[]),

            html.Div(
                style={"display": "flex", "alignItems": "center", "gap": "14px", "marginBottom": "14px"},
                children=[
                    html.Button("←", id="btn_gastos_mes_anterior", n_clicks=0, style={
                        "height": "32px", "width": "32px", "cursor": "pointer",
                        "background": "#161b27", "color": "#94a3b8",
                        "border": "1px solid rgba(255,255,255,0.1)", "borderRadius": "8px",
                        "fontSize": "16px", "fontFamily": FONT,
                    }),
                    html.Div(id="gastos_mes_label", style={
                        "fontSize": "15px", "fontWeight": "700", "color": "#e2e8f0",
                        "fontFamily": FONT, "minWidth": "160px", "textAlign": "center",
                    }),
                    html.Button("→", id="btn_gastos_mes_siguiente", n_clicks=0, style={
                        "height": "32px", "width": "32px", "cursor": "pointer",
                        "background": "#161b27", "color": "#94a3b8",
                        "border": "1px solid rgba(255,255,255,0.1)", "borderRadius": "8px",
                        "fontSize": "16px", "fontFamily": FONT,
                    }),
                ],
            ),
            dcc.Store(id="gastos_mes_store", data=None),

            html.Div(style={"display": "flex", "alignItems": "center", "gap": "10px", "marginBottom": "12px"},
                     children=[html.Span("📊", style={"fontSize": "20px"}),
                               section_title("Resumen por supervisor", style={"color": "#fbbf24", "marginBottom": "0", "fontSize": "14px"})]),
            panel([
                html.Div(id="gastos_resumen_cards"),
            ], {"marginBottom": "28px"}),

            html.Div(style={"display": "flex", "alignItems": "center", "gap": "10px", "marginBottom": "12px"},
                     children=[html.Span("📋", style={"fontSize": "20px"}),
                               section_title("Detalle día por día", style={"color": "#94a3b8", "marginBottom": "0", "fontSize": "14px"})]),
            panel([
                dash_table.DataTable(
                    id="gastos_tbl_detalle", page_size=30, sort_action="native", sort_mode="multi",
                    filter_action="native",
                    columns=[
                        {"name": "Supervisor", "id": "supervisor"},
                        {"name": "Fecha",      "id": "fecha"},
                        {"name": "Vendedor",   "id": "vendedor"},
                        {"name": "Monto",      "id": "monto_fmt"},
                    ],
                    style_table=TBL_TABLE, style_cell=TBL_CELL, style_header=TBL_HEADER,
                    style_data_conditional=[
                        {"if": {"row_index": "odd"}, "backgroundColor": "rgba(255,255,255,0.02)"},
                        {"if": {"column_id": "monto_fmt"}, "color": "#4ade80", "fontWeight": "700"},
                        {"if": {"column_id": "supervisor"}, "fontWeight": "700", "color": "#7ea3c4"},
                    ],
                ),
            ], {"marginBottom": "40px"}),

            html.Hr(style={"border": "none", "borderTop": "1px solid rgba(255,255,255,0.08)", "margin": "8px 0 32px"}),

            html.Div(
                "💡 Liquidación de vendedores: cada uno tiene un monto fijo por día hábil trabajado. "
                "A fin de mes, marcá acá los días que NO salió — esos días se descuentan del total a pagar. "
                "Cuenta Lunes a Sábado del mes elegido arriba (mismo selector de mes que el resumen de supervisores).",
                style={"fontSize": "11px", "color": "#475569", "fontFamily": FONT, "fontStyle": "italic", "marginBottom": "20px"},
            ),

            dcc.Store(id="pagos_montos_ids_store", data=[]),

            html.Div(style={"display": "flex", "alignItems": "center", "gap": "10px", "marginBottom": "12px"},
                     children=[html.Span("📅", style={"fontSize": "20px"}),
                               section_title("Marcar días que NO salió (por vendedor)", style={"color": "#f87171", "marginBottom": "0", "fontSize": "14px"})]),
            panel([
                html.Div([
                    filter_label("Vendedor a marcar"),
                    dcc.Dropdown(
                        id="pagos_vend_ausencias", options=[], value=None, clearable=True,
                        placeholder="Elegí un vendedor...",
                        className="filtro-ancho",
                        style={**DROPDOWN_STYLE, "minWidth": "280px", "marginBottom": "16px"},
                    ),
                ]),
                html.Div(
                    "Tildá los días hábiles en que NO salió este vendedor durante el mes elegido arriba. "
                    "Los que queden sin tildar se pagan normal.",
                    style={"fontSize": "11px", "color": "#475569", "fontFamily": FONT, "fontStyle": "italic", "marginBottom": "12px"},
                ),
                dcc.Checklist(
                    id="pagos_ausencias_checklist",
                    options=[], value=[],
                    style={"color": "#e2e8f0", "fontFamily": FONT, "fontSize": "13px"},
                    labelStyle={
                        "display": "inline-block", "width": "110px", "marginBottom": "8px",
                        "backgroundColor": "#161b27", "border": "1px solid rgba(255,255,255,0.07)",
                        "borderRadius": "8px", "padding": "6px 10px", "marginRight": "8px",
                    },
                ),
                html.Div(
                    html.Button("💾  Guardar ausencias de este vendedor", id="btn_pagos_ausencias_guardar", n_clicks=0, style={
                        "height": "38px", "cursor": "pointer",
                        "background": "linear-gradient(135deg, #7c2d12 0%, #9a3412 100%)",
                        "color": "#fed7aa", "border": "1px solid rgba(249,115,22,0.4)",
                        "borderRadius": "10px", "padding": "0 18px",
                        "fontWeight": "600", "fontSize": "13px", "fontFamily": FONT, "marginTop": "12px",
                    }),
                ),
                html.Div(id="pagos_ausencias_status_msg", style={"fontSize": "12px", "fontFamily": FONT, "marginTop": "10px"}),
            ], {"marginBottom": "28px"}),

            html.Div(style={"display": "flex", "alignItems": "center", "gap": "10px", "marginBottom": "12px"},
                     children=[html.Span("🧾", style={"fontSize": "20px"}),
                               section_title("Liquidación del mes — todos los vendedores", style={"color": "#fbbf24", "marginBottom": "0", "fontSize": "14px"})]),
            panel([
                dash_table.DataTable(
                    id="pagos_tbl_liquidacion", page_size=30, sort_action="native", sort_mode="multi",
                    filter_action="native",
                    columns=[
                        {"name": "Vendedor",       "id": "vendedor"},
                        {"name": "Días hábiles",   "id": "dias_habiles"},
                        {"name": "Días ausente",   "id": "dias_ausente"},
                        {"name": "Días pagados",   "id": "dias_pagados"},
                        {"name": "Monto/día",      "id": "monto_diario_fmt"},
                        {"name": "Total a cobrar", "id": "total_fmt"},
                    ],
                    style_table=TBL_TABLE, style_cell=TBL_CELL, style_header=TBL_HEADER,
                    style_data_conditional=[
                        {"if": {"row_index": "odd"}, "backgroundColor": "rgba(255,255,255,0.02)"},
                        {"if": {"column_id": "vendedor"}, "fontWeight": "600", "color": "#e2e8f0", "textAlign": "left"},
                        {"if": {"column_id": "dias_ausente"}, "color": "#f87171", "fontWeight": "700"},
                        {"if": {"column_id": "total_fmt"}, "color": "#4ade80", "fontWeight": "700"},
                    ],
                ),
            ], {"marginBottom": "40px"}),

            html.Hr(style={"border": "none", "borderTop": "1px solid rgba(255,255,255,0.08)", "margin": "8px 0 32px"}),

            html.Div(
                "💡 Combustible por ruta: cargá los km que recorre cada vendedor por día de la semana. "
                "La tabla se completa sola con lo del mes anterior — solo editá lo que cambió y guardá. "
                "Descuenta automáticamente los días marcados como ausencia arriba. Usa el mismo selector de mes.",
                style={"fontSize": "11px", "color": "#475569", "fontFamily": FONT, "fontStyle": "italic", "marginBottom": "20px"},
            ),

            html.Div(style={"display": "flex", "alignItems": "center", "gap": "10px", "marginBottom": "12px"},
                     children=[html.Span("⛽", style={"fontSize": "20px"}),
                               section_title("Precio de la nafta", style={"color": "#f59e0b", "marginBottom": "0", "fontSize": "14px"})]),
            panel([
                html.Div(
                    style={"display": "flex", "gap": "16px", "flexWrap": "wrap", "alignItems": "flex-end", "marginBottom": "12px"},
                    children=[
                        html.Div([
                            filter_label("Precio por km ($)"),
                            dcc.Input(
                                id="combustible_precio_input", type="number", min=0, step=1,
                                placeholder="Ej: 203",
                                style={
                                    "backgroundColor": "#0d1117", "color": "#e2e8f0",
                                    "border": "1px solid rgba(255,255,255,0.1)", "borderRadius": "10px",
                                    "padding": "9px 12px", "fontFamily": FONT, "fontSize": "13px",
                                    "height": "38px", "width": "160px",
                                },
                            ),
                        ]),
                        html.Button("💾  Guardar precio del mes", id="btn_combustible_precio_guardar", n_clicks=0, style={
                            "height": "38px", "cursor": "pointer",
                            "background": "linear-gradient(135deg, #14532d 0%, #166534 100%)",
                            "color": "#86efac", "border": "1px solid rgba(34,197,94,0.35)",
                            "borderRadius": "10px", "padding": "0 18px",
                            "fontWeight": "600", "fontSize": "13px", "fontFamily": FONT,
                        }),
                    ],
                ),
                html.Div(id="combustible_precio_status_msg", style={"fontSize": "12px", "fontFamily": FONT}),
            ], {"marginBottom": "28px"}),

            html.Div(style={"display": "flex", "alignItems": "center", "gap": "10px", "marginBottom": "12px"},
                     children=[html.Span("🗺️", style={"fontSize": "20px"}),
                               section_title("Kms de ruta por vendedor y día", style={"color": "#38bdf8", "marginBottom": "0", "fontSize": "14px"})]),
            panel([
                html.Div(
                    "Editá los km directamente en la tabla (día vacío = no hace ruta ese día) y tocá Guardar. "
                    "Se precarga sola con lo del mes anterior la primera vez que abrís cada mes.",
                    style={"fontSize": "11px", "color": "#475569", "fontFamily": FONT, "fontStyle": "italic", "marginBottom": "12px"},
                ),
                dash_table.DataTable(
                    id="combustible_tbl_rutas",
                    editable=True,
                    page_size=30,
                    columns=[
                        {"name": "Vendedor",  "id": "vendedor", "editable": False},
                        {"name": "Lunes",     "id": "lunes",     "type": "numeric"},
                        {"name": "Martes",    "id": "martes",    "type": "numeric"},
                        {"name": "Miércoles", "id": "miercoles", "type": "numeric"},
                        {"name": "Jueves",    "id": "jueves",    "type": "numeric"},
                        {"name": "Viernes",   "id": "viernes",   "type": "numeric"},
                        {"name": "Sábado",    "id": "sabado",    "type": "numeric"},
                    ],
                    style_table=TBL_TABLE, style_cell=TBL_CELL, style_header=TBL_HEADER,
                    style_data_conditional=[
                        {"if": {"row_index": "odd"}, "backgroundColor": "rgba(255,255,255,0.02)"},
                        {"if": {"column_id": "vendedor"}, "fontWeight": "600", "color": "#e2e8f0", "textAlign": "left"},
                    ],
                ),
                html.Div(
                    html.Button("💾  Guardar rutas", id="btn_combustible_ruta_guardar", n_clicks=0, style={
                        "height": "38px", "cursor": "pointer",
                        "background": "linear-gradient(135deg, #14532d 0%, #166534 100%)",
                        "color": "#86efac", "border": "1px solid rgba(34,197,94,0.35)",
                        "borderRadius": "10px", "padding": "0 18px",
                        "fontWeight": "600", "fontSize": "13px", "fontFamily": FONT, "marginTop": "14px",
                    }),
                ),
                html.Div(id="combustible_ruta_status_msg", style={"fontSize": "12px", "fontFamily": FONT, "marginTop": "10px"}),
            ], {"marginBottom": "28px"}),

            html.Div(style={"display": "flex", "justifyContent": "space-between", "alignItems": "center", "marginBottom": "12px"},
                     children=[
                         html.Div(style={"display": "flex", "alignItems": "center", "gap": "10px"},
                                  children=[html.Span("🧾", style={"fontSize": "20px"}),
                                            section_title("Liquidación de combustible del mes", style={"color": "#fbbf24", "marginBottom": "0", "fontSize": "14px"})]),
                         html.Button("⬇  Descargar Excel", id="btn_download_combustible", n_clicks=0, style={
                             "height": "36px", "cursor": "pointer",
                             "background": "linear-gradient(135deg, #14532d 0%, #166534 100%)",
                             "color": "#86efac", "border": "1px solid rgba(34,197,94,0.35)",
                             "borderRadius": "10px", "padding": "0 16px",
                             "fontWeight": "600", "fontSize": "12px", "fontFamily": FONT,
                         }),
                     ]),
            dcc.Download(id="download_combustible_excel"),
            panel([
                dash_table.DataTable(
                    id="combustible_tbl_liquidacion", page_size=30, sort_action="native", sort_mode="multi",
                    filter_action="native",
                    columns=[
                        {"name": "Vendedor",                  "id": "vendedor"},
                        {"name": "Kms totales",                "id": "kms_totales"},
                        {"name": "Días ausente descontados",   "id": "dias_ausente_descontados"},
                        {"name": "Precio nafta",               "id": "precio_nafta_fmt"},
                        {"name": "Total a liquidar",           "id": "total_fmt"},
                    ],
                    style_table=TBL_TABLE, style_cell=TBL_CELL, style_header=TBL_HEADER,
                    style_data_conditional=[
                        {"if": {"row_index": "odd"}, "backgroundColor": "rgba(255,255,255,0.02)"},
                        {"if": {"column_id": "vendedor"}, "fontWeight": "600", "color": "#e2e8f0", "textAlign": "left"},
                        {"if": {"column_id": "dias_ausente_descontados"}, "color": "#f87171", "fontWeight": "700"},
                        {"if": {"column_id": "total_fmt"}, "color": "#4ade80", "fontWeight": "700"},
                    ],
                ),
            ], {"marginBottom": "40px"}),
        ]),
    ])


def _tab_planificacion():
    return dcc.Tab(label="🗓️  Planificación", value="tab_planificacion", children=[
        html.Div(style={"marginTop": "20px"}, children=[
            # Stores internos (no se ven, solo coordinan los callbacks)
            dcc.Store(id="planif_refresh_trg", data=0),
            dcc.Store(id="planif_ids_store", data=[]),

            html.Div(
                "💡 Este es tu calendario personal: elegí un día, opcionalmente un vendedor de tu equipo, "
                "y anotá qué vas a hacer (si el día es futuro) o qué hiciste (si ya pasó). "
                "Si no elegís vendedor, queda como una tarea general de ese día. "
                "Un mismo día puede tener varias entradas.",
                style={"fontSize": "11px", "color": "#475569", "fontFamily": FONT, "fontStyle": "italic", "marginBottom": "16px"},
            ),

            html.Div(style={"display": "flex", "alignItems": "center", "gap": "10px", "marginBottom": "12px"},
                     children=[html.Span("📊", style={"fontSize": "20px"}),
                               section_title("Con quién salieron esta semana", style={"color": "#a78bfa", "marginBottom": "0", "fontSize": "14px"})]),
            panel([
                html.Div(id="planif_resumen_equipo"),
            ], {"marginBottom": "24px"}),

            # Solo visible para el admin (martin): elegir de quién ver el calendario
            html.Div(
                id="planif_supervisor_wrapper",
                style={"display": "none", "maxWidth": "320px", "marginBottom": "16px"},
                children=[
                    filter_label("Ver calendario de"),
                    dcc.Dropdown(
                        id="planif_supervisor_ver", options=[], value=None, clearable=False,
                        style=DROPDOWN_STYLE,
                    ),
                ],
            ),
            html.Div(
                id="planif_modo_lectura_aviso",
                children="👁️ Estás viendo el calendario de otra persona en modo solo lectura.",
                style={"display": "none", "fontSize": "12px", "color": "#f59e0b", "fontFamily": FONT,
                       "fontStyle": "italic", "marginBottom": "16px"},
            ),

            # Calendario mensual — click en un día para seleccionarlo
            dcc.Store(id="planif_mes_store", data=None),
            html.Div(
                style={"display": "flex", "alignItems": "center", "gap": "14px", "marginBottom": "14px"},
                children=[
                    html.Button("←", id="btn_planif_mes_anterior", n_clicks=0, style={
                        "height": "32px", "width": "32px", "cursor": "pointer",
                        "background": "#161b27", "color": "#94a3b8",
                        "border": "1px solid rgba(255,255,255,0.1)", "borderRadius": "8px",
                        "fontSize": "16px", "fontFamily": FONT,
                    }),
                    html.Div(id="planif_mes_label", style={
                        "fontSize": "15px", "fontWeight": "700", "color": "#e2e8f0",
                        "fontFamily": FONT, "minWidth": "160px", "textAlign": "center",
                    }),
                    html.Button("→", id="btn_planif_mes_siguiente", n_clicks=0, style={
                        "height": "32px", "width": "32px", "cursor": "pointer",
                        "background": "#161b27", "color": "#94a3b8",
                        "border": "1px solid rgba(255,255,255,0.1)", "borderRadius": "8px",
                        "fontSize": "16px", "fontFamily": FONT,
                    }),
                ],
            ),
            panel([
                html.Div(id="planif_calendario_grid"),
            ], {"marginBottom": "20px"}),

            html.Div(
                style={"display": "flex", "gap": "16px", "flexWrap": "wrap", "alignItems": "flex-end", "marginBottom": "16px"},
                children=[
                    html.Div([
                        filter_label("Día"),
                        dcc.DatePickerSingle(
                            id="planif_fecha",
                            date=date.today().isoformat(),
                            display_format="DD/MM/YYYY",
                            first_day_of_week=1,
                        ),
                    ]),
                    html.Div([
                        filter_label("Seleccionado"),
                        html.Div(
                            id="planif_fecha_grande",
                            style={
                                "fontSize": "16px", "fontWeight": "800", "color": "#4ade80",
                                "fontFamily": FONT, "backgroundColor": "rgba(74,222,128,0.1)",
                                "border": "1px solid rgba(74,222,128,0.35)", "borderRadius": "10px",
                                "padding": "0 16px", "height": "38px", "display": "flex",
                                "alignItems": "center", "whiteSpace": "nowrap",
                            },
                        ),
                    ]),
                ],
            ),

            # Formulario de agregar — se oculta cuando estás viendo el calendario de otra persona
            html.Div(id="planif_form_wrapper", children=[
                html.Div(
                    style={"display": "flex", "gap": "16px", "flexWrap": "wrap", "alignItems": "flex-end", "marginBottom": "16px"},
                    children=[
                        html.Div([
                            filter_label("Vendedor"),
                            dcc.Dropdown(
                                id="planif_vendedor", options=[], value=None, clearable=True,
                                placeholder="Elegí un vendedor de tu equipo (opcional)...",
                                style={**DROPDOWN_STYLE, "minWidth": "280px"},
                            ),
                        ], style={"flex": "1", "minWidth": "280px"}),
                    ],
                ),

                html.Div([
                    filter_label("Motivo"),
                    dcc.Dropdown(
                        id="planif_motivo",
                        options=[
                            {"label": "Acompañamiento de ruta",         "value": "Acompañamiento de ruta"},
                            {"label": "Reunión de seguimiento",         "value": "Reunión de seguimiento"},
                            {"label": "Revisión de objetivos",          "value": "Revisión de objetivos"},
                            {"label": "Capacitación",                   "value": "Capacitación"},
                            {"label": "Entrega de material/mercadería", "value": "Entrega de material/mercadería"},
                            {"label": "Control de cobertura",           "value": "Control de cobertura"},
                            {"label": "Feedback de desempeño",          "value": "Feedback de desempeño"},
                            {"label": "Tarea administrativa",           "value": "Tarea administrativa"},
                            {"label": "✏️ Otro (personalizado, escribir abajo)", "value": "__otro__"},
                        ],
                        value=None, clearable=True, multi=True,
                        placeholder="Elegí uno o varios motivos, o dejalo vacío y escribí todo abajo...",
                        style={**DROPDOWN_STYLE, "marginBottom": "8px"},
                    ),
                ], style={"marginBottom": "12px"}),

                html.Div([
                    filter_label("Detalle"),
                    html.Div(
                        id="planif_nota_ayuda",
                        children="Si elegiste un motivo arriba, esto es opcional (se suma como detalle extra). "
                                 "Si elegiste \"Otro\" o no elegiste ningún motivo, escribí acá directamente.",
                        style={"fontSize": "11px", "color": "#475569", "fontFamily": FONT, "fontStyle": "italic", "marginBottom": "6px"},
                    ),
                    dcc.Textarea(
                        id="planif_nota", value="", placeholder="Escribí acá...",
                        style={
                            "width": "100%", "minHeight": "80px", "backgroundColor": "#0d1117",
                            "color": "#e2e8f0", "border": "1px solid rgba(255,255,255,0.1)",
                            "borderRadius": "10px", "padding": "10px", "fontFamily": FONT,
                            "fontSize": "13px", "resize": "vertical",
                        },
                    ),
                ], style={"marginBottom": "12px"}),

                html.Div(
                    style={"display": "flex", "alignItems": "center", "gap": "12px", "marginBottom": "28px"},
                    children=[
                        html.Button("+  Agregar entrada", id="btn_planif_agregar", n_clicks=0, style={
                            "height": "38px", "cursor": "pointer",
                            "background": "linear-gradient(135deg, #14532d 0%, #166534 100%)",
                            "color": "#86efac", "border": "1px solid rgba(34,197,94,0.35)",
                            "borderRadius": "10px", "padding": "0 18px",
                            "fontWeight": "600", "fontSize": "13px", "fontFamily": FONT,
                        }),
                        html.Div(id="planif_agregar_status", style={
                            "fontSize": "12px", "fontFamily": FONT,
                        }),
                    ],
                ),
            ]),

            html.Div(style={"display": "flex", "alignItems": "center", "gap": "10px", "marginBottom": "12px"},
                     children=[html.Span("📌", style={"fontSize": "20px"}),
                               section_title("Entradas de ese día", style={"color": "#4ade80", "marginBottom": "0", "fontSize": "14px"}),
                               html.Div(id="planif_dia_seleccionado_label", style={
                                   "fontSize": "13px", "color": "#94a3b8", "fontFamily": FONT, "fontWeight": "600",
                               })]),
            html.Div(
                "Para borrar una entrada, hacé click en la ✕ que aparece a la izquierda de la fila.",
                style={"fontSize": "11px", "color": "#475569", "fontFamily": FONT, "fontStyle": "italic", "marginBottom": "10px"},
            ),
            panel([
                dash_table.DataTable(
                    id="planif_tbl_dia",
                    row_deletable=True,
                    page_size=15,
                    columns=[
                        {"name": "Vendedor", "id": "vendedor"},
                        {"name": "Nota",     "id": "nota"},
                    ],
                    style_table=TBL_TABLE, style_cell=TBL_CELL, style_header=TBL_HEADER,
                    style_data_conditional=[
                        {"if": {"row_index": "odd"}, "backgroundColor": "rgba(255,255,255,0.02)"},
                        {"if": {"column_id": "vendedor"}, "fontWeight": "600", "color": "#e2e8f0"},
                    ],
                ),
            ], {"marginBottom": "28px"}),

            html.Div(style={"display": "flex", "alignItems": "center", "gap": "10px", "marginBottom": "12px"},
                     children=[html.Span("📅", style={"fontSize": "20px"}),
                               section_title("Resumen de la semana (Lunes a Domingo)", style={"color": "#94a3b8", "marginBottom": "0", "fontSize": "14px"})]),
            panel([
                dash_table.DataTable(
                    id="planif_tbl_semana",
                    page_size=30,
                    columns=[
                        {"name": "Día",      "id": "dia_semana"},
                        {"name": "Fecha",    "id": "fecha_corta"},
                        {"name": "Vendedor", "id": "vendedor"},
                        {"name": "Nota",     "id": "nota"},
                    ],
                    style_table=TBL_TABLE, style_cell=TBL_CELL, style_header=TBL_HEADER,
                    style_data_conditional=[
                        {"if": {"row_index": "odd"}, "backgroundColor": "rgba(255,255,255,0.02)"},
                        {"if": {"column_id": "dia_semana"}, "fontWeight": "700", "color": "#7ea3c4"},
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
                    html.Div([filter_label("Año"),      dcc.Dropdown(id="f_year",  options=[], value=None, clearable=True, style=DROPDOWN_STYLE)]),
                    html.Div([filter_label("Mes"),      dcc.Dropdown(id="f_month", options=[{"label": f"{m:02d}", "value": m} for m in range(1, 13)], value=date.today().month, clearable=True, style=DROPDOWN_STYLE)]),
                    html.Div([filter_label("Semana"),   dcc.Dropdown(id="f_week",  options=[], value=None, clearable=True, style=DROPDOWN_STYLE)]),
                    html.Div([filter_label("Vendedor"), dcc.Dropdown(id="f_vend",  options=[], value=None, clearable=True, style=DROPDOWN_STYLE)]),
                ],
            ),
            html.Div(id="tabs_container"),
        ],
    )