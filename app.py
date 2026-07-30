import threading

from dash import Dash
from dash_auth import BasicAuth

from data.cache import CACHE
from ui.layout import build_layout, INDEX_STRING
import ui.callbacks  # noqa: F401
from utils.telegram_bot import iniciar_listener, iniciar_scheduler_diario

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
    "04-nicolas":   "04-NICOLAS MANUEL SEGURA",
    "05-palermo":   "05-GUSTAVO PALERMO",
    "06-fraile":    "06-FRAILE BIBIANA",
    "07-munoz":     "07-MUÑOZ ESTEBAN",
    "08-dauria":    "08-DAURIA NEYEM ELIA",
    "09-rumin":     "09-RUMIN GERMAN",
    "10-marche":    "10-MARCHE FERNANDO",
    "11-solano":    "11-SOLANO MARINA",
    "12-mercado":   "12-MERCADO RAFAEL",
    "13-reynoso":   "13-REYNOSO ENZO PAT",
    "14-solia":     "14-SOLIA WALTER",
    "15-meli":      "15-MARCOS EZEQUIEL MELI",
    "16-tamagnini": "16-TAMAGNINI MARCOS",
    "17-rugger":    "17-RUGGER SEBASTIAN",
    "18-allende":   "18-CESAR ALLENDE",
    "19-cabrera":   "19-JOEL CABRERA",
    "20-passaponti":"20-JOAQUIN PASSAPONTI",
    "21-ferreyra":  "21-FERREYRA MAURICIO EMANUEL",
}

# ── Qué vendedores le corresponden a cada supervisor (para Telegram) ──
SUPERVISOR_VENDEDORES = {
    "hugo": [
        "02-lampert", "03-saldari", "04-nicolas", "05-palermo", "06-fraile",
        "11-solano", "14-solia", "15-meli", "17-rugger", "18-allende", "19-cabrera",
    ],
    "ariel": [
        "01-coria", "07-munoz", "08-dauria", "09-rumin", "10-marche",
        "12-mercado", "13-reynoso", "16-tamagnini", "20-passaponti", "21-ferreyra",
    ],
    # Usuario de prueba — recibe el resumen de TODOS los vendedores (ambos equipos)
    "martin": [
        "02-lampert", "03-saldari", "04-nicolas", "05-palermo", "06-fraile",
        "11-solano", "14-solia", "15-meli", "17-rugger", "18-allende", "19-cabrera",
        "01-coria", "07-munoz", "08-dauria", "09-rumin", "10-marche",
        "12-mercado", "13-reynoso", "16-tamagnini", "20-passaponti", "21-ferreyra",
    ],
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
app.SUPERVISORES          = SUPERVISORES
app.VENDEDOR_MAP          = VENDEDOR_MAP
app.SUPERVISOR_VENDEDORES = SUPERVISOR_VENDEDORES

# Único usuario autorizado para usar los botones de envío/reseteo de Telegram
app.ADMIN_TELEGRAM_USUARIO = "martin"

# Gunicorn necesita esta variable
server = app.server

CACHE.reload()

if __name__ == "__main__":
    # ── Telegram: listener de registro + envío automático diario ──
    threading.Thread(
        target=iniciar_listener,
        args=(VENDEDOR_MAP, set(SUPERVISOR_VENDEDORES.keys())),
        daemon=True,
    ).start()
    threading.Thread(
        target=iniciar_scheduler_diario,
        args=(VENDEDOR_MAP, SUPERVISOR_VENDEDORES),
        daemon=True,
    ).start()

    app.run(host="0.0.0.0", port=8050, debug=False)