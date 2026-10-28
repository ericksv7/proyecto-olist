"""Importa un subconjunto de 1.000 pedidos reales de Olist a SQLite."""
import sqlite3
from pathlib import Path

import pandas as pd

RAIZ = Path(__file__).resolve().parent.parent
RAW = RAIZ / "data" / "raw"
DB = RAIZ / "data" / "olist.db"
RECHAZADOS = RAIZ / "data" / "rechazados_importacion.csv"

N_PEDIDOS = 1000
SEMILLA = 42
DESDE = "2017-01-01"
HASTA = "2018-08-31 23:59:59"
FMT = "%Y-%m-%d %H:%M:%S"
COLS_FECHA = [
    "order_purchase_timestamp",
    "order_approved_at",
    "order_delivered_carrier_date",
    "order_delivered_customer_date",
    "order_estimated_delivery_date",
]


def filas(df):
    """Convierte un DataFrame en filas simples; los valores vacios pasan a None."""
    return [
        tuple(None if pd.isna(v) else v for v in fila)
        for fila in df.itertuples(index=False, name=None)
    ]


def insertar(con, sql, datos):
    """Ejecuta el INSERT y devuelve cuantas filas nuevas se guardaron."""
    antes = con.total_changes
    con.executemany(sql, datos)
    return con.total_changes - antes


