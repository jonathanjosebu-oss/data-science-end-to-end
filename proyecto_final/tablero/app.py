"""Tablero de monitoreo QSRR-Predict (PSet 4 §6.4).

    streamlit run tablero/app.py          # local (lee .env)
    docker compose up -d tablero          # http://localhost:8501

Muestra lote por lote (semana k = lote k) las métricas de sistema, de modelo,
de desempeño y de deriva, con las alertas y los reentrenamientos marcados.
Fuente: tablas PRODUCCION.* de Snowflake. Sin credenciales (por ejemplo, quien
revisa el repositorio), lee las exportaciones de docs/*.csv.
"""

from __future__ import annotations

import sys
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))
DOCS = RAIZ / "docs"

AZUL, NARANJA, GRIS = "#2a78d6", "#eb6834", "#8a8984"
CRITICO = "#d03b3b"
TABLAS = ("monitoreo", "alertas", "reentrenamientos")

st.set_page_config(page_title="QSRR-Predict · Monitoreo", layout="wide")


@st.cache_data(ttl=60, show_spinner="Leyendo métricas…")
def cargar() -> tuple[dict[str, pd.DataFrame], str]:
    try:
        from src import almacen

        datos = {t: almacen.consultar(f"SELECT * FROM {t.upper()}") for t in TABLAS}
        return datos, "Snowflake · PRODUCCION"
    except Exception as exc:  # noqa: BLE001 - sin credenciales se usa la exportación
        datos = {}
        for t in TABLAS:
            ruta = DOCS / ("reentrenamientos_decisiones.csv" if t == "reentrenamientos" else f"{t}.csv")
            datos[t] = pd.read_csv(ruta) if ruta.exists() else pd.DataFrame()
            datos[t].columns = [c.lower() for c in datos[t].columns]
        return datos, f"docs/*.csv (Snowflake no disponible: {type(exc).__name__})"


def serie(mon: pd.DataFrame, metrica: str, eje: str = "lote", feature: str | None = None) -> pd.DataFrame:
    m = mon[mon["metrica"] == metrica]
    if feature is not None:
        m = m[m["feature"] == feature]
    return m.dropna(subset=[eje]).assign(**{eje: lambda d: d[eje].astype(int)}).sort_values(eje)


def marcas_reentrenamiento(reent: pd.DataFrame) -> alt.Chart | None:
    """Regla vertical en la semana de cada reentrenamiento, con su decisión."""
    if reent.empty:
        return None
    r = reent.assign(
        etiqueta=lambda d: "Reentrenamiento v" + d["version_challenger"].astype(str) + " · " + d["decision_humana"].fillna("pendiente")
    )
    base = alt.Chart(r).encode(x=alt.X("lote:O"))
    return base.mark_rule(color=GRIS, strokeDash=[4, 4], strokeWidth=1.5).encode(
        tooltip=[alt.Tooltip("lote:O", title="Semana"), alt.Tooltip("etiqueta:N", title="Evento"),
                 alt.Tooltip("motivo:N", title="Motivo"), alt.Tooltip("motivo_decision:N", title="Decisión")]
    )


def con_marcas(grafico: alt.Chart, reent: pd.DataFrame) -> alt.LayerChart | alt.Chart:
    regla = marcas_reentrenamiento(reent)
    return (grafico + regla) if regla is not None else grafico


def umbral(valor: float, texto: str) -> alt.Chart:
    d = pd.DataFrame({"y": [valor], "t": [f"{texto}: {valor:,.2f}"]})
    return alt.Chart(d).mark_rule(color=CRITICO, strokeDash=[2, 3], strokeWidth=1.5).encode(
        y="y:Q", tooltip=alt.Tooltip("t:N", title="Umbral")
    )


