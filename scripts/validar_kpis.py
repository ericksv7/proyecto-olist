"""Compara los KPIs calculados con SQL contra un calculo independiente en pandas."""
import sqlite3
import sys
from pathlib import Path

import pandas as pd

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "app"))
import kpis  # noqa: E402

DESDE, HASTA, ORIGEN = "2000-01-01", "2100-01-01", "Todos"

con = sqlite3.connect(RAIZ / "data" / "olist.db")
ped = pd.read_sql_query("SELECT * FROM pedidos", con)
items = pd.read_sql_query("SELECT * FROM items_pedido", con)
prod = pd.read_sql_query("SELECT * FROM productos", con)
cat = pd.read_sql_query("SELECT * FROM categorias", con)
con.close()

# --- Calculo con pandas ---
validos = ped[~ped["estado"].isin(["canceled", "unavailable"])]
m = items.merge(validos[["id_pedido"]], on="id_pedido")
ticket_pd = m["precio"].sum() / m["id_pedido"].nunique()

ent = ped[ped["estado"] == "delivered"]
dias = (pd.to_datetime(ent["fecha_entrega"]) - pd.to_datetime(ent["fecha_compra"])).dt.total_seconds() / 86400
ciclo_pd = dias.mean()
a_tiempo_pd = (ent["fecha_entrega"] <= ent["fecha_estimada"]).mean() * 100

mc = m.merge(prod, on="id_producto").merge(cat, on="id_categoria")
unidades_pd = mc.groupby("id_categoria").size().sort_values(ascending=False)
top1_pd, total_pd = int(unidades_pd.iloc[0]), int(unidades_pd.sum())

# --- Calculo con SQL (el mismo codigo del dashboard) ---
k = kpis.kpis_globales(DESDE, HASTA, ORIGEN)
top = kpis.top_categorias(DESDE, HASTA, ORIGEN)

pruebas = [
    ("Ticket promedio", k["ticket"], ticket_pd),
    ("Ciclo de entrega (dias)", k["ciclo"], ciclo_pd),
    ("% entregas a tiempo", k["a_tiempo"], a_tiempo_pd),
    ("Unidades categoria #1", int(top.iloc[0]["unidades"]), top1_pd),
    ("Unidades totales vendidas", int(top["unidades"].sum()), total_pd),
]

print(f"{'KPI':28} {'SQL (dashboard)':>18} {'pandas':>18}  Resultado")
fallos = 0
for nombre, sql_v, pd_v in pruebas:
    ok = abs(float(sql_v) - float(pd_v)) < 1e-6
    fallos += not ok
    print(f"{nombre:28} {float(sql_v):18.4f} {float(pd_v):18.4f}  {'OK' if ok else 'DIFERENCIA'}")

print("\nTodos los KPIs coinciden." if fallos == 0 else f"\n{fallos} KPI(s) con diferencias.")
sys.exit(1 if fallos else 0)
