import os

# ======================================================
# RUTAS
# ======================================================
BASE_DIR   = os.path.dirname(os.path.abspath(__file__))
DATA_DIR   = os.path.join(BASE_DIR, "data_files")        # carpeta con subcarpetas YYYY-MM/visitas, /ventas, etc.
MASTER_DIR = os.path.join(BASE_DIR, "master")            # vendedores.xlsx
ALTAS_DIR  = os.path.join(BASE_DIR, "altas")             # archivos de altas de clientes
INACTIVOS_FILE = os.path.join(BASE_DIR, "control_clientes_inactivos.xlsx")
MASTER_VENDEDORES_XLSX = os.path.join(MASTER_DIR, "vendedores.xlsx")

# ======================================================
# MAPEOS
# ======================================================
SPANISH_MONTHS = {
    "ENE": 1, "FEB": 2, "MAR": 3, "ABR": 4, "MAY": 5, "JUN": 6,
    "JUL": 7, "AGO": 8, "SEP": 9, "OCT": 10, "NOV": 11, "DIC": 12,
}

BRAND_MAP = {
    1003: "PIER",
    1004: "DOLCHESTER",
    1005: "LIVERPOOL",
    1006: "CORONA",
    1028: "MIX",
}

DIAS = {
    0: "Lunes",
    1: "Martes",
    2: "Miércoles",
    3: "Jueves",
    4: "Viernes",
    5: "Sábado",
    6: "Domingo",
}

# Límite de inicio de jornada: 9:30 en segundos
LIMITE_INICIO_SEG = 9 * 3600 + 30 * 60

# ======================================================
# UI
# ======================================================
FONT = "'DM Sans', 'Segoe UI', sans-serif"