def main():
    if not DB.exists():
        raise SystemExit("No existe data/olist.db. Ejecuta primero: python scripts/crear_bd.py")

    orders = pd.read_csv(RAW / "olist_orders_dataset.csv", parse_dates=COLS_FECHA)
    items = pd.read_csv(RAW / "olist_order_items_dataset.csv")
    products = pd.read_csv(RAW / "olist_products_dataset.csv")
    customers = pd.read_csv(RAW / "olist_customers_dataset.csv")
    trad = pd.read_csv(RAW / "product_category_name_translation.csv", encoding="utf-8-sig")

    rechazados = []  # (tipo, id, motivo)

    # 1. Seleccion de la muestra
    candidatos = orders[
        orders["order_id"].isin(items["order_id"])
        & (orders["order_purchase_timestamp"] >= DESDE)
        & (orders["order_purchase_timestamp"] <= HASTA)
    ]
    muestra = candidatos.sample(n=N_PEDIDOS, random_state=SEMILLA).copy()
    print(f"Pedidos candidatos ({DESDE[:7]} a 2018-08): {len(candidatos)}")
    print(f"Pedidos en la muestra: {len(muestra)} (semilla {SEMILLA})")

    # 2. Validacion de pedidos
    sin_fecha = (muestra["order_status"] == "delivered") & muestra[
        "order_delivered_customer_date"
    ].isna()
    entrega_antes = (
        muestra["order_delivered_customer_date"] < muestra["order_purchase_timestamp"]
    )
    sin_cliente = ~muestra["customer_id"].isin(customers["customer_id"])
    for mascara, motivo in [
        (sin_fecha, "estado entregado sin fecha de entrega"),
        (entrega_antes, "fecha de entrega anterior a la compra"),
        (sin_cliente, "cliente inexistente"),
    ]:
        for oid in muestra.loc[mascara, "order_id"]:
            rechazados.append(("pedido", oid, motivo))
    muestra = muestra[~(sin_fecha | entrega_antes | sin_cliente)].copy()

    # 3. Validacion de items
    it = items[items["order_id"].isin(muestra["order_id"])].copy()
    valido = (
        (it["price"] > 0)
        & (it["freight_value"] >= 0)
        & it["product_id"].isin(products["product_id"])
    )
    for oid in it.loc[~valido, "order_id"]:
        rechazados.append(("item", oid, "precio, flete o producto invalido"))
    it = it[valido].copy()

    sin_items = ~muestra["order_id"].isin(it["order_id"])
    for oid in muestra.loc[sin_items, "order_id"]:
        rechazados.append(("pedido", oid, "sin items validos"))
    muestra = muestra[~sin_items].copy()

    # 4. Preparar tablas
    cl = customers[customers["customer_id"].isin(muestra["customer_id"])]
    mapa = cl.set_index("customer_id")["customer_unique_id"]
    muestra["id_cliente"] = muestra["customer_id"].map(mapa)
    clientes = cl.drop_duplicates("customer_unique_id")[
        ["customer_unique_id", "customer_city", "customer_state"]
    ]

    pr = products[products["product_id"].isin(it["product_id"])][
        ["product_id", "product_category_name"]
    ].copy()
    pr["product_category_name"] = pr["product_category_name"].fillna("sin_categoria")

    trad_map = dict(zip(trad["product_category_name"], trad["product_category_name_english"]))
    trad_map["sin_categoria"] = "uncategorized"
    cats = [(c, trad_map.get(c, c)) for c in sorted(pr["product_category_name"].unique())]

    for c in COLS_FECHA:
        muestra[c] = muestra[c].dt.strftime(FMT)
    pedidos = muestra[
        [
            "order_id",
            "id_cliente",
            "order_status",
            "order_purchase_timestamp",
            "order_approved_at",
            "order_delivered_carrier_date",
            "order_delivered_customer_date",
            "order_estimated_delivery_date",
        ]
    ]
    it = it[["order_id", "order_item_id", "product_id", "price", "freight_value"]]

    # 5. Insercion
    con = sqlite3.connect(DB)
    con.execute("PRAGMA foreign_keys = ON")

    n_cat = insertar(con, "INSERT OR IGNORE INTO categorias (nombre_pt, nombre_en) VALUES (?, ?)", cats)
    id_cat = dict(con.execute("SELECT nombre_pt, id_categoria FROM categorias").fetchall())

    n_cli = insertar(
        con,
        "INSERT OR IGNORE INTO clientes (id_cliente, ciudad, estado_uf, origen) "
        "VALUES (?, ?, ?, 'historico')",
        filas(clientes),
    )
    prod_filas = [(p, id_cat[c]) for p, c in pr.itertuples(index=False, name=None)]
    n_prod = insertar(
        con,
        "INSERT OR IGNORE INTO productos (id_producto, id_categoria, origen) "
        "VALUES (?, ?, 'historico')",
        prod_filas,
    )
    n_ped = insertar(
        con,
        "INSERT OR IGNORE INTO pedidos (id_pedido, id_cliente, estado, fecha_compra, "
        "fecha_aprobacion, fecha_envio, fecha_entrega, fecha_estimada, origen) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'historico')",
        filas(pedidos),
    )
    n_it = insertar(
        con,
        "INSERT OR IGNORE INTO items_pedido (id_pedido, num_item, id_producto, precio, flete) "
        "VALUES (?, ?, ?, ?, ?)",
        filas(it),
    )
    con.commit()

    # 6. Informe
    print("\n=== INFORME DE IMPORTACION ===")
    print(f"Categorias nuevas: {n_cat}")
    print(f"Clientes nuevos:   {n_cli}")
    print(f"Productos nuevos:  {n_prod}")
    print(f"Pedidos nuevos:    {n_ped}")
    print(f"Items nuevos:      {n_it}")
    print(f"Registros rechazados: {len(rechazados)}")
    if rechazados:
        rech = pd.DataFrame(rechazados, columns=["tipo", "id", "motivo"])
        rech.to_csv(RECHAZADOS, index=False)
        print(rech.groupby(["tipo", "motivo"]).size().to_string())
        print("Detalle en:", RECHAZADOS)

    print("\n=== VERIFICACION EN LA BASE ===")
    for t in ["estados_pedido", "categorias", "clientes", "productos", "pedidos", "items_pedido"]:
        print(f"  {t}: {con.execute(f'SELECT COUNT(*) FROM {t}').fetchone()[0]} filas")
    fk = con.execute("PRAGMA foreign_key_check").fetchall()
    print("Violaciones de llaves foraneas:", len(fk))
    rango = con.execute("SELECT MIN(fecha_compra), MAX(fecha_compra) FROM pedidos").fetchone()
    print("Rango de fechas de compra:", rango[0], "->", rango[1])
    print("Pedidos por estado:")
    for estado, n in con.execute(
        "SELECT estado, COUNT(*) FROM pedidos GROUP BY estado ORDER BY COUNT(*) DESC"
    ):
        print(f"  {estado}: {n}")

    print("\n=== VISTA PREVIA DE KPIs (SQL) ===")
    ticket = con.execute(
        "SELECT SUM(i.precio) / COUNT(DISTINCT p.id_pedido) "
        "FROM pedidos p JOIN items_pedido i ON i.id_pedido = p.id_pedido "
        "WHERE p.estado NOT IN ('canceled', 'unavailable')"
    ).fetchone()[0]
    ciclo, a_tiempo = con.execute(
        "SELECT AVG(julianday(fecha_entrega) - julianday(fecha_compra)), "
        "AVG(fecha_entrega <= fecha_estimada) * 100 "
        "FROM pedidos WHERE estado = 'delivered'"
    ).fetchone()
    print(f"Ticket promedio:       {ticket:.2f} BRL")
    print(f"Ciclo de entrega:      {ciclo:.2f} dias")
    print(f"% entregas a tiempo:   {a_tiempo:.1f} %")
    con.close()


if __name__ == "__main__":
    main()
