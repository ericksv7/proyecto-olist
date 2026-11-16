import re
import sqlite3
from datetime import date, datetime, time, timedelta

import pandas as pd
import streamlit as st

import db

st.title("📦 Operaciones")
st.caption("Registro, consulta y seguimiento de pedidos")

if "carrito" not in st.session_state:
    st.session_state.carrito = []
if "mensaje" in st.session_state:
    st.success(st.session_state.pop("mensaje"))

tab_reg, tab_con, tab_est = st.tabs(
    ["Registrar pedido", "Consultar pedidos", "Actualizar estado"]
)

# =====================================================================
# 1. REGISTRAR PEDIDO
# =====================================================================
with tab_reg:
    st.subheader("1. Cliente")
    tipo = st.radio("Tipo de cliente", ["Cliente existente", "Cliente nuevo"], horizontal=True)
    id_cliente, cliente_nuevo = None, None
    if tipo == "Cliente existente":
        clientes = db.listar_clientes()
        etiquetas = {
            r.id_cliente: f"{r.ciudad} ({r.estado_uf}) · {r.id_cliente[:8]}"
            for r in clientes.itertuples()
        }
        id_cliente = st.selectbox(
            "Cliente (escribe para buscar)", options=list(etiquetas), format_func=etiquetas.get
        )
    else:
        c1, c2 = st.columns(2)
        ciudad = c1.text_input("Ciudad")
        uf = c2.text_input("Estado (UF, 2 letras)", max_chars=2)
        cliente_nuevo = {"ciudad": ciudad.strip(), "uf": uf.strip().upper()}

    st.subheader("2. Productos")
    cats = db.listar_categorias()
    nombres_cat = dict(zip(cats["id_categoria"], cats["nombre"]))
    c1, c2 = st.columns(2)
    id_cat = c1.selectbox(
        "Categoría", options=list(nombres_cat), format_func=nombres_cat.get
    )
    productos = db.listar_productos(id_cat)
    id_prod = c2.selectbox("Producto", options=productos, format_func=lambda p: p[:12] + "…")
    c3, c4, c5 = st.columns([2, 2, 1])
    precio = c3.number_input("Precio (BRL)", min_value=0.0, value=50.0, step=1.0, format="%.2f")
    flete = c4.number_input("Flete (BRL)", min_value=0.0, value=15.0, step=1.0, format="%.2f")
    c5.write("")
    c5.write("")
    if c5.button("Agregar"):
        if not id_prod:
            st.error("Esta categoría no tiene productos.")
        elif precio <= 0:
            st.error("El precio debe ser mayor que 0.")
        else:
            st.session_state.carrito.append(
                {
                    "id_producto": id_prod,
                    "categoria": nombres_cat[id_cat],
                    "precio": float(precio),
                    "flete": float(flete),
                }
            )
            st.rerun()

    if st.session_state.carrito:
        carrito = pd.DataFrame(st.session_state.carrito)
        st.dataframe(carrito, hide_index=True, use_container_width=True)
        st.write(f"**Total productos:** {carrito['precio'].sum():,.2f} BRL")
        if st.button("Vaciar lista"):
            st.session_state.carrito = []
            st.rerun()
    else:
        st.info("Aún no has agregado productos al pedido.")

    st.subheader("3. Entrega")
    fecha_est = st.date_input(
        "Fecha estimada de entrega",
        value=date.today() + timedelta(days=12),
        min_value=date.today() + timedelta(days=1),
    )

    if st.button("Registrar pedido", type="primary"):
        errores = []
        if cliente_nuevo is not None:
            if not cliente_nuevo["ciudad"]:
                errores.append("La ciudad del cliente es obligatoria.")
            if not re.fullmatch(r"[A-Z]{2}", cliente_nuevo["uf"]):
                errores.append("El estado (UF) debe tener exactamente 2 letras.")
        if not st.session_state.carrito:
            errores.append("Agrega al menos un producto al pedido.")
        if errores:
            for e in errores:
                st.error(e)
        else:
            try:
                id_pedido = db.registrar_pedido(
                    id_cliente, cliente_nuevo, fecha_est, st.session_state.carrito
                )
            except sqlite3.Error as e:
                st.error(f"No se pudo registrar el pedido: {e}")
            else:
                st.session_state.carrito = []
                st.session_state.mensaje = f"Pedido registrado correctamente: {id_pedido}"
                st.rerun()

# =====================================================================
# 2. CONSULTAR PEDIDOS
# =====================================================================
with tab_con:
    estados = db.listar_estados()
    nombre_a_codigo = dict(zip(estados["nombre"], estados["codigo"]))
    f1, f2, f3, f4, f5 = st.columns([1, 1, 2, 1, 2])
    desde = f1.date_input("Desde", value=date(2017, 1, 1), key="f_desde")
    hasta = f2.date_input("Hasta", value=date.today(), key="f_hasta")
    sel_estados = f3.multiselect("Estado", list(nombre_a_codigo), key="f_estados")
    origen = f4.selectbox("Origen", ["Todos", "historico", "sistema"], key="f_origen")
    texto = f5.text_input("Buscar por ID de pedido", key="f_texto")

    df = db.buscar_pedidos(
        desde,
        hasta,
        [nombre_a_codigo[n] for n in sel_estados],
        None if origen == "Todos" else origen,
        texto,
    )
    if df.empty:
        st.info("No hay pedidos con esos filtros.")
    else:
        st.write(f"**{len(df)} pedidos** (máximo 500 por consulta)")
        st.dataframe(
            df,
            hide_index=True,
            use_container_width=True,
            column_config={"total": st.column_config.NumberColumn("Total (BRL)", format="%.2f")},
        )
        sel = st.selectbox("Ver detalle de un pedido", df["id_pedido"].tolist())
        cab, items = db.detalle_pedido(sel)
        st.dataframe(cab, hide_index=True, use_container_width=True)
        st.dataframe(items, hide_index=True, use_container_width=True)

# =====================================================================
# 3. ACTUALIZAR ESTADO
# =====================================================================
with tab_est:
    st.caption(
        "Solo se pueden modificar pedidos creados desde el sistema. "
        "Los pedidos históricos importados son de solo lectura."
    )
    pend = db.pedidos_modificables()
    if pend.empty:
        st.info("No hay pedidos del sistema pendientes. Registra uno en la primera pestaña.")
    else:
        etiquetas = {
            r.id_pedido: f"{r.id_pedido} · {r.estado_nombre} · {r.fecha_compra[:16]}"
            for r in pend.itertuples()
        }
        id_sel = st.selectbox("Pedido", options=list(etiquetas), format_func=etiquetas.get)
        fila = pend[pend["id_pedido"] == id_sel].iloc[0]
        opciones = db.SIGUIENTE[fila["estado"]]
        nombres = dict(zip(estados["codigo"], estados["nombre"]))
        nuevo = st.selectbox("Nuevo estado", opciones, format_func=nombres.get)

        fecha_entrega = None
        if nuevo == "delivered":
            compra = datetime.strptime(fila["fecha_compra"], db.FMT)
            dia = st.date_input("Fecha de entrega", value=date.today(), min_value=compra.date())
            fecha_entrega = max(datetime.combine(dia, time(12, 0)), compra).strftime(db.FMT)

        if st.button("Actualizar estado", type="primary"):
            try:
                db.cambiar_estado(id_sel, nuevo, fecha_entrega)
            except sqlite3.Error as e:
                st.error(f"No se pudo actualizar: {e}")
            else:
                st.session_state.mensaje = f"Pedido actualizado a «{nombres[nuevo]}»."
                st.rerun()
