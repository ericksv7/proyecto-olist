"""Pruebas automaticas del sistema. Usa una copia temporal de la base de datos."""
import shutil
import sqlite3
import sys
import tempfile
from contextlib import closing
from datetime import date, timedelta
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "app"))
import db  # noqa: E402
import kpis  # noqa: E402

ORIGINAL = RAIZ / "data" / "olist.db"
if not ORIGINAL.exists():
    sys.exit("No existe data/olist.db. Ejecuta crear_bd.py e importar_csv.py primero.")

db.DB = Path(tempfile.mkdtemp()) / "copia_pruebas.db"
shutil.copy(ORIGINAL, db.DB)

D, H, O = "2000-01-01", "2100-01-01", "Todos"
resultados = []


def prueba(nombre):
    def deco(f):
        try:
            f()
            resultados.append((nombre, True, ""))
        except Exception as e:  # noqa: BLE001
            resultados.append((nombre, False, f"{type(e).__name__}: {e}"))
        return f
    return deco


def rechaza(sql, params=()):
    """True si la base rechaza la operacion por una restriccion de integridad."""
    con = db.conectar()
    try:
        with con:
            con.execute(sql, params)
        return False
    except sqlite3.IntegrityError:
        return True
    finally:
        con.close()


def escalar(sql, params=()):
    return db.consultar(sql, params).iloc[0, 0]


ID_HIST = escalar("SELECT id_pedido FROM pedidos WHERE origen = 'historico' LIMIT 1")
ID_CLI = escalar("SELECT id_cliente FROM clientes LIMIT 1")
ID_PROD = escalar("SELECT id_producto FROM productos LIMIT 1")
INS_PEDIDO = (
    "INSERT INTO pedidos (id_pedido, id_cliente, estado, fecha_compra, fecha_estimada, "
    "fecha_entrega, origen) VALUES (?, ?, ?, ?, ?, ?, 'sistema')"
)


@prueba("P01 Existen las 6 tablas del modelo")
def _():
    t = set(db.consultar(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
    )["name"])
    esperadas = {"estados_pedido", "categorias", "clientes", "productos", "pedidos", "items_pedido"}
    assert esperadas <= t, f"faltan: {esperadas - t}"


@prueba("P02 Hay entre 200 y 1.000 pedidos historicos importados")
def _():
    n = escalar("SELECT COUNT(*) FROM pedidos WHERE origen = 'historico'")
    assert 200 <= n <= 1000, f"hay {n}"


@prueba("P03 Sin violaciones de llaves foraneas")
def _():
    with closing(db.conectar()) as con:
        assert con.execute("PRAGMA foreign_key_check").fetchall() == []


@prueba("P04 Sin pedidos duplicados")
def _():
    assert escalar("SELECT COUNT(*) - COUNT(DISTINCT id_pedido) FROM pedidos") == 0


@prueba("P05 Rechaza un item con precio 0")
def _():
    assert rechaza(
        "INSERT INTO items_pedido (id_pedido, num_item, id_producto, precio, flete) "
        "VALUES (?, 99, ?, 0, 0)", (ID_HIST, ID_PROD))


@prueba("P06 Rechaza un item con flete negativo")
def _():
    assert rechaza(
        "INSERT INTO items_pedido (id_pedido, num_item, id_producto, precio, flete) "
        "VALUES (?, 98, ?, 10, -5)", (ID_HIST, ID_PROD))


@prueba("P07 Rechaza un pedido 'entregado' sin fecha de entrega")
def _():
    assert rechaza(INS_PEDIDO, ("T-1", ID_CLI, "delivered", "2024-01-01 10:00:00",
                                "2024-01-10 00:00:00", None))


@prueba("P08 Rechaza una entrega anterior a la compra")
def _():
    assert rechaza(INS_PEDIDO, ("T-2", ID_CLI, "delivered", "2024-01-10 10:00:00",
                                "2024-01-20 00:00:00", "2024-01-05 10:00:00"))


@prueba("P09 Rechaza un estado que no existe")
def _():
    assert rechaza(INS_PEDIDO, ("T-3", ID_CLI, "inventado", "2024-01-01 10:00:00",
                                "2024-01-10 00:00:00", None))


@prueba("P10 Rechaza un id de pedido repetido")
def _():
    assert rechaza(INS_PEDIDO, (ID_HIST, ID_CLI, "created", "2024-01-01 10:00:00",
                                "2024-01-10 00:00:00", None))


