import sqlite3
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
DB = RAIZ / "data" / "olist.db"
SCHEMA = RAIZ / "sql" / "schema.sql"


def main():
    DB.parent.mkdir(exist_ok=True)
    con = sqlite3.connect(DB)
    con.execute("PRAGMA foreign_keys = ON")
    con.executescript(SCHEMA.read_text(encoding="utf-8"))
    con.commit()

    print("Base de datos:", DB)
    tablas = con.execute(
        "SELECT name FROM sqlite_master "
        "WHERE type = 'table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
    ).fetchall()
    print("\nTablas creadas:")
    for (t,) in tablas:
        n = con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
        print(f"  {t}: {n} filas")

    print("\nRelaciones de pedidos:")
    for fk in con.execute("PRAGMA foreign_key_list(pedidos)").fetchall():
        print(f"  pedidos.{fk[3]} -> {fk[2]}.{fk[4]}")
    con.close()


if __name__ == "__main__":
    main()
