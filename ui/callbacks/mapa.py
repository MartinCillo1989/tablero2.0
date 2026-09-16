from datetime import date, timedelta

import pandas as pd
from dash import Input, Output

from data.cache import CACHE
from utils.helpers import apply_filters
from utils.chesserp_ventas import obtener_ultima_compra_por_cliente, es_cliente_anulado

# Un cliente se considera "inactivo" si hace más de esta cantidad de días
# que no tiene NINGUNA compra registrada (o si nunca compró nada).
INACTIVIDAD_DIAS = 30

# Colores fijos para las categorías más comunes — el resto (motivos menos
# frecuentes) se les asigna color automáticamente por Plotly.
COLOR_MAP = {
    "VENTA":                "#22c55e",
    "NO VISITADO":          "#475569",
    "NUNCA VISITADO":       "#7f1d1d",
    "INACTIVO":             "#f43f5e",
    "TIENE STOCK":          "#3b82f6",
    "CERRADO":              "#f59e0b",
    "CERRADO PERMANENTE":   "#dc2626",
    "DUEÑO AUSENTE":        "#a78bfa",
    "SIN DINERO":           "#ec4899",
    "COMPRO FUERA DE RUTA": "#06b6d4",
    "COMPRO MAS BARATO":    "#f97316",
    "COMPRO MISMO PRECIO":  "#eab308",
    "SIN MOTIVO":           "#64748b",
    "VOLVER A VISITAR":     "#14b8a6",
}


def _ultima_compra_combinada(vend, client_key):
    """Devuelve {cliente_int: fecha_ultima_compra} combinando TODO el
    historial de Visitas (sin filtrar por año/mes/semana) con el historial
    real de ChessERP (incluye ventas fuera de ruta). Para cada cliente,
    la fecha final es la más reciente entre las dos fuentes.

    Es la misma fuente de verdad que usa _calcular_clientes_inactivos, y
    también la usamos para decidir qué clientes marcar "VENTA" por haber
    comprado recientemente (últimos INACTIVIDAD_DIAS días) — así ese
    criterio no depende de si hubo una visita con "Hora venta" cargada
    justo dentro del mes/semana filtrado en pantalla, y refleja también
    las compras fuera de ruta que solo aparecen en ChessERP."""
    if not client_key or client_key not in CACHE.vis.columns:
        return {}

    base_hist = CACHE.vis
    if vend and "vendedor" in base_hist.columns:
        base_hist = base_hist[base_hist["vendedor"] == vend]

    ultima_venta_visitas = {}
    if "Hora venta" in base_hist.columns and "date" in base_hist.columns:
        tiene_venta_hist = base_hist["Hora venta"].notna()
        con_venta = base_hist[tiene_venta_hist]
        if not con_venta.empty:
            fechas_venta = pd.to_datetime(con_venta["date"], errors="coerce")
            serie = fechas_venta.groupby(con_venta[client_key]).max()
            ultima_venta_visitas = {int(k): v for k, v in serie.items() if pd.notna(v)}

    # meses_hacia_atras=2 alcanza de sobra para detectar inactividad de
    # INACTIVIDAD_DIAS (30 días) sin arriesgarnos al timeout de 60s que
    # vimos con rangos más grandes (6 meses tardaba ~59s en ChessERP).
    ultima_venta_chesserp = obtener_ultima_compra_por_cliente(meses_hacia_atras=2)

    todos_los_clientes = set(base_hist[client_key].dropna().unique())
    combinada = {}
    for cliente in todos_los_clientes:
        try:
            cliente_int = int(cliente)
        except (ValueError, TypeError):
            cliente_int = None

        fechas_candidatas = []
        if cliente in ultima_venta_visitas:
            fechas_candidatas.append(pd.Timestamp(ultima_venta_visitas[cliente]))
        if cliente_int is not None and cliente_int in ultima_venta_chesserp:
            fechas_candidatas.append(pd.Timestamp(ultima_venta_chesserp[cliente_int]))

        if fechas_candidatas:
            combinada[cliente] = max(fechas_candidatas)

    return combinada