@prueba("P11 Un pedido historico no se puede modificar desde la aplicacion")
def _():
    antes = escalar("SELECT estado FROM pedidos WHERE id_pedido = ?", (ID_HIST,))
    db.cambiar_estado(ID_HIST, "canceled")
    despues = escalar("SELECT estado FROM pedidos WHERE id_pedido = ?", (ID_HIST,))
    assert antes == despues, f"cambio de {antes} a {despues}"


@prueba("P12 PRUEBA INTEGRAL: registrar -> guardar -> reflejar en KPIs -> entregar")
def _():
    a = kpis.kpis_globales(D, H, O)
    total_antes = escalar("SELECT COUNT(*) FROM pedidos")

    items = [
        {"id_producto": ID_PROD, "precio": 100.0, "flete": 10.0},
        {"id_producto": ID_PROD, "precio": 50.0, "flete": 5.0},
    ]
    nuevo = db.registrar_pedido(ID_CLI, None, date.today() + timedelta(days=12), items)

    # Guardado en la base
    fila = db.consultar("SELECT estado, origen FROM pedidos WHERE id_pedido = ?", (nuevo,)).iloc[0]
    assert (fila["estado"], fila["origen"]) == ("created", "sistema")
    assert escalar("SELECT COUNT(*) FROM items_pedido WHERE id_pedido = ?", (nuevo,)) == 2
    assert escalar("SELECT COUNT(*) FROM pedidos") == total_antes + 1

    # Reflejado en los KPIs (pedido creado: cuenta en ventas, aun no en entregas)
    b = kpis.kpis_globales(D, H, O)
    assert b["pedidos_total"] == a["pedidos_total"] + 1
    assert b["pedidos_validos"] == a["pedidos_validos"] + 1
    assert abs(b["ingresos"] - (a["ingresos"] + 150.0)) < 1e-6
    esperado = (a["ingresos"] + 150.0) / (a["pedidos_validos"] + 1)
    assert abs(b["ticket"] - esperado) < 1e-6, "ticket promedio incorrecto"
    assert b["entregados"] == a["entregados"]

    # Avance del estado hasta la entrega
    for estado in ["approved", "invoiced", "processing", "shipped", "delivered"]:
        db.cambiar_estado(nuevo, estado)
    c = kpis.kpis_globales(D, H, O)
    assert c["entregados"] == a["entregados"] + 1
    dias = escalar(
        "SELECT julianday(fecha_entrega) - julianday(fecha_compra) FROM pedidos WHERE id_pedido = ?",
        (nuevo,))
    ciclo_esp = (a["ciclo"] * a["entregados"] + dias) / (a["entregados"] + 1)
    assert abs(c["ciclo"] - ciclo_esp) < 1e-6, "ciclo de entrega incorrecto"
    a_tiempo_esp = (a["a_tiempo"] * a["entregados"] / 100 + 1) / (a["entregados"] + 1) * 100
    assert abs(c["a_tiempo"] - a_tiempo_esp) < 1e-6, "% a tiempo incorrecto"


@prueba("P13 Las tablas y graficos del dashboard cuadran con los KPIs")
def _():
    k = kpis.kpis_globales(D, H, O)
    assert len(kpis.detalle(D, H, O)) == k["pedidos_total"], "tabla detalle != total"
    assert int(kpis.pedidos_por_estado(D, H, O)["pedidos"].sum()) == k["pedidos_total"]
    sql_indep = escalar(
        "SELECT SUM(i.precio) FROM items_pedido i JOIN pedidos p ON p.id_pedido = i.id_pedido "
        "WHERE p.estado NOT IN ('canceled', 'unavailable')")
    assert abs(sql_indep - k["ingresos"]) < 1e-6, "ingresos no coinciden"


@prueba("P14 El filtro por origen separa historico y sistema")
def _():
    h = kpis.kpis_globales(D, H, "historico")["pedidos_total"]
    s = kpis.kpis_globales(D, H, "sistema")["pedidos_total"]
    assert h + s == kpis.kpis_globales(D, H, O)["pedidos_total"]
    assert s >= 1, "debe existir el pedido creado en P12"


print(f"\n{'Prueba':72} Resultado")
print("-" * 90)
fallos = 0
for nombre, ok, detalle in resultados:
    fallos += not ok
    print(f"{nombre:72} {'APROBADA' if ok else 'FALLO  ' + detalle}")
print("-" * 90)
print(f"{len(resultados) - fallos} de {len(resultados)} pruebas aprobadas")
sys.exit(1 if fallos else 0)
