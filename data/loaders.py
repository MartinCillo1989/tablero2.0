import os
import re
from datetime import date, datetime

import pandas as pd

from config import (
    DATA_DIR, MASTER_VENDEDORES_XLSX, INACTIVOS_FILE, ALTAS_DIR, BRAND_MAP, BASE_DIR,
)
from utils.helpers import (
    list_month_folders, read_xlsx_folder, safe_replace_na,
    parse_period_spanish, normalize_vendor, monday_of, week_label,
)

PARQUET_VISITAS = os.path.join(BASE_DIR, "cache_visitas.parquet")
PARQUET_VENTAS  = os.path.join(BASE_DIR, "cache_ventas.parquet")


def _parquet_es_valido(parquet_path: str, data_subdir: str) -> bool:
    """Devuelve True si el parquet existe y es más nuevo que todos los xlsx de data_subdir."""
    if not os.path.exists(parquet_path):
        return False
    parquet_mtime = os.path.getmtime(parquet_path)
    for month in list_month_folders(DATA_DIR):
        folder = os.path.join(DATA_DIR, month, data_subdir)
        if not os.path.isdir(folder):
            continue
        for fn in os.listdir(folder):
            if fn.lower().endswith(".xlsx") and not fn.startswith("~$"):
                xlsx_mtime = os.path.getmtime(os.path.join(folder, fn))
                if xlsx_mtime > parquet_mtime:
                    print(f"🔄 Archivo nuevo detectado: {fn} — regenerando parquet...")
                    return False
    return True


def _guardar_parquet(df: pd.DataFrame, path: str):
    tmp = df.copy()
    for col in tmp.select_dtypes(include="object").columns:
        tmp[col] = tmp[col].astype(str)
    tmp.to_parquet(path, index=False)
    print(f"💾 Parquet guardado: {os.path.basename(path)}")


def _limpiar_nan_strings(df: pd.DataFrame) -> pd.DataFrame:
    """Convierte strings 'nan'/'None'/'NaT' de vuelta a NaN real en columnas object."""
    NAN_STRINGS = {"nan", "none", "nat", "<na>", ""}
    for col in df.select_dtypes(include="object").columns:
        mask = df[col].str.lower().isin(NAN_STRINGS)
        if mask.any():
            df[col] = df[col].where(~mask, other=pd.NA)
    return df


# ======================================================
# MASTER VENDEDORES
# ======================================================
def load_master_vendedores() -> dict:
    """Devuelve {id_int: 'XX-NOMBRE'} desde el Excel maestro de vendedores."""
    if not os.path.exists(MASTER_VENDEDORES_XLSX):
        print("⚠️  No existe:", MASTER_VENDEDORES_XLSX)
        return {}
    df = pd.read_excel(MASTER_VENDEDORES_XLSX)
    lower_cols = {c.lower().strip(): c for c in df.columns}

    id_col = None
    for key in ["idvendedor", "id vendedor", "id_vendedor", "codigo vendedor", "código vendedor"]:
        if key in lower_cols:
            id_col = lower_cols[key]
            break

    name_col = None
    for key in ["vendedorreal", "vendedor real", "nombre vendedor", "nomvendedor", "vendedor", "nombre"]:
        if key in lower_cols:
            name_col = lower_cols[key]
            break

    if id_col is not None and name_col is not None:
        ids   = pd.to_numeric(df[id_col], errors="coerce")
        names = df[name_col].astype(str).str.strip()
    else:
        ids   = pd.to_numeric(df.iloc[:, 3], errors="coerce")
        names = df.iloc[:, 0].astype(str).str.strip()

    vend_map = {}
    for i, n in zip(ids, names):
        if pd.isna(i):
            continue
        try:
            key = int(i)
        except Exception:
            continue
        vend_map[key] = normalize_vendor(n)
    return vend_map


# ======================================================
# VISITAS
# ======================================================
def load_visitas() -> pd.DataFrame:
    if _parquet_es_valido(PARQUET_VISITAS, "visitas"):
        print("📦 Cargando visitas desde parquet...")
        df = pd.read_parquet(PARQUET_VISITAS)
        df = _limpiar_nan_strings(df)
        if "date" in df.columns:
            df["date"] = pd.to_datetime(df["date"], errors="coerce").dt.date
        return df
    print("⚙️  Procesando visitas desde Excel...")
    df = _load_visitas_desde_xlsx()
    _guardar_parquet(df, PARQUET_VISITAS)
    return df


