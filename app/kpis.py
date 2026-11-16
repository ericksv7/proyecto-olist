"""Consultas SQL de los KPIs y graficos del dashboard."""
import pandas as pd

import db

# Metas propuestas para el proyecto (no son referencias reales)
METAS = {"ticket": 130.0, "ciclo": 12.0, "a_tiempo": 90.0}
EXCLUIDOS = "('canceled', 'unavailable')"


def _filtro(desde, hasta, origen):
    where = ["date(p.fecha_compra) BETWEEN ? AND ?"]
    params = [str(desde), str(hasta)]
    if origen and origen != "Todos":
        where.append("p.origen = ?")
        params.append(origen)
    return " AND ".join(where), params


def kpis_globales(desde, hasta, origen):
    w, params = _filtro(desde, hasta, origen)
    ventas = db.consultar(
        f"""SELECT SUM(i.precio) * 1.0 / COUNT(DISTINCT p.id_pedido) AS ticket,
                   COUNT(DISTINCT p.id_pedido) AS pedidos_validos,
                   SUM(i.precio) AS ingresos
            FROM pedidos p JOIN items_pedido i ON i.id_pedido = p.id_pedido
            WHERE {w} AND p.estado NOT IN {EXCLUIDOS}""",
        params,
    ).iloc[0]
    entregas = db.consultar(
        f"""SELECT AVG(julianday(p.fecha_entrega) - julianday(p.fecha_compra)) AS ciclo,
                   AVG(p.fecha_entrega <= p.fecha_estimada) * 100 AS a_tiempo,
                   COUNT(*) AS entregados
            FROM pedidos p
            WHERE {w} AND p.estado = 'delivered'""",
        params,
    ).iloc[0]
    total = db.consultar(f"SELECT COUNT(*) AS n FROM pedidos p WHERE {w}", params).iloc[0]["n"]
    return {
        "ticket": ventas["ticket"],
        "ingresos": ventas["ingresos"],
        "pedidos_validos": int(ventas["pedidos_validos"]),
        "ciclo": entregas["ciclo"],
        "a_tiempo": entregas["a_tiempo"],
        "entregados": int(entregas["entregados"]),
        "pedidos_total": int(total),
    }


def ingresos_mensuales(desde, hasta, origen):
    w, params = _filtro(desde, hasta, origen)
    return db.consultar(
        f"""SELECT strftime('%Y-%m', p.fecha_compra) AS mes,
                   COUNT(DISTINCT p.id_pedido) AS pedidos,
                   ROUND(SUM(i.precio), 2) AS ingresos
            FROM pedidos p JOIN items_pedido i ON i.id_pedido = p.id_pedido
            WHERE {w} AND p.estado NOT IN {EXCLUIDOS}
            GROUP BY mes ORDER BY mes""",
        params,
    )


def entregas_mensuales(desde, hasta, origen):
    w, params = _filtro(desde, hasta, origen)
    return db.consultar(
        f"""SELECT strftime('%Y-%m', p.fecha_compra) AS mes,
                   COUNT(*) AS entregados,
                   ROUND(AVG(julianday(p.fecha_entrega) - julianday(p.fecha_compra)), 2) AS ciclo,
                   ROUND(AVG(p.fecha_entrega <= p.fecha_estimada) * 100, 1) AS a_tiempo
            FROM pedidos p
            WHERE {w} AND p.estado = 'delivered'
            GROUP BY mes ORDER BY mes""",
        params,
    )


def top_categorias(desde, hasta, origen):
    """Todas las categorias con unidades, ingresos y participacion (%)."""
    w, params = _filtro(desde, hasta, origen)
    df = db.consultar(
        f"""SELECT COALESCE(c.nombre_en, c.nombre_pt) AS categoria,
                   COUNT(*) AS unidades,
                   ROUND(SUM(i.precio), 2) AS ingresos
            FROM items_pedido i
            JOIN pedidos p ON p.id_pedido = i.id_pedido
            JOIN productos pr ON pr.id_producto = i.id_producto
            JOIN categorias c ON c.id_categoria = pr.id_categoria
            WHERE {w} AND p.estado NOT IN {EXCLUIDOS}
            GROUP BY c.id_categoria
            ORDER BY unidades DESC, ingresos DESC""",
        params,
    )
    if not df.empty:
        df["participacion"] = (df["unidades"] / df["unidades"].sum() * 100).round(1)
    return df


def detalle(desde, hasta, origen, estados=None):
    w, params = _filtro(desde, hasta, origen)
    if estados:
        w += " AND p.estado IN (%s)" % ",".join("?" * len(estados))
        params = params + list(estados)
    return db.consultar(
        f"""SELECT p.id_pedido,
                   substr(p.fecha_compra, 1, 16) AS compra,
                   e.nombre AS estado,
                   p.origen,
                   c.ciudad,
                   c.estado_uf AS uf,
                   COUNT(i.num_item) AS items,
                   ROUND(COALESCE(SUM(i.precio), 0), 2) AS total,
                   ROUND(julianday(p.fecha_entrega) - julianday(p.fecha_compra), 1) AS dias_entrega,
                   CASE WHEN p.fecha_entrega IS NULL THEN NULL
                        WHEN p.fecha_entrega <= p.fecha_estimada THEN 'A tiempo'
                        ELSE 'Tarde' END AS puntualidad
            FROM pedidos p
            JOIN estados_pedido e ON e.codigo = p.estado
            JOIN clientes c ON c.id_cliente = p.id_cliente
            LEFT JOIN items_pedido i ON i.id_pedido = p.id_pedido
            WHERE {w}
            GROUP BY p.id_pedido
            ORDER BY p.fecha_compra DESC""",
        params,
    )
