"""Acceso a la base de datos SQLite del proyecto."""
import sqlite3
import uuid
from contextlib import closing
from datetime import datetime
from pathlib import Path

import pandas as pd

RAIZ = Path(__file__).resolve().parent.parent
DB = RAIZ / "data" / "olist.db"
FMT = "%Y-%m-%d %H:%M:%S"

# Transiciones permitidas en el flujo de un pedido
SIGUIENTE = {
    "created": ["approved", "canceled"],
    "approved": ["invoiced", "canceled"],
    "invoiced": ["processing", "canceled"],
    "processing": ["shipped", "canceled"],
    "shipped": ["delivered", "canceled"],
}


def conectar():
    con = sqlite3.connect(DB)
    con.execute("PRAGMA foreign_keys = ON")
    return con


def consultar(sql, params=()):
    with closing(conectar()) as con:
        return pd.read_sql_query(sql, con, params=params)


# ---------- Listas para los formularios ----------

def listar_estados():
    return consultar("SELECT codigo, nombre FROM estados_pedido ORDER BY orden")


def listar_clientes():
    return consultar(
        "SELECT id_cliente, ciudad, estado_uf, origen FROM clientes ORDER BY ciudad, id_cliente"
    )


def listar_categorias():
    return consultar(
        "SELECT id_categoria, COALESCE(nombre_en, nombre_pt) AS nombre "
        "FROM categorias ORDER BY nombre"
    )


def listar_productos(id_categoria):
    df = consultar(
        "SELECT id_producto FROM productos WHERE id_categoria = ? ORDER BY id_producto",
        (int(id_categoria),),
    )
    return df["id_producto"].tolist()


# ---------- Consultas ----------

def buscar_pedidos(desde, hasta, estados=None, origen=None, texto=""):
    where = ["date(p.fecha_compra) BETWEEN ? AND ?"]
    params = [str(desde), str(hasta)]
    if estados:
        where.append("p.estado IN (%s)" % ",".join("?" * len(estados)))
        params += list(estados)
    if origen:
        where.append("p.origen = ?")
        params.append(origen)
    if texto and texto.strip():
        where.append("p.id_pedido LIKE ?")
        params.append(f"%{texto.strip()}%")
    sql = f"""
        SELECT p.id_pedido, p.fecha_compra, e.nombre AS estado, p.origen,
               c.ciudad, c.estado_uf AS uf,
               COUNT(i.num_item) AS items,
               ROUND(COALESCE(SUM(i.precio), 0), 2) AS total,
               p.fecha_estimada, p.fecha_entrega
        FROM pedidos p
        JOIN estados_pedido e ON e.codigo = p.estado
        JOIN clientes c ON c.id_cliente = p.id_cliente
        LEFT JOIN items_pedido i ON i.id_pedido = p.id_pedido
        WHERE {" AND ".join(where)}
        GROUP BY p.id_pedido
        ORDER BY p.fecha_compra DESC
        LIMIT 500
    """
    return consultar(sql, params)


def detalle_pedido(id_pedido):
    cab = consultar(
        "SELECT p.id_pedido, e.nombre AS estado, p.origen, c.ciudad, c.estado_uf AS uf, "
        "p.fecha_compra, p.fecha_aprobacion, p.fecha_envio, p.fecha_entrega, p.fecha_estimada "
        "FROM pedidos p "
        "JOIN estados_pedido e ON e.codigo = p.estado "
        "JOIN clientes c ON c.id_cliente = p.id_cliente "
        "WHERE p.id_pedido = ?",
        (id_pedido,),
    )
    items = consultar(
        "SELECT i.num_item, i.id_producto, COALESCE(c.nombre_en, c.nombre_pt) AS categoria, "
        "i.precio, i.flete "
        "FROM items_pedido i "
        "JOIN productos pr ON pr.id_producto = i.id_producto "
        "JOIN categorias c ON c.id_categoria = pr.id_categoria "
        "WHERE i.id_pedido = ? ORDER BY i.num_item",
        (id_pedido,),
    )
    return cab, items


def pedidos_modificables():
    return consultar(
        "SELECT p.id_pedido, p.estado, e.nombre AS estado_nombre, p.fecha_compra "
        "FROM pedidos p JOIN estados_pedido e ON e.codigo = p.estado "
        "WHERE p.origen = 'sistema' AND p.estado NOT IN ('delivered', 'canceled') "
        "ORDER BY p.fecha_compra DESC"
    )


# ---------- Escrituras ----------

def registrar_pedido(id_cliente, cliente_nuevo, fecha_estimada, items):
    """Guarda cliente nuevo (si aplica), pedido e items en una sola transaccion."""
    ahora = datetime.now().strftime(FMT)
    id_pedido = "SYS-" + uuid.uuid4().hex[:16]
    with closing(conectar()) as con:
        with con:  # commit automatico; rollback si hay error
            if cliente_nuevo:
                id_cliente = "SYS-C-" + uuid.uuid4().hex[:12]
                con.execute(
                    "INSERT INTO clientes (id_cliente, ciudad, estado_uf, origen) "
                    "VALUES (?, ?, ?, 'sistema')",
                    (id_cliente, cliente_nuevo["ciudad"], cliente_nuevo["uf"]),
                )
            con.execute(
                "INSERT INTO pedidos (id_pedido, id_cliente, estado, fecha_compra, "
                "fecha_estimada, origen) VALUES (?, ?, 'created', ?, ?, 'sistema')",
                (id_pedido, id_cliente, ahora, f"{fecha_estimada} 00:00:00"),
            )
            con.executemany(
                "INSERT INTO items_pedido (id_pedido, num_item, id_producto, precio, flete) "
                "VALUES (?, ?, ?, ?, ?)",
                [
                    (id_pedido, n, it["id_producto"], it["precio"], it["flete"])
                    for n, it in enumerate(items, start=1)
                ],
            )
    return id_pedido


def cambiar_estado(id_pedido, nuevo, fecha_entrega=None):
    """Actualiza el estado de un pedido creado desde el sistema."""
    ahora = datetime.now().strftime(FMT)
    sets, params = ["estado = ?"], [nuevo]
    if nuevo == "approved":
        sets.append("fecha_aprobacion = ?")
        params.append(ahora)
    elif nuevo == "shipped":
        sets.append("fecha_envio = ?")
        params.append(ahora)
    elif nuevo == "delivered":
        sets.append("fecha_entrega = ?")
        params.append(fecha_entrega or ahora)
    params.append(id_pedido)
    with closing(conectar()) as con:
        with con:
            con.execute(
                f"UPDATE pedidos SET {', '.join(sets)} "
                "WHERE id_pedido = ? AND origen = 'sistema'",
                params,
            )