def _load_visitas_desde_xlsx() -> pd.DataFrame:
    all_months = list_month_folders(DATA_DIR)
    print("MESES DETECTADOS VISITAS:", all_months)
    dfs = []
    for m in all_months:
        dfs += read_xlsx_folder(os.path.join(DATA_DIR, m, "visitas"), m)
    if not dfs:
        return pd.DataFrame()
    df = pd.concat(dfs, ignore_index=True)

    for col in ["Fecha", "Sector", "Hora visita", "Hora venta", "Hora motivo", "Motivo"]:
        if col not in df.columns:
            df[col] = pd.NA
    for c in ["Hora venta", "Hora motivo", "Motivo", "Sector"]:
        df[c] = safe_replace_na(df[c])

    if ("Hora venta" not in df.columns or df["Hora venta"].isna().all()) and df.shape[1] > 11:
        df["Hora venta"] = df.iloc[:, 11]

    df["Fecha"] = pd.to_datetime(df["Fecha"], errors="coerce", dayfirst=True)
    df["date"]  = df["Fecha"].dt.date
    df["year"]  = df["Fecha"].dt.year.astype("Int64")
    df["month"] = df["Fecha"].dt.month.astype("Int64")

    if "__source_month" in df.columns:
        src      = df["__source_month"].astype(str)
        mask_na  = df["year"].isna() | df["month"].isna()
        y = pd.to_numeric(src.str.slice(0, 4), errors="coerce").astype("Int64")
        m = pd.to_numeric(src.str.slice(5, 7), errors="coerce").astype("Int64")
        df.loc[mask_na, "year"]  = y.loc[mask_na]
        df.loc[mask_na, "month"] = m.loc[mask_na]

        def make_date(row):
            if pd.notna(row["date"]):
                return row["date"]
            try:
                return date(int(row["year"]), int(row["month"]), 1)
            except Exception:
                return pd.NaT
        df["date"] = df.apply(make_date, axis=1)

    df["week_start"] = df["date"].apply(lambda x: monday_of(x) if pd.notna(x) else pd.NaT)
    df["week_label"] = df["week_start"].apply(lambda x: week_label(x) if pd.notna(x) else "")
    df["vendedor"]   = df["Sector"].apply(normalize_vendor)
    return df


# ======================================================
# VENTAS
# ======================================================
def load_ventas() -> pd.DataFrame:
    if _parquet_es_valido(PARQUET_VENTAS, "ventas"):
        print("📦 Cargando ventas desde parquet...")
        df = pd.read_parquet(PARQUET_VENTAS)
        return _limpiar_nan_strings(df)
    print("⚙️  Procesando ventas desde Excel...")
    df = _load_ventas_desde_xlsx()
    _guardar_parquet(df, PARQUET_VENTAS)
    return df


