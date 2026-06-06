from datetime import date, datetime
from collections import defaultdict

import pandas as pd

from config import DIAS, LIMITE_INICIO_SEG
from utils.helpers import monday_of, week_label, sec_to_hhmmss, hours_to_hhmm
from data.loaders import load_visitas, load_ventas, load_inactivos, load_altas


DIAS_ESP = {
    0: "Lunes", 1: "Martes", 2: "Miércoles",
    3: "Jueves", 4: "Viernes", 5: "Sábado", 6: "Domingo",
}

PLACEHOLDERS = {"", "NAN", "NONE", "<NA>", "SIN MOTIVO", "S/M", "SM", "N/A", "NA", "-", "--", "0", "NULL"}


# ======================================================
# JORNADA PRECALCULADA
# ======================================================
def _build_jornada_precalc(vis: pd.DataFrame) -> pd.DataFrame:
    if not isinstance(vis, pd.DataFrame) or vis.empty or "Hora visita" not in vis.columns:
        return pd.DataFrame()

    tmp = vis.copy()
    hv  = tmp["Hora visita"].astype(str).str.strip().replace({"": pd.NA, "nan": pd.NA, "NaT": pd.NA, "None": pd.NA})
    mask = hv.str.match(r"^\d{1,2}:\d{2}$", na=False)
    hv.loc[mask] = hv.loc[mask] + ":00"
    tmp["_hv_sec"] = pd.to_timedelta(hv, errors="coerce").dt.total_seconds()

    mot   = tmp["Motivo"] if "Motivo" in tmp.columns else pd.Series(pd.NA, index=tmp.index)
    mstr  = mot.astype(str).str.replace("\u00a0", " ", regex=False).str.strip().str.upper()
    sin_texto = mot.isna() | mstr.isin(PLACEHOLDERS)
    tmp["_sin_mot"] = tmp["Hora venta"].isna() & sin_texto

    grp_cols = [c for c in ["vendedor", "date", "year", "month", "week_label"] if c in tmp.columns]
    jornada  = (
        tmp.groupby(grp_cols, sort=False).agg(
            primera_sec =("_hv_sec", "min"),
            ultima_sec  =("_hv_sec", "max"),
            ventas      =("Hora venta",  lambda s: int(s.notna().sum())),
            no_ventas   =("Hora motivo", lambda s: int(s.notna().sum())),
            sin_motivo  =("_sin_mot",    lambda s: int(s.sum())),
        ).reset_index()
    )

    jornada["dia"]            = jornada["date"].apply(lambda d: DIAS_ESP.get(d.weekday(), "") if isinstance(d, date) else "")
    jornada["primera_visita"] = jornada["primera_sec"].apply(sec_to_hhmmss)
    jornada["ultima_visita"]  = jornada["ultima_sec"].apply(sec_to_hhmmss)
    jornada["hs_trab"]        = (
        (jornada["ultima_sec"] - jornada["primera_sec"]) / 3600
    ).where(jornada["primera_sec"].notna() & jornada["ultima_sec"].notna()).round(2)
    jornada["hs_trab_hhmm"]   = jornada["hs_trab"].apply(hours_to_hhmm)
    jornada["inicio_obj"]     = jornada["primera_sec"].apply(
        lambda s: "✅" if pd.notna(s) and s <= LIMITE_INICIO_SEG else ("❌" if pd.notna(s) else "—")
    )

    return jornada.sort_values(["date", "vendedor"]).reset_index(drop=True)


# ======================================================
# CACHE GLOBAL
# ======================================================
class _Cache:
    def __init__(self):
        self.vis             = pd.DataFrame()
        self.ven             = pd.DataFrame()
        self.inact           = pd.DataFrame()
        self.inact_ant       = pd.DataFrame()
        self.jornada_all     = pd.DataFrame()
        self.altas_count     = {}
        self.years           = []
        self.loaded_at       = None
        # resumen precalculado: {(year, month): dict_por_vendedor}
        self.resumen_cache: dict = {}

    def reload(self):
        print("⏳ Cargando datos...")
        t0 = datetime.now()

        self.vis       = load_visitas()
        self.ven       = load_ventas()
        self.inact, self.inact_ant = load_inactivos()

        altas = load_altas()
        self.altas_count = {}
        if isinstance(altas, pd.DataFrame) and not altas.empty and "_vend_num" in altas.columns:
            for vnum, grp in altas.groupby("_vend_num"):
                try:
                    self.altas_count[f"{int(vnum):02d}"] = len(grp)
                except Exception:
                    pass

        self.jornada_all = _build_jornada_precalc(self.vis)

        yrs = set()
        for df in [self.vis, self.ven]:
            if isinstance(df, pd.DataFrame) and "year" in df.columns:
                yrs |= set(df["year"].dropna().unique())
        self.years = sorted(int(y) for y in yrs)

        # NO precalculamos resumenes al arrancar — se calculan la primera vez que se piden
        self.resumen_cache = {}

        self.loaded_at = datetime.now()
        print(f"✅ Listo en {(self.loaded_at - t0).total_seconds():.1f}s")

    def get_resumen(self, year, month) -> dict:
        """Devuelve el resumen para un período. Lo calcula la primera vez y lo cachea."""
        key = (year, month)
        if key not in self.resumen_cache:
            print(f"⚙️  Calculando resumen {month:02d}/{year} por primera vez...")
            from logic.resumen import build_resumen_vendedores
            t0 = datetime.now()
            self.resumen_cache[key] = build_resumen_vendedores(
                vis_df          = self.vis,
                ven_df          = self.ven,
                inactivos_df    = self.inact,
                inactivos_ant_df= self.inact_ant,
                altas_count     = self.altas_count,
                year            = year,
                month           = month,
                jornada_all     = self.jornada_all,
            )
            print(f"✅ Resumen {month:02d}/{year} listo en {(datetime.now()-t0).total_seconds():.1f}s — queda en cache")
        return self.resumen_cache[key]


# Instancia global — importar desde cualquier módulo
CACHE = _Cache()