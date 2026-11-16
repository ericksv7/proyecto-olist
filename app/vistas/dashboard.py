from datetime import date

import pandas as pd
import plotly.express as px
import streamlit as st

import db
import kpis

st.title("📊 Dashboard gerencial")
st.caption("Control de ventas y entregas · datos en vivo desde la base de datos")

# ---------- Filtros ----------
with st.sidebar:
    st.header("Filtros")
    desde = st.date_input("Desde", value=date(2017, 1, 1), key="d_desde")
    hasta = st.date_input("Hasta", value=date.today(), key="d_hasta")
    origen = st.selectbox("Origen de los datos", ["Todos", "historico", "sistema"], key="d_origen")
    st.caption("histórico = CSV de Olist · sistema = pedidos registrados en la aplicación")

if desde > hasta:
    st.error("La fecha 'Desde' no puede ser posterior a 'Hasta'.")
    st.stop()

k = kpis.kpis_globales(desde, hasta, origen)
if k["pedidos_total"] == 0:
    st.warning("No hay pedidos en el rango y origen seleccionados.")
    st.stop()


def num(x):
    return None if x is None or pd.isna(x) else float(x)


ticket, ciclo, a_tiempo = num(k["ticket"]), num(k["ciclo"]), num(k["a_tiempo"])
M = kpis.METAS

# ---------- Zona superior: tarjetas de KPIs ----------
c1, c2, c3, c4 = st.columns(4)
c1.metric(
    "Ticket promedio",
    f"{ticket:,.2f} BRL" if ticket is not None else "—",
    delta=f"{ticket - M['ticket']:+,.2f} vs meta ≥ {M['ticket']:.0f}" if ticket is not None else None,
    help="Suma de precios de los ítems ÷ pedidos (sin cancelados ni no disponibles).",
)
c2.metric(
    "Ciclo de entrega",
    f"{ciclo:.2f} días" if ciclo is not None else "—",
    delta=f"{ciclo - M['ciclo']:+.2f} días vs meta ≤ {M['ciclo']:.0f}" if ciclo is not None else None,
    delta_color="inverse",
    help="Promedio de (fecha de entrega − fecha de compra) en pedidos entregados.",
)
c3.metric(
    "Entregas a tiempo",
    f"{a_tiempo:.1f} %" if a_tiempo is not None else "—",
    delta=f"{a_tiempo - M['a_tiempo']:+.1f} pp vs meta ≥ {M['a_tiempo']:.0f} %" if a_tiempo is not None else None,
    help="Entregados en o antes de la fecha estimada ÷ total entregados.",
)
c4.metric(
    "Pedidos en el período",
    f"{k['pedidos_total']:,}",
    delta=f"{k['entregados']:,} entregados",
    delta_color="off",
    help="Todos los pedidos del filtro, sin importar su estado.",
)

# ---------- Alertas gerenciales ----------
alertas = []
if ticket is not None and ticket < M["ticket"]:
    alertas.append(f"el ticket promedio ({ticket:,.2f}) está bajo la meta de {M['ticket']:.0f} BRL")
if ciclo is not None and ciclo > M["ciclo"]:
    alertas.append(f"el ciclo de entrega ({ciclo:.2f} días) supera la meta de {M['ciclo']:.0f} días")
if a_tiempo is not None and a_tiempo < M["a_tiempo"]:
    alertas.append(f"las entregas a tiempo ({a_tiempo:.1f} %) están bajo la meta de {M['a_tiempo']:.0f} %")
if alertas:
    st.warning("**Atención gerencial:** " + "; ".join(alertas) + ".")
else:
    st.success("Todos los KPIs del período cumplen sus metas.")
st.caption("Las metas son objetivos propuestos para el proyecto, no referencias oficiales.")

st.divider()

# ---------- Zona media: gráficos ----------
mensual = kpis.ingresos_mensuales(desde, hasta, origen)
entregas = kpis.entregas_mensuales(desde, hasta, origen)
cats = kpis.top_categorias(desde, hasta, origen)
uf = kpis.ventas_por_uf(desde, hasta, origen)
estados_df = kpis.pedidos_por_estado(desde, hasta, origen)