def lineas(df: pd.DataFrame, x: str, titulo_x: str, titulo_y: str, colores: dict[str, str], fmt: str = ",.2f") -> alt.Chart:
    """Varias series en una línea por serie; leyenda arriba, tooltip por punto,
    y los puntos que superan su umbral marcados en rojo con un anillo."""
    escala = alt.Scale(domain=list(colores), range=list(colores.values()))
    base = alt.Chart(df).encode(
        x=alt.X(f"{x}:O", title=titulo_x, axis=alt.Axis(labelAngle=0)),
        y=alt.Y("valor:Q", title=titulo_y),
        # Una sola serie: el título del gráfico la nombra, sin caja de leyenda.
        color=alt.Color("serie:N", scale=escala,
                        legend=alt.Legend(orient="top", title=None, labelLimit=0) if len(colores) > 1 else None),
    )
    tooltip = [alt.Tooltip(f"{x}:O", title=titulo_x), alt.Tooltip("serie:N", title="Serie"),
               alt.Tooltip("valor:Q", title=titulo_y, format=fmt)]
    capa = base.mark_line(strokeWidth=2) + base.mark_point(size=70, filled=True, opacity=1).encode(tooltip=tooltip)
    if "supera" in df and df["supera"].fillna(False).astype(bool).any():
        alertas = df[df["supera"].fillna(False).astype(bool)]
        capa += alt.Chart(alertas).mark_point(size=260, shape="circle", color=CRITICO, strokeWidth=2.5, filled=False).encode(
            x=f"{x}:O", y="valor:Q", tooltip=tooltip + [alt.Tooltip("umbral:Q", title="Umbral", format=fmt)]
        )
    return capa


def apilar(mon: pd.DataFrame, metricas: dict[str, str], eje: str = "lote") -> pd.DataFrame:
    partes = [serie(mon, m, eje).assign(serie=nombre) for m, nombre in metricas.items()]
    partes = [p for p in partes if not p.empty]
    return pd.concat(partes, ignore_index=True) if partes else pd.DataFrame(columns=[eje, "valor", "serie", "supera", "umbral"])


def primer_umbral(df: pd.DataFrame) -> float | None:
    u = df["umbral"].dropna() if "umbral" in df else pd.Series(dtype=float)
    return float(u.iloc[0]) if len(u) else None


# ---------------------------------------------------------------- datos
datos, fuente = cargar()
mon, alertas, reent = datos["monitoreo"], datos["alertas"], datos["reentrenamientos"]
if mon.empty:
    st.error("No hay métricas todavía: ejecuta el flujo produccion_lotes en Kestra o exporta docs/monitoreo.csv.")
    st.stop()
for col in ("valor", "umbral"):
    mon[col] = pd.to_numeric(mon[col], errors="coerce")
mon["supera"] = mon["supera"].map(lambda v: str(v).lower() in ("true", "1", "1.0"))
if not reent.empty:
    reent = reent.sort_values("lote")

st.title("QSRR-Predict · monitoreo de producción")
st.caption(
    f"Fuente: {fuente}. Semana k = lote k. El tiempo medido de un lote llega una semana después, "
    "así que el desempeño de la semana k es el del lote k-1. Las líneas grises punteadas marcan "
    "los reentrenamientos y los círculos rojos los valores que dispararon alerta."
)

# ---------------------------------------------------------------- KPIs
semanas = int(mon["lote"].max())
n_alertas = len(alertas)
altas = int((alertas.get("severidad", pd.Series(dtype=str)) == "Alta").sum())
version = serie(mon, "predicciones")["version_modelo"].dropna()
ultimo = reent.iloc[-1] if not reent.empty else None
k1, k2, k3, k4 = st.columns(4)
k1.metric("Semanas procesadas", semanas)
k2.metric("Alertas", n_alertas)
k2.caption(f"{altas} de severidad alta")
k3.metric("Reentrenamientos", len(reent))
if ultimo is not None:
    k3.caption(f"Último: semana {int(ultimo['lote'])}, {ultimo['decision_humana'] or 'pendiente'}")
k4.metric("Versión en producción", f"v{int(version.iloc[-1])}" if len(version) else "—")

