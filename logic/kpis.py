from datetime import date, datetime

import pandas as pd

from config import LIMITE_INICIO_SEG, DIAS
from utils.helpers import sec_to_hhmmss, hours_to_hhmm, monday_of, week_label, normalize_vendor

PLACEHOLDERS = {"", "NAN", "NONE", "<NA>", "SIN MOTIVO", "S/M", "SM", "N/A", "NA", "-", "--", "0", "NULL"}


# ======================================================
# KPIs GENERALES
# ======================================================
def compute_kpis(vis_df: pd.DataFrame, ven_df: pd.DataFrame) -> dict:
    for col in ["Hora visita", "Hora venta", "Hora motivo", "Motivo"]:
        if col not in vis_df.columns:
            vis_df[col] = pd.NA

    total_visitas = int(len(vis_df))
    ventas        = int(vis_df["Hora venta"].notna().sum())
    no_ventas     = int(vis_df["Hora motivo"].notna().sum())

    mot      = vis_df["Motivo"]
    mot_str  = mot.astype(str).str.replace("\u00a0", " ", regex=False).str.strip().str.upper()
    sin_texto = mot.isna() | mot_str.isin(PLACEHOLDERS)

    sin_motivo   = 0
    no_visitados = 0
    if len(vis_df) > 0:
        sin_venta      = vis_df["Hora venta"].isna()
        sin_hora_motivo = vis_df["Hora motivo"].isna()
        sin_motivo     = int((sin_venta & sin_hora_motivo & sin_texto).sum())

        sin_hora_visita = vis_df["Hora visita"].isna()
        no_visitados    = int((sin_hora_visita & sin_venta & sin_hora_motivo & sin_texto).sum())

    cant_total = float(ven_df["Cantidades Totales"].sum()) if "Cantidades Totales" in ven_df.columns else 0.0

    return {
        "Visitas": total_visitas, "Ventas": ventas, "No ventas": no_ventas,
        "No ventas sin motivo": sin_motivo, "No visitados": no_visitados,
        "Cantidades": cant_total,
    }


# ======================================================
# JORNADA POR DÍA
# ======================================================
def build_jornada_df(vis_f: pd.DataFrame) -> pd.DataFrame:
    cols_out = ["vendedor", "date", "dia", "primera_visita", "ultima_visita", "hs_trab_hhmm", "hs_trab", "ventas", "no_ventas"]
    if not isinstance(vis_f, pd.DataFrame) or len(vis_f) == 0 or "Hora visita" not in vis_f.columns:
        return pd.DataFrame(columns=cols_out)

    tmp = vis_f.copy()
    hv  = tmp["Hora visita"].astype(str).str.strip().replace({"": pd.NA, "nan": pd.NA, "NaT": pd.NA, "None": pd.NA})
    mask = hv.str.match(r"^\d{1,2}:\d{2}$", na=False)
    hv.loc[mask] = hv.loc[mask] + ":00"
    tmp["_hv_sec"] = pd.to_timedelta(hv, errors="coerce").dt.total_seconds()

    mot      = tmp["Motivo"] if "Motivo" in tmp.columns else pd.Series([pd.NA] * len(tmp), index=tmp.index)
    mot_str  = mot.astype(str).str.replace("\u00a0", " ", regex=False).str.strip().str.upper()
    sin_texto = mot.isna() | mot_str.isin(PLACEHOLDERS)
    tmp["_sin_motivo"] = tmp["Hora venta"].isna() & sin_texto

    jornada = (
        tmp.groupby(["vendedor", "date"], as_index=False).agg(
            primera_visita_sec     =("_hv_sec",    "min"),
            ultima_visita_sec      =("_hv_sec",    "max"),
            ventas                 =("Hora venta",  lambda s: int(pd.Series(s).notna().sum())),
            no_ventas              =("Hora motivo", lambda s: int(pd.Series(s).notna().sum())),
            no_ventas_sin_motivo   =("_sin_motivo", lambda s: int(pd.Series(s).sum())),
        )
    )

    jornada["dia"]            = jornada["date"].apply(lambda d: DIAS.get(d.weekday(), "") if isinstance(d, date) else "")
    jornada["primera_visita"] = jornada["primera_visita_sec"].apply(sec_to_hhmmss)
    jornada["ultima_visita"]  = jornada["ultima_visita_sec"].apply(sec_to_hhmmss)

    def calc_hours(row):
        a, b = row["primera_visita_sec"], row["ultima_visita_sec"]
        return round((b - a) / 3600, 2) if pd.notna(a) and pd.notna(b) else None

    jornada["hs_trab"]      = jornada.apply(calc_hours, axis=1)
    jornada["hs_trab_hhmm"] = jornada["hs_trab"].apply(hours_to_hhmm)
    jornada["inicio_obj"]   = jornada["primera_visita_sec"].apply(
        lambda s: "✅" if pd.notna(s) and s <= LIMITE_INICIO_SEG else ("❌" if pd.notna(s) else "—")
    )

    jornada = jornada.sort_values(["date", "vendedor"])
    return jornada[["vendedor", "date", "dia", "primera_visita", "inicio_obj",
                     "ultima_visita", "hs_trab_hhmm", "hs_trab", "ventas",
                     "no_ventas", "no_ventas_sin_motivo"]]


# ======================================================
# VENTAS SEMANALES
# ======================================================
def build_ventas_semanales_df(ven_f: pd.DataFrame) -> pd.DataFrame:
    cols = ["Semana", "Vendedor", "Facturas", "Cantidades Totales"]
    if not isinstance(ven_f, pd.DataFrame) or ven_f.empty:
        return pd.DataFrame(columns=cols)

    tmp = ven_f.copy()
    if "week_label" not in tmp.columns:
        tmp["week_label"] = ""
    if "vendedor" not in tmp.columns:
        tmp["vendedor"] = tmp.get("Vendedor según comprobante", "").apply(normalize_vendor)

    tmp["Cantidades Totales"] = pd.to_numeric(tmp.get("Cantidades Totales", 0), errors="coerce").fillna(0)

    agg_dict = {"Cantidades Totales": "sum"}
    if "Cantidad de Facturas" in tmp.columns:
        tmp["Cantidad de Facturas"] = pd.to_numeric(tmp["Cantidad de Facturas"], errors="coerce").fillna(0)
        agg_dict["Cantidad de Facturas"] = "sum"
    else:
        tmp["_facturas_calc"] = 1
        agg_dict["_facturas_calc"] = "count"

    resumen = (
        tmp.groupby(["week_label", "vendedor"], as_index=False)
        .agg(agg_dict)
        .rename(columns={
            "week_label":          "Semana",
            "vendedor":            "Vendedor",
            "Cantidad de Facturas":"Facturas",
            "_facturas_calc":      "Facturas",
        })
    )

    def week_order(label):
        try:
            return datetime.strptime(str(label).split(" - ")[0].strip(), "%d/%m/%Y")
        except Exception:
            return datetime(1900, 1, 1)

    resumen["_orden"] = resumen["Semana"].apply(week_order)
    resumen = resumen.sort_values(["_orden", "Vendedor"]).drop(columns=["_orden"])
    resumen["Facturas"]           = pd.to_numeric(resumen["Facturas"],           errors="coerce").fillna(0).round(0).astype(int)
    resumen["Cantidades Totales"] = pd.to_numeric(resumen["Cantidades Totales"], errors="coerce").fillna(0).round(2)
    return resumen[cols]