import os
import re
from datetime import timedelta, date, datetime

import pandas as pd

from config import SPANISH_MONTHS, DIAS


# ======================================================
# FECHAS Y SEMANAS
# ======================================================
def monday_of(d: date) -> date:
    return d - timedelta(days=d.weekday())


def week_label(monday: date) -> str:
    sunday = monday + timedelta(days=6)
    return f"{monday.strftime('%d/%m/%Y')} - {sunday.strftime('%d/%m/%Y')}"


def parse_period_spanish(desc: str):
    if not isinstance(desc, str):
        return None, None
    m = re.match(
        r"^\s*(\d{2})\s+([A-ZÑ]{3})\s+(\d{4})\s*-\s*(\d{2})\s+([A-ZÑ]{3})\s+(\d{4})\s*$",
        desc.strip().upper(),
    )
    if not m:
        return None, None
    d1, mon1, y1, d2, mon2, y2 = m.groups()
    mon1 = SPANISH_MONTHS.get(mon1.upper())
    mon2 = SPANISH_MONTHS.get(mon2.upper())
    if not mon1 or not mon2:
        return None, None
    start = date(int(y1), mon1, int(d1))
    end   = date(int(y2), mon2, int(d2))
    return start, end


# ======================================================
# VENDEDORES
# ======================================================
def normalize_vendor(x: str) -> str:
    if x is None or pd.isna(x):
        return ""
    s = str(x).strip().upper()
    s = re.sub(r"\s+", " ", s)
    m = re.search(r"\b(\d{1,2})\s*[-–]\s*([A-ZÁÉÍÓÚÑÜ ]{3,})\b", s)
    if m:
        num  = int(m.group(1))
        name = re.sub(r"\s+", " ", m.group(2).strip())
        return f"{num:02d}-{name}"
    m = re.search(r"(\d{2}-[A-ZÁÉÍÓÚÑÜ\s]+)$", s)
    if m:
        return re.sub(r"\s+", " ", m.group(1)).strip()
    return s


# ======================================================
# FORMATEO
# ======================================================
def sec_to_hhmmss(x):
    if pd.isna(x):
        return None
    x = int(x)
    h = x // 3600
    m = (x % 3600) // 60
    s = x % 60
    return f"{h:02d}:{m:02d}:{s:02d}"


def hours_to_hhmm(x):
    if pd.isna(x):
        return ""
    total_minutes = int(round(float(x) * 60))
    h = total_minutes // 60
    m = total_minutes % 60
    return f"{h:02d}:{m:02d}"


def _fmt_qty(x: float) -> str:
    try:
        return f"{float(x):,.2f}"
    except Exception:
        return "0.00"


def _badge(ok: bool) -> str:
    return "✅" if ok else "❌"


# ======================================================
# DATAFRAMES
# ======================================================
def safe_replace_na(series: pd.Series) -> pd.Series:
    return series.replace({
        "": pd.NA, "nan": pd.NA, "None": pd.NA, "NaT": pd.NA, "<NA>": pd.NA,
    })


def apply_filters(df: pd.DataFrame, year=None, month=None, week=None, vend=None):
    if not isinstance(df, pd.DataFrame) or df.empty:
        return df
    out = df.copy()
    if year is not None and "year" in out.columns:
        out = out[out["year"] == year]
    if month is not None and "month" in out.columns:
        out = out[out["month"] == month]
    if week is not None and "week_label" in out.columns and str(week).strip() != "":
        out = out[out["week_label"] == week]
    if vend is not None and "vendedor" in out.columns and str(vend).strip() != "":
        out = out[out["vendedor"] == vend]
    return out


# ======================================================
# ARCHIVOS
# ======================================================
def list_month_folders(data_dir: str):
    """Devuelve lista ordenada de carpetas con formato YYYY-MM dentro de data_dir."""
    import re as _re
    if not os.path.isdir(data_dir):
        return []
    months = []
    for name in os.listdir(data_dir):
        full = os.path.join(data_dir, name)
        if os.path.isdir(full) and _re.match(r"^\d{4}-\d{2}$", name):
            months.append(name)
    return sorted(months)


def read_xlsx_folder(folder: str, month_tag: str):
    """Lee todos los .xlsx de una carpeta y agrega columnas __source_month y __source_file."""
    dfs = []
    if not os.path.isdir(folder):
        return dfs
    for fn in os.listdir(folder):
        if fn.lower().endswith(".xlsx") and not fn.startswith("~$"):
            path = os.path.join(folder, fn)
            try:
                df = pd.read_excel(path)
            except PermissionError:
                print(f"⚠️  Archivo bloqueado, se omite: {path}")
                continue
            except Exception as e:
                print(f"⚠️  Error leyendo {path}: {e}")
                continue
            df["__source_month"] = month_tag
            df["__source_file"]  = fn
            dfs.append(df)
    return dfs


# ======================================================
# INACTIVOS
# ======================================================
def filter_inactivos_por_vendedor(df: "pd.DataFrame", vend=None) -> "pd.DataFrame":
    import re as _re
    import pandas as _pd
    if not isinstance(df, _pd.DataFrame) or df.empty:
        return _pd.DataFrame()
    out = df.copy()
    if vend is not None and str(vend).strip() != "" and "Cod. Vendedor" in out.columns:
        nums = _re.findall(r"\d+", str(vend))
        if nums:
            cod = f"{int(nums[0]):02d}"
            out = out[out["Cod. Vendedor"].astype(str).str.zfill(2) == cod]
    return out


# ======================================================
# PERÍODOS
# ======================================================
def get_previous_year_month(year, month):
    if year is None or month is None:
        return None, None
    year  = int(year)
    month = int(month)
    if month == 1:
        return year - 1, 12
    return year, month - 1