tab_sis, tab_mod, tab_des, tab_der, tab_ale = st.tabs(
    ["Sistema", "Modelo", "Desempeño y negocio", "Deriva y datos", "Alertas y reentrenamientos"]
)

# ---------------------------------------------------------------- sistema
with tab_sis:
    c1, c2 = st.columns(2)
    lat = apilar(mon, {"latencia_p50_ms": "p50", "latencia_p95_ms": "p95"})
    graf = lineas(lat, "lote", "Semana", "Latencia por solicitud (ms)", {"p50": AZUL, "p95": NARANJA}, ",.0f")
    if (u := primer_umbral(lat)) is not None:
        graf += umbral(u, "Alerta p95")
    c1.subheader("Latencia")
    c1.altair_chart(con_marcas(graf, reent).properties(height=280), use_container_width=True)

    err = apilar(mon, {"tasa_4xx": "4xx", "tasa_5xx": "5xx"})
    graf = lineas(err, "lote", "Semana", "Tasa de errores", {"4xx": AZUL, "5xx": NARANJA}, ".1%")
    graf += umbral(0.05, "Alerta 4xx") + umbral(0.01, "Alerta 5xx")
    c2.subheader("Errores")
    c2.altair_chart(con_marcas(graf, reent).properties(height=280), use_container_width=True)

    vol = serie(mon, "solicitudes").merge(
        serie(mon, "predicciones")[["lote", "valor"]].rename(columns={"valor": "predicciones"}), on="lote", how="left"
    )
    graf = alt.Chart(vol).mark_bar(color=AZUL, cornerRadiusTopLeft=4, cornerRadiusTopRight=4, size=26).encode(
        x=alt.X("lote:O", title="Semana", axis=alt.Axis(labelAngle=0)),
        y=alt.Y("valor:Q", title="Solicitudes a la API"),
        tooltip=[alt.Tooltip("lote:O", title="Semana"), alt.Tooltip("valor:Q", title="Solicitudes", format=","),
                 alt.Tooltip("predicciones:Q", title="Analitos predichos", format=",")],
    )
    st.subheader("Volumen")
    st.altair_chart(con_marcas(graf, reent).properties(height=220), use_container_width=True)

# ---------------------------------------------------------------- modelo
with tab_mod:
    c1, c2 = st.columns(2)
    dist = serie(mon, "prediccion_p10")[["lote", "valor"]].rename(columns={"valor": "p10"})
    for m in ("p50", "p90", "media"):
        dist = dist.merge(serie(mon, f"prediccion_{m}")[["lote", "valor"]].rename(columns={"valor": m}), on="lote")
    base = alt.Chart(dist).encode(x=alt.X("lote:O", title="Semana", axis=alt.Axis(labelAngle=0)))
    tt = [alt.Tooltip("lote:O", title="Semana")] + [alt.Tooltip(f"{m}:Q", title=m, format=".2f") for m in ("p10", "p50", "p90", "media")]
    graf = (
        base.mark_area(color=AZUL, opacity=0.18).encode(y=alt.Y("p10:Q", title="Tiempo de retención predicho (min)"), y2="p90:Q")
        + base.mark_line(color=AZUL, strokeWidth=2).encode(y="p50:Q")
        + base.mark_point(color=AZUL, filled=True, size=70).encode(y="p50:Q", tooltip=tt)
    )
    c1.subheader("Distribución de las predicciones")
    c1.caption("Línea: mediana. Banda: percentiles 10 a 90.")
    c1.altair_chart(con_marcas(graf, reent).properties(height=280), use_container_width=True)

    dec = apilar(mon, {"tasa_aprobar": "aprobar condiciones", "tasa_revisar": "revisar condiciones"})
    graf = alt.Chart(dec).mark_bar(size=26, stroke="#fcfcfb", strokeWidth=2).encode(
        x=alt.X("lote:O", title="Semana", axis=alt.Axis(labelAngle=0)),
        y=alt.Y("valor:Q", title="Fracción de métodos", axis=alt.Axis(format="%"), stack="zero"),
        color=alt.Color("serie:N", scale=alt.Scale(domain=["aprobar condiciones", "revisar condiciones"], range=[AZUL, NARANJA]),
                        legend=alt.Legend(orient="top", title=None, labelLimit=0)),
        tooltip=[alt.Tooltip("lote:O", title="Semana"), alt.Tooltip("serie:N", title="Decisión"),
                 alt.Tooltip("valor:Q", title="Tasa", format=".1%")],
    )
    c2.subheader("Tasa de cada decisión")
    c2.caption("Con el umbral del PSet 3 (intervalo del 95 %) el modelo todavía no aprueba métodos.")
    c2.altair_chart(con_marcas(graf, reent).properties(height=280), use_container_width=True)

