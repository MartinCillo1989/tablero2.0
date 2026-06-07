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

# Usuarios y contraseñas
USERS = {
    "hugo":   "hugo",
    "ariel":  "ariel",
    "matias": "matias",
    "martin": "martin",
}
BasicAuth(app, USERS)

# Gunicorn necesita esta variable
server = app.server

CACHE.reload()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8050, debug=False)