g1, g2 = st.columns(2)
with g1:
    st.subheader("¿Cómo evolucionan las ventas?")
    if mensual.empty:
        st.info("Sin ventas en el período.")
    else:
        fig = px.bar(
            mensual, x="mes", y="ingresos",
            labels={"mes": "Mes", "ingresos": "Ingresos (BRL)"},
            hover_data={"pedidos": True},
        )
        st.plotly_chart(fig)
    st.caption("Ingresos por mes de compra. Ayuda a detectar temporadas altas y caídas.")

with g2:
    st.subheader("¿Estamos entregando rápido?")
    if entregas.empty:
        st.info("Sin pedidos entregados en el período.")
    else:
        fig = px.line(
            entregas, x="mes", y="ciclo", markers=True,
            labels={"mes": "Mes de compra", "ciclo": "Días de entrega"},
            hover_data={"entregados": True},
        )
        fig.add_hline(y=M["ciclo"], line_dash="dash", annotation_text=f"Meta ≤ {M['ciclo']:.0f} días")
        st.plotly_chart(fig)
    st.caption("Ciclo de entrega promedio por mes. Sobre la línea punteada se incumple la meta.")

g3, g4 = st.columns(2)
with g3:
    st.subheader("¿Cumplimos lo prometido?")
    if entregas.empty:
        st.info("Sin pedidos entregados en el período.")
    else:
        fig = px.line(
            entregas, x="mes", y="a_tiempo", markers=True,
            labels={"mes": "Mes de compra", "a_tiempo": "% entregas a tiempo"},
            hover_data={"entregados": True},
        )
        fig.add_hline(y=M["a_tiempo"], line_dash="dash", annotation_text=f"Meta ≥ {M['a_tiempo']:.0f} %")
        fig.update_yaxes(range=[0, 105])
        st.plotly_chart(fig)
    st.caption("Porcentaje de entregas en la fecha estimada o antes. Bajo la meta, revisar logística.")

with g4:
    st.subheader("¿Qué se vende más?")
    if cats.empty:
        st.info("Sin ventas en el período.")
    else:
        top5 = cats.head(5)
        fig = px.bar(
            top5, x="unidades", y="categoria", orientation="h",
            text=top5["participacion"].map(lambda v: f"{v:.1f} %"),
            labels={"unidades": "Unidades vendidas", "categoria": ""},
            hover_data={"ingresos": ":,.2f"},
        )
        fig.update_yaxes(autorange="reversed")
        st.plotly_chart(fig)
    st.caption("Top 5 de categorías por unidades, con su participación sobre el total vendido.")

g5, g6 = st.columns(2)
with g5:
    st.subheader("¿Dónde están los clientes?")
    if uf.empty:
        st.info("Sin ventas en el período.")
    else:
        fig = px.bar(
            uf, x="uf", y="ingresos",
            labels={"uf": "Estado (UF)", "ingresos": "Ingresos (BRL)"},
            hover_data={"pedidos": True},
        )
        st.plotly_chart(fig)
    st.caption("Top 10 de estados por ingresos. Orienta dónde reforzar logística o marketing.")

with g6:
    st.subheader("¿Hay pedidos sin completar?")
    fig = px.bar(
        estados_df, x="estado", y="pedidos", text_auto=True,
        labels={"estado": "Estado del pedido", "pedidos": "Pedidos"},
    )
    st.plotly_chart(fig)
    st.caption("Pedidos por estado. Muchos pedidos detenidos antes de 'Entregado' indican cuellos de botella.")

st.divider()

# ---------- Zona inferior: tabla detallada ----------
st.subheader("Detalle de pedidos")
estados = db.listar_estados()
nombre_a_codigo = dict(zip(estados["nombre"], estados["codigo"]))
sel = st.multiselect("Filtrar por estado", list(nombre_a_codigo), key="d_estados")
det = kpis.detalle(desde, hasta, origen, [nombre_a_codigo[n] for n in sel])
if det.empty:
    st.info("No hay pedidos con esos filtros.")
else:
    st.write(f"**{len(det):,} pedidos**")
    st.dataframe(
        det,
        hide_index=True,
        column_config={"total": st.column_config.NumberColumn("Total (BRL)", format="%.2f")},
    )
    st.download_button(
        "Descargar tabla en CSV",
        det.to_csv(index=False).encode("utf-8"),
        file_name="detalle_pedidos.csv",
        mime="text/csv",
    )
