from dash import Dash
from dash_auth import BasicAuth

from data.cache import CACHE
from ui.layout import build_layout, INDEX_STRING
import ui.callbacks  # noqa: F401

app = Dash(__name__)
app.title        = "Supervisión Aloma"
app.index_string = INDEX_STRING
app.layout       = build_layout()

from ui.callbacks import dashboard, rankings, resumen
dashboard.register(app)
rankings.register(app)
resumen.register(app)

# ── Usuarios ────────────────────────────────────────────
# Supervisores — ven todo
SUPERVISORES = {"hugo", "ariel", "matias", "martin"}

# Vendedores — usuario: nombre corto, contraseña: número, valor: nombre completo en datos
VENDEDOR_MAP = {
    "01-coria":     "01-CORIA BLAS GUILLE",
    "02-lampert":   "02-LAMPERT MATIAS",
    "03-saldari":   "03-SALDARI DANIEL",
    "04-gomez":     "04-GOMEZ MARCELO",
    "05-palermo":   "05-GUSTAVO PALERMO",
    "05-delpie":    "05-JOAQUIN DEL PIE YANES",
    "06-fraile":    "06-FRAILE BIBIANA",
    "07-munoz":     "07-MUÑOZ ESTEBAN",
    "08-dauria":    "08-DAURIA NEYEM ELIA",
    "09-rumin":     "09-RUMIN GERMAN",
    "10-marche":    "10-MARCHE FERNANDO",
    "11-solano":    "11-SOLANO MARINA",
    "12-mercado":   "12-MERCADO RAFAEL",
    "13-reynoso":   "13-REYNOSO ENZO PAT",
    "14-solia":     "14-SOLIA WALTER",
    "15-guarino":   "15-GUARINO GABRIELA",
    "16-sanchez":   "16-SANCHEZ DARIO",
    "17-rugger":    "17-RUGGER SEBASTIAN",
    "18-allende":   "18-CESAR ALLENDE",
    "19-vallori":   "19-AGUSTIN VALLORI",
    "19-cabrera":   "19-JOEL CABRERA",
    "20-mirabelli": "20-GONZALO MIRABELLI",
    "20-passaponti":"20-JOAQUIN PASSAPONTI",
    "21-ferreyra":  "21-FERREYRA MAURICIO EMANUEL",
}

# Contraseñas: supervisores usan su nombre, vendedores usan su número
USERS = {
    "hugo":   "hugo",
    "ariel":  "ariel",
    "matias": "matias",
    "martin": "martin",
    **{usuario: usuario.split("-")[0] for usuario in VENDEDOR_MAP}
}

BasicAuth(app, USERS)

# Exponer para que los callbacks puedan consultar el rol
app.SUPERVISORES  = SUPERVISORES
app.VENDEDOR_MAP  = VENDEDOR_MAP

# Gunicorn necesita esta variable
server = app.server

CACHE.reload()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8050, debug=False)