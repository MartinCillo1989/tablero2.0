from dash import html, dcc, dash_table

from config import FONT
from ui.styles import TBL_CELL, TBL_HEADER, TBL_TABLE, RANKING_CONDITIONAL


def panel(children, extra_style=None):
    base = {
        "backgroundColor": "#161b27",
        "border": "1px solid rgba(255,255,255,0.07)",
        "borderRadius": "16px",
        "padding": "20px 24px",
        "boxShadow": "0 8px 32px rgba(0,0,0,0.4)",
    }
    if extra_style:
        base.update(extra_style)
    return html.Div(style=base, children=children)


def section_title(text, style=None):
    base = {
        "fontSize": "13px",
        "fontWeight": "600",
        "letterSpacing": "0.08em",
        "textTransform": "uppercase",
        "color": "#7ea3c4",
        "marginBottom": "14px",
        "marginTop": "0",
        "fontFamily": FONT,
    }
    if style:
        base.update(style)
    return html.H4(text, style=base)


def kpi_card(title, value):
    return html.Div(
        style={
            "background": "linear-gradient(145deg, #1a2035 0%, #1e2840 100%)",
            "border": "1px solid rgba(59,130,246,0.18)",
            "borderRadius": "14px",
            "padding": "18px 22px",
            "minWidth": "160px",
            "flex": "1",
            "position": "relative",
            "overflow": "hidden",
            "boxShadow": "0 4px 20px rgba(0,0,0,0.4), inset 0 1px 0 rgba(255,255,255,0.05)",
        },
        children=[
            html.Div(style={
                "position": "absolute", "top": "-30px", "right": "-30px",
                "width": "90px", "height": "90px", "borderRadius": "50%",
                "background": "radial-gradient(circle, rgba(59,130,246,0.12) 0%, transparent 70%)",
                "pointerEvents": "none",
            }),
            html.Div(title, style={
                "fontSize": "10px", "fontWeight": "600", "letterSpacing": "0.1em",
                "textTransform": "uppercase", "color": "#64748b",
                "marginBottom": "8px", "fontFamily": FONT,
            }),
            html.Div(str(value), style={
                "fontSize": "24px", "fontWeight": "700", "color": "#e2e8f0",
                "lineHeight": "1.1", "fontFamily": FONT, "letterSpacing": "-0.02em",
            }),
        ],
    )


def filter_label(text):
    return html.Div(text, style={
        "fontSize": "11px", "fontWeight": "600", "letterSpacing": "0.07em",
        "textTransform": "uppercase", "color": "#64748b",
        "marginBottom": "6px", "fontFamily": FONT,
    })


def ranking_table(table_id):
    return dash_table.DataTable(
        id=table_id,
        page_size=20,
        sort_action="native",
        sort_mode="multi",
        style_table=TBL_TABLE,
        style_cell=TBL_CELL,
        style_header=TBL_HEADER,
        style_data_conditional=RANKING_CONDITIONAL,
    )