# ---------------------------------------------------------------- desempeño
with tab_des:
    st.caption("Eje x = semana en que llegó el tiempo medido (lote evaluado = semana - 1).")
    c1, c2 = st.columns(2)
    rmse = apilar(mon, {"rmse": "Modelo", "rmse_linea_base": "Línea base (mediana por condición)"})
    graf = lineas(rmse, "lote", "Semana", "RMSE del lote (min)",
                  {"Modelo": AZUL, "Línea base (mediana por condición)": NARANJA})
    if (u := primer_umbral(rmse)) is not None:
        graf += umbral(u, "Alerta RMSE (p95 pseudo-lotes)")
    c1.subheader("Error técnico (RMSE)")
    c1.altair_chart(con_marcas(graf, reent).properties(height=300), use_container_width=True)

    ses = apilar(mon, {"sesgo": "Sesgo (predicho - medido)"})
    ses_abs = serie(mon, "sesgo_abs")[["lote", "supera", "umbral"]]
    ses = ses.drop(columns=["supera", "umbral"], errors="ignore").merge(ses_abs, on="lote", how="left")
    graf = lineas(ses, "lote", "Semana", "Error medio del lote (min)", {"Sesgo (predicho - medido)": AZUL})
    if (u := primer_umbral(ses)) is not None:
        graf += umbral(u, "Alerta +sesgo") + umbral(-u, "Alerta -sesgo")
    c2.subheader("Sesgo")
    c2.caption("Negativo = el modelo predice antes de lo que eluye (efecto del volumen de retardo).")
    c2.altair_chart(con_marcas(graf, reent).properties(height=300), use_container_width=True)

    neg = apilar(mon, {"corridas_evitadas_netas": "Modelo", "neto_aprobar_todo": "Aprobar todo sin revisar",
                       "neto_linea_base": "Proceso actual (revisar siempre)"})
    graf = lineas(neg, "lote", "Semana", "Corridas evitadas netas",
                  {"Modelo": AZUL, "Aprobar todo sin revisar": NARANJA, "Proceso actual (revisar siempre)": GRIS}, ",.0f")
    st.subheader("Métrica de negocio por lote")
    st.caption("Corridas exploratorias evitadas menos repeticiones por aprobar un método que falla. "
               "El proceso actual ahorra 0 por definición.")
    st.altair_chart(con_marcas(graf, reent).properties(height=280), use_container_width=True)

    diag = mon[mon["metrica"].str.startswith("diagnostico:", na=False)].assign(
        diagnostico=lambda d: d["metrica"].str.removeprefix("diagnostico:"))
    if not diag.empty:
        st.subheader("Diagnóstico por lote evaluado")
        st.dataframe(diag[["lote", "lote_evaluado", "diagnostico"]].rename(
            columns={"lote": "Semana", "lote_evaluado": "Lote evaluado", "diagnostico": "Diagnóstico"}).sort_values("Semana"),
            hide_index=True, use_container_width=True)