def _calcular_clientes_inactivos(vend, client_key):
    """Devuelve el set de clientes que hace más de INACTIVIDAD_DIAS días
    que no tienen ninguna compra (Visitas + ChessERP combinados), o que
    nunca compraron."""
    if not client_key or client_key not in CACHE.vis.columns:
        return set()

    base_hist = CACHE.vis
    if vend and "vendedor" in base_hist.columns:
        base_hist = base_hist[base_hist["vendedor"] == vend]

    todos_los_clientes = set(base_hist[client_key].dropna().unique())
    if not todos_los_clientes:
        return set()

    combinada = _ultima_compra_combinada(vend, client_key)

    hoy = pd.Timestamp(date.today())
    inactivos = set()
    for cliente in todos_los_clientes:
        if cliente not in combinada:
            inactivos.add(cliente)  # nunca compró, por ninguna de las dos vías
            continue
        dias_desde_ultima = (hoy - combinada[cliente]).days
        if dias_desde_ultima > INACTIVIDAD_DIAS:
            inactivos.add(cliente)

    # FIX (10/09/2026): un cliente dado de baja/anulado en ChessERP nunca
    # más va a comprar, así que siempre superaba los 30 días y quedaba
    # marcado "inactivo" para siempre — el Excel de Visitas no tiene
    # ninguna columna de estado/anulado, así que hay que preguntarle
    # directo a ChessERP por cada candidato (con caché de 24hs adentro de
    # es_cliente_anulado, no pega a ChessERP en cada refresh del mapa).
    inactivos_filtrados = set()
    for cliente in inactivos:
        try:
            cliente_int = int(cliente)
        except (ValueError, TypeError):
            inactivos_filtrados.add(cliente)  # no se pudo convertir, lo dejamos tal cual
            continue
        if not es_cliente_anulado(cliente_int):
            inactivos_filtrados.add(cliente)

    return inactivos_filtrados


