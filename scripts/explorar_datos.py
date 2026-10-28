import pandas as pd

RAW = "data/raw/"

fechas = [
    "order_purchase_timestamp",
    "order_approved_at",
    "order_delivered_carrier_date",
    "order_delivered_customer_date",
    "order_estimated_delivery_date",
]
orders = pd.read_csv(RAW + "olist_orders_dataset.csv", parse_dates=fechas)
items = pd.read_csv(RAW + "olist_order_items_dataset.csv")
products = pd.read_csv(RAW + "olist_products_dataset.csv")
customers = pd.read_csv(RAW + "olist_customers_dataset.csv")
trad = pd.read_csv(RAW + "product_category_name_translation.csv")

print("=== PEDIDOS ===")
print("Filas:", len(orders), "| order_id duplicados:", orders["order_id"].duplicated().sum())
print("\nPedidos por estado:")
print(orders["order_status"].value_counts())
print("\nValores nulos por columna:")
print(orders.isna().sum())
print("\nRango de fechas de compra:",
      orders["order_purchase_timestamp"].min(), "->", orders["order_purchase_timestamp"].max())

print("\n=== ENTREGADOS ===")
ent = orders[orders["order_status"] == "delivered"].dropna(
    subset=["order_delivered_customer_date"]
)
print("Entregados con fecha de entrega:", len(ent))
dias = (ent["order_delivered_customer_date"] - ent["order_purchase_timestamp"]).dt.total_seconds() / 86400
print("Ciclo de entrega en dias (compra -> entrega):")
print(dias.describe().round(2))
a_tiempo = (ent["order_delivered_customer_date"] <= ent["order_estimated_delivery_date"]).mean() * 100
print("% entregados a tiempo en el historico completo:", round(a_tiempo, 1))

print("\n=== ITEMS ===")
print("Filas:", len(items), "| pedidos distintos:", items["order_id"].nunique())
print("Duplicados (order_id, order_item_id):", items.duplicated(["order_id", "order_item_id"]).sum())
print(items[["price", "freight_value"]].describe().round(2))

print("\n=== PRODUCTOS ===")
print("Filas:", len(products), "| sin categoria:", products["product_category_name"].isna().sum())
sin_trad = ~products["product_category_name"].dropna().isin(trad["product_category_name"])
print("Categorias sin traduccion al ingles:", sin_trad.sum())

print("\n=== CLIENTES ===")
print("Filas:", len(customers),
      "| customer_id unicos:", customers["customer_id"].nunique(),
      "| customer_unique_id unicos:", customers["customer_unique_id"].nunique())