def _load_ventas_desde_xlsx() -> pd.DataFrame:
    all_months = list_month_folders(DATA_DIR)
    dfs = []
    for m in all_months:
        dfs += read_xlsx_folder(os.path.join(DATA_DIR, m, "ventas"), m)
    if not dfs:
        return pd.DataFrame()
    df = pd.concat(dfs, ignore_index=True)

    for col in ["Descripción Período", "Vendedor según comprobante", "Cantidades Totales", "Importes Finales", "Marca"]:
        if col not in df.columns:
            df[col] = pd.NA
    for c in ["Descripción Período", "Vendedor según comprobante"]:
        df[c] = safe_replace_na(df[c])

    parsed          = df["Descripción Período"].apply(parse_period_spanish)
    df["period_start"] = parsed.apply(lambda x: x[0])
    df["period_end"]   = parsed.apply(lambda x: x[1])
    df["week_start"]   = df["period_start"].apply(lambda x: monday_of(x) if isinstance(x, date) else pd.NaT)
    df["week_label"]   = df["week_start"].apply(lambda x: week_label(x) if isinstance(x, date) else "")
    df["year"]  = pd.array([x.year  if isinstance(x, date) else pd.NA for x in df["period_start"]], dtype="Int64")
    df["month"] = pd.array([x.month if isinstance(x, date) else pd.NA for x in df["period_start"]], dtype="Int64")

    if "__source_month" in df.columns:
        src     = df["__source_month"].astype(str)
        mask_na = df["year"].isna() | df["month"].isna()
        y = pd.to_numeric(src.str.slice(0, 4), errors="coerce").astype("Int64")
        m = pd.to_numeric(src.str.slice(5, 7), errors="coerce").astype("Int64")
        df.loc[mask_na, "year"]  = y.loc[mask_na]
        df.loc[mask_na, "month"] = m.loc[mask_na]

        def fill_period_start(row):
            if isinstance(row["period_start"], date):
                return row["period_start"]
            try:
                return date(int(row["year"]), int(row["month"]), 1)
            except Exception:
                return pd.NaT
        df["period_start"] = df.apply(fill_period_start, axis=1)
        df["week_start"]   = df["period_start"].apply(lambda x: monday_of(x) if isinstance(x, date) else pd.NaT)
        df["week_label"]   = df["week_start"].apply(lambda x: week_label(x) if pd.notna(x) else "")

    df["vendedor"] = df["Vendedor según comprobante"].apply(normalize_vendor)

    # Filtrar fósforos
    desc_col = None
    for c in df.columns:
        s = df[c].astype(str).str.upper()
        if s.str.contains("FOSFOROS", na=False).any():
            desc_col = c
            break
    if desc_col is not None:
        s = df[desc_col].astype(str).str.upper()
        mask_fosforos = (
            s.str.contains(r"\(001003\)", regex=True, na=False) |
            (s.str.contains("FOSFOROS", na=False) & s.str.contains("X 50", na=False))
        )
        df = df[~mask_fosforos]

    # Detectar columna artículo
    art_col = None
    prefer  = ["articulo", "artículo", "producto", "item", "descripcion articulo", "descripción articulo", "detalle articulo"]
    for c in df.columns:
        cl = c.lower().strip()
        if any(p in cl for p in prefer):
            if "período" in cl or "periodo" in cl or "vendedor" in cl or "comprobante" in cl:
                continue
            art_col = c
            break
    if art_col is None:
        patrones = [r"\(\d{6}\)", r"20X250", r"\bBOX\b", r"\bPOP\b", r"\bPIER\b", r"\bDOLCHESTER\b", r"\bLIVERPOOL\b", r"\bCORONA\b"]
        for c in df.columns:
            cl = c.lower().strip()
            if "período" in cl or "periodo" in cl or "vendedor" in cl or "marca" in cl:
                continue
            s     = df[c].astype(str).str.upper()
            score = sum(s.str.contains(p, regex=True, na=False).any() for p in patrones)
            if score >= 2:
                art_col = c
                break
    df["articulo"] = df[art_col].astype(str).str.strip() if art_col is not None else "SIN_ARTICULO"

    df["marca_id"]          = pd.to_numeric(df["Marca"], errors="coerce")
    df["marca"]             = df["marca_id"].apply(lambda x: BRAND_MAP.get(int(x), f"{int(x)}") if pd.notna(x) else "OTROS")
    df["Cantidades Totales"] = pd.to_numeric(df["Cantidades Totales"], errors="coerce").fillna(0)
    df["Importes Finales"]   = pd.to_numeric(df["Importes Finales"],   errors="coerce").fillna(0)
    return df


