# Olist · Control de ventas y entregas

Prototipo operativo y tablero de control analítico para la asignatura **Gerencia Estratégica de TI**.
Un módulo web registra pedidos de e-commerce, los guarda en una base de datos relacional junto a 1.000 pedidos
históricos reales del dataset público de Olist, y un dashboard convierte esos datos en KPIs para la toma de decisiones.

**Autor:** ericksv7 (trabajo individual)

## Caso de negocio

Una distribuidora en línea registra pedidos y entregas de forma manual, por lo que la gerencia no detecta a tiempo
los retrasos ni sabe qué categorías y regiones generan más ingresos. El sistema digitaliza el registro del pedido
(cliente, productos, estado) y ofrece un tablero con los indicadores clave.

**Usuarios:** operador de ventas (registra y actualiza pedidos) y gerente (consulta el dashboard).

## KPIs

| KPI | Fórmula | Meta propuesta* |
|---|---|---|
| Ticket promedio | Suma de precios de ítems ÷ pedidos (sin cancelados ni no disponibles) | ≥ 130 BRL |
| Ciclo de entrega | Promedio de (fecha de entrega − fecha de compra) en pedidos entregados | ≤ 12 días |
| % entregas a tiempo | Entregados en o antes de la fecha estimada ÷ entregados | ≥ 90 % |
| Categorías más vendidas | Ranking por unidades vendidas, con su participación | Top 5 |

\*Las metas son objetivos propuestos para este proyecto, no referencias oficiales. Se fijaron a partir de los
valores observados en el dataset (ciclo 12,56 días y 91,9 % a tiempo en todo el histórico de Olist).

## Tecnologías

Python · SQLite · pandas · Streamlit · Plotly · Git/GitHub

## Estructura del repositorio

    app/
      main.py              Punto de entrada y menú
      db.py                Acceso a la base de datos y operaciones
      kpis.py              Consultas SQL de los KPIs y gráficos
      vistas/
        dashboard.py       Dashboard gerencial
        operaciones.py     Registro, consulta y cambio de estado de pedidos
    scripts/
      explorar_datos.py    Exploración inicial de los CSV
      crear_bd.py          Crea la base de datos desde sql/schema.sql
      importar_csv.py      Importa 1.000 pedidos históricos con validaciones
      validar_kpis.py      Compara los KPIs de SQL contra un cálculo en pandas
    sql/schema.sql         Esquema de la base de datos
    tests/run_tests.py     Pruebas automáticas
    .streamlit/config.toml Tema visual
    requirements.txt       Dependencias
    data/                  (no versionada) CSV descargados y olist.db generada

## Modelo de datos

Seis tablas: `estados_pedido`, `categorias`, `clientes` y `productos` (maestras); `pedidos` e `items_pedido`
(transaccionales). `clientes`, `productos` y `pedidos` llevan la columna `origen` (`historico` o `sistema`) para
distinguir los datos importados de los registrados desde la aplicación. Las restricciones (precio > 0, flete ≥ 0,
entrega posterior a la compra, estado válido, llaves foráneas) se aplican en la propia base de datos.

## Instalación y ejecución

Requisitos: Python 3.10 o superior y Git.

1. Clonar el repositorio y entrar a la carpeta:

        git clone https://github.com/ericksv7/proyecto-olist.git
        cd proyecto-olist

2. Crear y activar el entorno virtual:

        python -m venv .venv
        source .venv/bin/activate        # Linux/macOS (bash o zsh)
        source .venv/bin/activate.fish   # Linux con fish
        .venv\Scripts\activate           # Windows

3. Instalar dependencias:

        pip install -r requirements.txt

4. Descargar el dataset (requiere cuenta gratuita de Kaggle):
   https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce
   Pulsar *Download*, descomprimir el ZIP y copiar los 9 archivos `.csv` en la carpeta `data/raw/`.

5. Crear la base de datos e importar los 1.000 pedidos históricos:

        python scripts/crear_bd.py
        python scripts/importar_csv.py

   La importación es repetible: ejecutarla de nuevo no duplica registros. Usa una muestra aleatoria con semilla fija
   (42), de pedidos con al menos un ítem entre enero de 2017 y agosto de 2018.

6. Iniciar la aplicación:

        streamlit run app/main.py

   Se abre en http://localhost:8501 con dos páginas: **Dashboard** y **Operaciones**.

## Pruebas

    python tests/run_tests.py      # 14 pruebas, incluida la prueba integral de punta a punta
    python scripts/validar_kpis.py # SQL vs pandas

Las pruebas usan una copia temporal de la base, por lo que no alteran los datos reales.

## Datos y reconocimiento

Dataset *Brazilian E-Commerce Public Dataset by Olist* (Kaggle), publicado por Olist. Se usan solo las tablas de
pedidos, ítems, clientes, productos y traducción de categorías. Los pedidos con identificador que empieza por `SYS-`
fueron creados desde la aplicación y no son datos históricos.

## Limitaciones

- Prototipo académico: sin autenticación ni roles.
- Los pedidos históricos son de solo lectura.
- Los precios y fletes de los pedidos nuevos los digita el operador; no hay catálogo de precios.