def register(app):

    @app.callback(
        Output("f_motivos_mapa", "options"),
        Input("btn_reload", "n_clicks"),
    )
    def init_motivos_mapa_options(n):
        if not isinstance(CACHE.vis, pd.DataFrame) or CACHE.vis.empty:
            return []

        opciones = [
            {"label": "✅ Con venta",                                        "value": "VENTA"},
            {"label": "⬛ No visitado (puntual, ese día)",                    "value": "NO VISITADO"},
            {"label": "🟥 Nunca visitado en el período",                     "value": "NUNCA VISITADO"},
            {"label": f"🔴 Inactivo (+{INACTIVIDAD_DIAS} días sin comprar)", "value": "INACTIVO"},
        ]
        if "Motivo" in CACHE.vis.columns:
            motivos = (
                CACHE.vis["Motivo"].astype(str).str.strip()
                .replace({"": "SIN MOTIVO", "nan": "SIN MOTIVO", "None": "SIN MOTIVO"})
            )
            valores = sorted({str(m).strip() for m in motivos.unique() if pd.notna(m) and str(m).strip()})
            opciones += [{"label": m, "value": m} for m in valores]
        return opciones

    @app.callback(
        Output("mapa_google_data", "data"),
        Output("mapa_kpi_label",   "children"),
        Input("btn_reload",      "n_clicks"),
        Input("f_year",          "value"),
        Input("f_month",         "value"),
        Input("f_week",          "value"),
        Input("f_vend",          "value"),
        Input("f_motivos_mapa",  "value"),
        Input("f_ruta_mapa",     "value"),
    )
    def refresh_mapa(n, year, month, week, vend, motivos_sel, ruta_sel):
        def _mapa_vacio(mensaje):
            return [], mensaje

        # Evitamos cargar miles de puntos de una — el mapa arranca vacío
        # hasta que se elija un vendedor puntual arriba.
        if not vend:
            return _mapa_vacio("👆 Elegí un vendedor en el filtro de arriba para ver sus visitas en el mapa.")

        vis_f = apply_filters(CACHE.vis, year, month, week, vend)
        if not isinstance(vis_f, pd.DataFrame) or vis_f.empty:
            return _mapa_vacio("Sin datos para los filtros elegidos.")

        df = vis_f.copy()
        if "Latitud" not in df.columns or "Longitud" not in df.columns:
            return _mapa_vacio("Faltan columnas de Latitud/Longitud en los datos.")

        def to_float(serie):
            return pd.to_numeric(serie.astype(str).str.replace(",", ".", regex=False), errors="coerce")

        df["lat"] = to_float(df["Latitud"])
        df["lon"] = to_float(df["Longitud"])
        df = df[df["lat"].notna() & df["lon"].notna()]
        df = df[(df["lat"] != 0) & (df["lon"] != 0)]
        if df.empty:
            return _mapa_vacio("No hay coordenadas válidas para los filtros elegidos.")

        # ── Categoría de cada punto: VENTA > Motivo > NO VISITADO ──
        tiene_venta  = df["Hora venta"].notna()  if "Hora venta"  in df.columns else pd.Series(False, index=df.index)
        tiene_motivo = df["Hora motivo"].notna() if "Hora motivo" in df.columns else pd.Series(False, index=df.index)

        motivo_txt = df["Motivo"].astype(str).str.strip() if "Motivo" in df.columns else pd.Series("", index=df.index)
        motivo_txt = motivo_txt.replace({"": "SIN MOTIVO", "nan": "SIN MOTIVO", "None": "SIN MOTIVO"})

        categoria = pd.Series("NO VISITADO", index=df.index)
        categoria[tiene_motivo] = motivo_txt[tiene_motivo]
        categoria[tiene_venta]  = "VENTA"

        # ── Distinguir "no visitado ese día puntual" de "nunca visitado en
        #    todo el período" — agrupamos por cliente y vemos si tuvo AL
        #    MENOS una visita real (venta o motivo registrado) en algún
        #    momento del período filtrado. Si nunca tuvo ninguna, todas sus
        #    filas "NO VISITADO" pasan a ser "NUNCA VISITADO". ──
        # FIX (10/09/2026): antes priorizaba "Id cliente" (columna B del
        # Excel de Visitas) sobre "Id cliente erp" (columna C) — pero
        # "Id cliente" NO es el código real de ChessERP, "Id cliente erp"
        # sí. Eso hacía que el mapa (y el cruce con ChessERP para
        # detectar inactivos/última compra) mostrara el número
        # equivocado. Invertido el orden de prioridad.
        client_key = next((c for c in ["Id cliente erp", "Id cliente"] if c in df.columns), None)
        if client_key:
            visito_algo = tiene_venta | tiene_motivo
            alguna_visita_por_cliente = visito_algo.groupby(df[client_key]).transform("any")
            nunca_visitado = (categoria == "NO VISITADO") & (~alguna_visita_por_cliente)
            categoria[nunca_visitado] = "NUNCA VISITADO"

        # ── Clientes inactivos: más de INACTIVIDAD_DIAS sin ninguna compra
        #    en TODO su historial. Restringimos a los clientes que
        #    aparecieron en la ruta de este vendedor en los últimos
        #    INACTIVIDAD_DIAS días reales (mismo criterio que la tabla de
        #    resumen). Si alguno de esos clientes no tiene ninguna fila
        #    dentro del período filtrado arriba (year/month/week), le
        #    agregamos un punto igual usando su última ubicación conocida
        #    — así el mapa muestra la MISMA cantidad de inactivos que la
        #    tabla de resumen, sin importar qué período esté seleccionado
        #    arriba. ──
        df["Categoría"] = categoria
        combinada_venta = {}  # cliente -> fecha real de última compra (Visitas+ChessERP)

        if client_key:
            # ── hist_reciente: TODO el historial de este vendedor en los
            #    últimos INACTIVIDAD_DIAS días reales desde hoy — sin
            #    importar qué año/mes/semana esté filtrado arriba. Lo
            #    usamos como fuente de "última ubicación conocida" tanto
            #    para agregar puntos de VENTA reciente como de INACTIVO
            #    que no tengan fila en el período filtrado actual. ──
            hoy_map = date.today()
            fecha_inicio_map = hoy_map - timedelta(days=INACTIVIDAD_DIAS)
            hist_vend = CACHE.vis
            if "vendedor" in hist_vend.columns:
                hist_vend = hist_vend[hist_vend["vendedor"] == vend]
            if "date" in hist_vend.columns:
                fechas_hist = pd.to_datetime(hist_vend["date"], errors="coerce").dt.date
                mask_reciente = fechas_hist.notna() & (fechas_hist >= fecha_inicio_map) & (fechas_hist <= hoy_map)
                hist_reciente = hist_vend[mask_reciente]
            else:
                hist_reciente = hist_vend.iloc[0:0]

            def _agregar_puntos_faltantes(df_actual, clientes_objetivo, etiqueta_categoria):
                """Para clientes en clientes_objetivo que no tienen ninguna
                fila en df_actual, les agrega un punto usando su última
                ubicación conocida dentro de hist_reciente (últimos 30
                días), con la categoría indicada. Devuelve el df con las
                filas agregadas."""
                if not clientes_objetivo or hist_reciente.empty:
                    return df_actual
                clientes_ya_en_df = set(df_actual[client_key].dropna().unique())
                faltantes = clientes_objetivo - clientes_ya_en_df
                if not faltantes:
                    return df_actual
                extra = hist_reciente[hist_reciente[client_key].isin(faltantes)].copy()
                if "Latitud" in extra.columns and "Longitud" in extra.columns:
                    extra["lat"] = to_float(extra["Latitud"])
                    extra["lon"] = to_float(extra["Longitud"])
                    extra = extra[extra["lat"].notna() & extra["lon"].notna()]
                    extra = extra[(extra["lat"] != 0) & (extra["lon"] != 0)]
                else:
                    extra = extra.iloc[0:0]
                if extra.empty:
                    return df_actual
                if "date" in extra.columns:
                    extra["_date_tmp"] = pd.to_datetime(extra["date"], errors="coerce")
                    extra = extra.sort_values("_date_tmp").drop_duplicates(subset=[client_key], keep="last")
                    extra = extra.drop(columns=["_date_tmp"])
                else:
                    extra = extra.drop_duplicates(subset=[client_key], keep="last")
                extra["Categoría"] = etiqueta_categoria
                return pd.concat([df_actual, extra], ignore_index=True)

            # ── VENTA reciente (últimos INACTIVIDAD_DIAS días), combinando
            #    Visitas + ChessERP — antes esto solo miraba "Hora venta"
            #    dentro del período filtrado (year/month/week), así que un
            #    cliente que compró fuera de ruta (solo visible en
            #    ChessERP), o que compró recientemente pero no tiene visita
            #    registrada en el mes filtrado, quedaba mal clasificado
            #    como NO VISITADO / NUNCA VISITADO en vez de VENTA. ──
            hoy_venta = pd.Timestamp(date.today())
            combinada_venta = _ultima_compra_combinada(vend, client_key)
            clientes_venta_reciente = {
                cliente for cliente, fecha in combinada_venta.items()
                if (hoy_venta - fecha).days <= INACTIVIDAD_DIAS
            }
            if clientes_venta_reciente:
                df.loc[df[client_key].isin(clientes_venta_reciente), "Categoría"] = "VENTA"
                df = _agregar_puntos_faltantes(df, clientes_venta_reciente, "VENTA")

            # ── Clientes inactivos: más de INACTIVIDAD_DIAS sin ninguna
            #    compra en TODO su historial. Restringimos a los clientes
            #    que aparecieron en la ruta de este vendedor en los
            #    últimos INACTIVIDAD_DIAS días reales (mismo criterio que
            #    la tabla de resumen). Si alguno de esos clientes no tiene
            #    ninguna fila dentro del período filtrado arriba, le
            #    agregamos un punto igual usando su última ubicación
            #    conocida — así el mapa muestra la MISMA cantidad de
            #    inactivos que la tabla de resumen, sin importar qué
            #    período esté seleccionado arriba. ──
            clientes_ruta_reciente = (
                set(hist_reciente[client_key].dropna().unique())
                if client_key in hist_reciente.columns else set()
            )

            clientes_inactivos_todos = _calcular_clientes_inactivos(vend, client_key)
            clientes_inactivos = clientes_inactivos_todos & clientes_ruta_reciente

            if clientes_inactivos:
                es_inactivo = df[client_key].isin(clientes_inactivos) & (df["Categoría"] != "VENTA")
                df.loc[es_inactivo, "Categoría"] = "INACTIVO"
                df = _agregar_puntos_faltantes(df, clientes_inactivos, "INACTIVO")

        # ── Filtro por día de ruta (extrae el día del texto de "Ruta") ──
        if ruta_sel and "Ruta" in df.columns:
            dia_extraido = (
                df["Ruta"].astype(str).str.split("-").str[-1]
                .str.strip().str.upper()
                .str.normalize("NFKD").str.encode("ascii", errors="ignore").str.decode("utf-8")
            )
            df = df[dia_extraido.isin([r.upper() for r in ruta_sel])]

        # ── Filtro por motivo/venta/no visitado/inactivo ──
        if motivos_sel:
            df = df[df["Categoría"].isin(motivos_sel)]

        if df.empty:
            return _mapa_vacio("Sin datos para los filtros elegidos.")

        # "INACTIVO", "NUNCA VISITADO" y "VENTA" cuentan CLIENTES, no visitas
        # — si el cliente compró varias veces (o apareció varias veces en
        # alguna de estas categorías) en el período filtrado, sin esto se
        # verían N puntos apilados exactamente en el mismo lugar, o un
        # conteo de "clientes" que en realidad es un conteo de eventos.
        # Nos quedamos con un solo punto por cliente para estas categorías.
        if client_key and client_key in df.columns:
            categorias_por_cliente = {"INACTIVO", "NUNCA VISITADO", "VENTA"}
            es_categoria_cliente = df["Categoría"].isin(categorias_por_cliente)
            df_categoria_cliente = df[es_categoria_cliente].drop_duplicates(subset=[client_key], keep="first")
            df_resto = df[~es_categoria_cliente]
            df = pd.concat([df_resto, df_categoria_cliente], ignore_index=True)

        # Freno de seguridad extra: si igual queda muy grande (ej: vendedor
        # elegido pero sin filtrar por mes), no intentamos dibujar miles de
        # puntos — mejor pedirle que acote un poco más.
        LIMITE_PUNTOS = 1500
        if len(df) > LIMITE_PUNTOS:
            return _mapa_vacio(
                f"⚠️ Hay {len(df):,} puntos para estos filtros — es demasiado para mostrar de una. "
                f"Acotá un poco más (elegí Mes, Semana, Motivo o Día de ruta) para que cargue bien."
                .replace(",", ".")
            )

        # ── Armamos la lista de marcadores para el mapa de Google ──
        marcadores = []
        for _, row in df.iterrows():
            cat = row["Categoría"]
            color = COLOR_MAP.get(cat, "#3b82f6")
            nombre_cliente = row.get("Descripción cliente", "") or ""

            partes_info = [f"<b>{nombre_cliente}</b>"]

            if client_key and client_key in df.columns and pd.notna(row.get(client_key)):
                id_cliente = row[client_key]
                try:
                    id_cliente = int(id_cliente)
                except (ValueError, TypeError):
                    pass
                partes_info.append(f"N° cliente: {id_cliente}")

            if "Domicilio" in df.columns and pd.notna(row.get("Domicilio")):
                partes_info.append(f"Dirección: {row['Domicilio']}")

            partes_info.append(f"Categoría: {cat}")
            if "vendedor" in df.columns and pd.notna(row.get("vendedor")):
                partes_info.append(f"Vendedor: {row['vendedor']}")

            # Para VENTA (compra reciente) e INACTIVO mostramos la fecha
            # REAL de última compra (combinando Visitas + ChessERP), no la
            # fecha de la visita puntual que generó este punto — porque si
            # el cliente compró fuera de ruta, esa visita puede ser vieja o
            # no tener nada que ver con la compra real. Para el resto de
            # las categorías (sin compra confirmada) mostramos la fecha de
            # la visita, que es el único dato de fecha disponible.
            id_cliente_raw = row.get(client_key) if client_key else None
            fecha_ultima_compra = combinada_venta.get(id_cliente_raw) if id_cliente_raw is not None else None

            if cat in ("VENTA", "INACTIVO") and fecha_ultima_compra is not None:
                partes_info.append(f"Última compra: {fecha_ultima_compra.date()}")
            elif "date" in df.columns and pd.notna(row.get("date")):
                partes_info.append(f"Fecha: {row['date']}")

            if "Ruta" in df.columns and pd.notna(row.get("Ruta")):
                partes_info.append(f"Ruta: {row['Ruta']}")

            # El InfoWindow de Google Maps es siempre de fondo blanco, pero
            # el texto puede heredar el color clarito del tema oscuro de la
            # app (queda casi ilegible). Forzamos color y tipografía acá
            # mismo, en el HTML del popup, para que no dependa de los
            # estilos globales de la página.
            info_html = (
                '<div style="color:#1f2937; font-family:system-ui,-apple-system,sans-serif; '
                'font-size:13px; line-height:1.5; max-width:220px;">'
                + "<br>".join(partes_info)
                + "</div>"
            )

            marcadores.append({
                "lat": float(row["lat"]),
                "lng": float(row["lon"]),
                "color": color,
                "title": nombre_cliente,
                "info": info_html,
            })

        total = len(marcadores)
        label = f"{total:,} puntos en el mapa".replace(",", ".")
        return marcadores, label

    app.clientside_callback(
        "window.dash_clientside.mapa_google.renderizar",
        Output("mapa_google_dummy_output", "children"),
        Input("mapa_google_data", "data"),
    )

    # ── Resumen rápido de TODOS los vendedores a la vez ─────────────
    # Independiente de los filtros de Año/Mes/Semana de arriba a propósito:
    # siempre mira los últimos INACTIVIDAD_DIAS días reales desde hoy, para
    # que no dependa de qué esté seleccionado en el dashboard. Los
    # vendedores igual salen de app.VENDEDOR_MAP (o de CACHE.vis si no
    # hubiera mapa), no de ningún filtro.
    @app.callback(
        Output("mapa_resumen_tbl", "data"),
        Output("mapa_resumen_tbl", "columns"),
        Input("btn_reload", "n_clicks"),
    )
    def refresh_resumen_mapa(n):
        columnas = [
            {"name": "Vendedor",               "id": "Vendedor"},
            {"name": "Clientes con venta",      "id": "Clientes con venta"},
            {"name": "Inactivos",               "id": "Inactivos"},
            {"name": "Nunca visitado",          "id": "Nunca visitado"},
            {"name": "No visitado (puntual)",   "id": "No visitado (puntual)"},
        ]

        if not isinstance(CACHE.vis, pd.DataFrame) or CACHE.vis.empty:
            return [], columnas

        vendedor_map = getattr(app, "VENDEDOR_MAP", {}) or {}
        if vendedor_map:
            nombres_vendedores = sorted(set(vendedor_map.values()))
        elif "vendedor" in CACHE.vis.columns:
            nombres_vendedores = sorted(CACHE.vis["vendedor"].dropna().unique())
        else:
            nombres_vendedores = []

        hoy = date.today()
        # FIX (07/09/2026): "hoy" acá es un date.today() normal de Python,
        # pero _ultima_compra_combinada() devuelve fechas como pd.Timestamp
        # — "date - Timestamp" no se puede restar directamente y tiraba
        # "TypeError: unsupported operand type(s) for -: 'datetime.date'
        # and 'Timestamp'" en cuanto había al menos un cliente con compra
        # combinada. Se agrega hoy_ts (versión Timestamp de hoy) para usar
        # en esa resta puntual, sin tocar el resto de las comparaciones que
        # ya usaban "hoy" como date plano (esas sí funcionan bien, porque
        # comparan contra "fechas" que también son .dt.date más abajo).
        hoy_ts = pd.Timestamp(hoy)
        fecha_inicio = hoy - timedelta(days=INACTIVIDAD_DIAS)

        filas = []
        for nombre_vend in nombres_vendedores:
            df_vend = CACHE.vis
            if "vendedor" in df_vend.columns:
                df_vend = df_vend[df_vend["vendedor"] == nombre_vend]

            if df_vend.empty or "date" not in df_vend.columns:
                filas.append({
                    "Vendedor": nombre_vend, "Clientes con venta": 0,
                    "Inactivos": 0, "Nunca visitado": 0, "No visitado (puntual)": 0,
                })
                continue

            # Ventana fija: últimos INACTIVIDAD_DIAS días reales desde hoy,
            # sin importar qué filtro de mes esté elegido arriba.
            fechas = pd.to_datetime(df_vend["date"], errors="coerce").dt.date
            mask_periodo = fechas.notna() & (fechas >= fecha_inicio) & (fechas <= hoy)
            df = df_vend[mask_periodo]

            if df.empty:
                filas.append({
                    "Vendedor": nombre_vend, "Clientes con venta": 0,
                    "Inactivos": 0, "Nunca visitado": 0, "No visitado (puntual)": 0,
                })
                continue

            # Ver comentario más arriba en refresh_mapa — se prioriza
            # "Id cliente erp" (columna C, el código real de ChessERP)
            # sobre "Id cliente" (columna B, no es el real).
            client_key = next((c for c in ["Id cliente erp", "Id cliente"] if c in df.columns), None)

            tiene_venta  = df["Hora venta"].notna()  if "Hora venta"  in df.columns else pd.Series(False, index=df.index)
            tiene_motivo = df["Hora motivo"].notna() if "Hora motivo" in df.columns else pd.Series(False, index=df.index)

            categoria = pd.Series("NO VISITADO", index=df.index)
            categoria[tiene_motivo] = "MOTIVO"

            combinada_venta = _ultima_compra_combinada(nombre_vend, client_key) if client_key else {}
            clientes_venta_reciente = {
                cliente for cliente, fecha in combinada_venta.items()
                if (hoy_ts - fecha).days <= INACTIVIDAD_DIAS
            } if client_key else set()
            if clientes_venta_reciente:
                categoria[df[client_key].isin(clientes_venta_reciente)] = "VENTA"
            elif not client_key:
                categoria[tiene_venta] = "VENTA"

            if client_key:
                visito_algo = tiene_venta | tiene_motivo
                alguna_visita_por_cliente = visito_algo.groupby(df[client_key]).transform("any")
                nunca_visitado_mask = (categoria == "NO VISITADO") & (~alguna_visita_por_cliente)
                categoria[nunca_visitado_mask] = "NUNCA VISITADO"

                clientes_con_venta      = df.loc[categoria == "VENTA", client_key].nunique()
                clientes_nunca_visitado = df.loc[categoria == "NUNCA VISITADO", client_key].nunique()
            else:
                clientes_con_venta      = int(tiene_venta.sum())
                clientes_nunca_visitado = int((categoria == "NUNCA VISITADO").sum())

            no_visitado_puntual = int((categoria == "NO VISITADO").sum())

            # Inactivos: mismo criterio de siempre (más de INACTIVIDAD_DIAS
            # sin comprar, mirando TODO el historial real), acotado a los
            # clientes que aparecen en la ruta de estos últimos 30 días
            # (df/client_key de arriba), no al mes elegido en los filtros.
            inactivos_set = _calcular_clientes_inactivos(nombre_vend, client_key) if client_key else set()
            if client_key:
                clientes_ruta_reciente = set(df[client_key].dropna().unique())
                inactivos_set = inactivos_set & clientes_ruta_reciente

            filas.append({
                "Vendedor": nombre_vend,
                "Clientes con venta": clientes_con_venta,
                "Inactivos": len(inactivos_set),
                "Nunca visitado": clientes_nunca_visitado,
                "No visitado (puntual)": no_visitado_puntual,
            })

        return filas, columnas