# ======================================================
# EXHIBICIONES
# ======================================================
def load_exhibiciones(vend_map: dict) -> pd.DataFrame:
    all_months = list_month_folders(DATA_DIR)
    dfs = []
    for m in all_months:
        dfs += read_xlsx_folder(os.path.join(DATA_DIR, m, "exhibiciones"), m)
    if not dfs:
        return pd.DataFrame()
    df = pd.concat(dfs, ignore_index=True)

    if "Fecha" not in df.columns:
        df["Fecha"] = pd.NA
    df["Fecha"] = safe_replace_na(df["Fecha"])
    df["Fecha"] = pd.to_datetime(df["Fecha"], errors="coerce", dayfirst=True)
    df["date"]  = df["Fecha"].dt.date
    df["year"]  = df["Fecha"].dt.year.astype("Int64")
    df["month"] = df["Fecha"].dt.month.astype("Int64")

    if "__source_month" in df.columns:
        src     = df["__source_month"].astype(str)
        mask_na = df["year"].isna() | df["month"].isna()
        y = pd.to_numeric(src.str.slice(0, 4), errors="coerce").astype("Int64")
        m = pd.to_numeric(src.str.slice(5, 7), errors="coerce").astype("Int64")
        df.loc[mask_na, "year"]  = y.loc[mask_na]
        df.loc[mask_na, "month"] = m.loc[mask_na]

        def make_date(row):
            if pd.notna(row["date"]):
                return row["date"]
            try:
                return date(int(row["year"]), int(row["month"]), 1)
            except Exception:
                return pd.NaT
        df["date"] = df.apply(make_date, axis=1)

    df["week_start"] = df["date"].apply(lambda x: monday_of(x) if pd.notna(x) else pd.NaT)
    df["week_label"] = df["week_start"].apply(lambda x: week_label(x) if pd.notna(x) else "")

    if "IdVendedor" in df.columns:
        ids = pd.to_numeric(df["IdVendedor"], errors="coerce")
    else:
        ids = pd.to_numeric(df.iloc[:, 5], errors="coerce") if df.shape[1] > 5 else pd.Series([pd.NA] * len(df))
    df["vendedor"] = ids.apply(lambda x: vend_map.get(int(x), "") if pd.notna(x) else "")
    df["vendedor"] = df["vendedor"].apply(normalize_vendor)

    if "Kiosko " in df.columns:
        df["cliente"] = df["Kiosko "].astype(str).str.strip()
    elif "Kiosko" in df.columns:
        df["cliente"] = df["Kiosko"].astype(str).str.strip()
    else:
        df["cliente"] = ""

    if "Estado" in df.columns:
        df["estado"] = df["Estado"].astype(str).str.strip().str.title()
        df["estado"] = df["estado"].replace({"": "Pendiente", "Nan": "Pendiente", "None": "Pendiente"})
    else:
        df["estado"] = "Pendiente"
    return df


# ======================================================
# INACTIVOS
# ======================================================
def load_inactivos():
    """Devuelve (df_actual, df_anterior)."""
    if not os.path.exists(INACTIVOS_FILE):
        print(f"⚠️  No existe: {INACTIVOS_FILE}")
        return pd.DataFrame(), pd.DataFrame()
    try:
        xl          = pd.ExcelFile(INACTIVOS_FILE)
        sheet_names = xl.sheet_names

        def _read_sheet(name):
            if name not in sheet_names:
                return pd.DataFrame()
            df = pd.read_excel(INACTIVOS_FILE, sheet_name=name)
            if "Cod. Vendedor" in df.columns:
                df["Cod. Vendedor"] = (
                    pd.to_numeric(df["Cod. Vendedor"], errors="coerce")
                    .fillna(0).astype(int)
                    .apply(lambda x: f"{x:02d}" if x > 0 else "")
                )
            dias = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
            for c in ["Clientes en cartera", "Clientes con venta", "Total inactivos", "% Inactivos", *dias]:
                if c not in df.columns:
                    df[c] = 0
            return df

        df_actual   = _read_sheet("Inactivos por vendedor")
        prev_sheet  = next((n for n in sheet_names if "anterior" in n.strip().lower()), None)
        df_anterior = _read_sheet(prev_sheet) if prev_sheet else pd.DataFrame()
        return df_actual, df_anterior
    except Exception as e:
        print("⚠️  ERROR leyendo inactivos:", e)
        return pd.DataFrame(), pd.DataFrame()


# ======================================================
# ALTAS DE CLIENTES
# ======================================================
def load_altas() -> pd.DataFrame:
    """Lee todos los xlsx de la carpeta altas/."""
    if not os.path.isdir(ALTAS_DIR):
        return pd.DataFrame()
    frames = []
    for fn in sorted(os.listdir(ALTAS_DIR)):
        if not fn.lower().endswith(".xlsx") or fn.startswith("~$"):
            continue
        path = os.path.join(ALTAS_DIR, fn)
        try:
            df = pd.read_excel(path, sheet_name="Clientes", header=1, skiprows=[2])
        except Exception as e:
            print(f"⚠️  Error leyendo altas {fn}: {e}")
            continue
        if "Descripción Ruta Vta." in df.columns:
            df["_vend_num"] = (
                df["Descripción Ruta Vta."].astype(str)
                .str.extract(r"^(\d+)")[0]
                .pipe(pd.to_numeric, errors="coerce")
            )
        else:
            df["_vend_num"] = pd.NA
        df["_periodo"] = fn.replace(".xlsx", "").replace(".XLSX", "")
        frames.append(df)
    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True)