# ---------------------------------------------------------------- deriva
with tab_der:
    psi = serie(mon, "psi").dropna(subset=["feature"]).assign(
        relativo=lambda d: d["valor"] / d["umbral"], supera_txt=lambda d: d["supera"].map({True: "▲", False: ""}))
    st.subheader("PSI por descriptor molecular")
    st.caption("Color = PSI / umbral calibrado (percentil 99 de pseudo-lotes). ▲ = supera su umbral. "
               "La alerta de deriva de datos exige al menos 2 descriptores sobre el umbral.")
    base = alt.Chart(psi).encode(
        x=alt.X("lote:O", title="Semana", axis=alt.Axis(labelAngle=0)), y=alt.Y("feature:N", title=None, axis=alt.Axis(labelLimit=0)))
    tt = [alt.Tooltip("lote:O", title="Semana"), alt.Tooltip("feature:N", title="Descriptor"),
          alt.Tooltip("valor:Q", title="PSI", format=".3f"), alt.Tooltip("umbral:Q", title="Umbral", format=".3f")]
    graf = base.mark_rect(stroke="#fcfcfb", strokeWidth=2).encode(
        color=alt.Color("relativo:Q", title="PSI / umbral", scale=alt.Scale(scheme="blues", domain=[0, 1.5], clamp=True)),
        tooltip=tt) + base.mark_text(fontSize=13, color="#0b0b0b").encode(text="supera_txt:N", tooltip=tt)
    st.altair_chart(graf.properties(height=300), use_container_width=True)

    c1, c2 = st.columns(2)
    sobre = serie(mon, "psi_features_sobre_umbral").assign(serie="Descriptores con PSI sobre umbral",
                                                          supera=lambda d: d["valor"] >= 2)
    graf = lineas(sobre, "lote", "Semana", "Descriptores sobre umbral", {"Descriptores con PSI sobre umbral": AZUL}, ".0f")
    graf += umbral(2, "Alerta de deriva de datos")
    c1.subheader("Deriva de datos")
    c1.altair_chart(con_marcas(graf, reent).properties(height=260), use_container_width=True)

    dom = apilar(mon, {"fraccion_fuera_de_dominio": "Fuera del dominio de entrenamiento"})
    graf = lineas(dom, "lote", "Semana", "Fracción de analitos", {"Fuera del dominio de entrenamiento": AZUL}, ".1%")
    if (u := primer_umbral(dom)) is not None:
        graf += umbral(u, "Alerta")
    c2.subheader("Guardia de dominio")
    c2.altair_chart(con_marcas(graf, reent).properties(height=260), use_container_width=True)

    st.subheader("Calidad de datos de entrada")
    tabla = mon[mon["metrica"].isin(["faltantes", "categoria_no_vista", "chi2_p"])].pivot_table(
        index=["metrica", "feature"], columns="lote", values="valor").round(3)
    st.dataframe(tabla, use_container_width=True)

# ---------------------------------------------------------------- alertas
with tab_ale:
    st.subheader("Alertas disparadas")
    if alertas.empty:
        st.info("Sin alertas.")
    else:
        cols = ["lote", "lote_evaluado", "alerta", "severidad", "metrica", "valor", "umbral", "receptor", "accion", "diagnostico"]
        st.dataframe(alertas[[c for c in cols if c in alertas]].sort_values("lote"), hide_index=True, use_container_width=True)
        conteo = alertas.groupby(["lote", "severidad"]).size().reset_index(name="n")
        graf = alt.Chart(conteo).mark_bar(size=26, stroke="#fcfcfb", strokeWidth=2).encode(
            x=alt.X("lote:O", title="Semana", axis=alt.Axis(labelAngle=0)),
            y=alt.Y("n:Q", title="Alertas", stack="zero"),
            color=alt.Color("severidad:N", scale=alt.Scale(domain=["Alta", "Media", "Baja"], range=[CRITICO, "#fab219", GRIS]),
                            legend=alt.Legend(orient="top", title="Severidad")),
            tooltip=["lote:O", "severidad:N", "n:Q"])
        st.altair_chart(con_marcas(graf, reent).properties(height=240), use_container_width=True)
    st.subheader("Reentrenamientos (challenger frente a champion)")
    if reent.empty:
        st.info("Sin reentrenamientos.")
    else:
        st.dataframe(reent, hide_index=True, use_container_width=True)
