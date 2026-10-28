PRAGMA foreign_keys = ON;

-- ===== TABLAS MAESTRAS =====

CREATE TABLE IF NOT EXISTS estados_pedido (
    codigo  TEXT PRIMARY KEY,
    nombre  TEXT NOT NULL,
    orden   INTEGER NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS categorias (
    id_categoria INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre_pt    TEXT NOT NULL UNIQUE,
    nombre_en    TEXT
);

CREATE TABLE IF NOT EXISTS clientes (
    id_cliente TEXT PRIMARY KEY,
    ciudad     TEXT NOT NULL,
    estado_uf  TEXT NOT NULL CHECK (length(estado_uf) = 2),
    origen     TEXT NOT NULL DEFAULT 'sistema' CHECK (origen IN ('historico', 'sistema'))
);

CREATE TABLE IF NOT EXISTS productos (
    id_producto  TEXT PRIMARY KEY,
    id_categoria INTEGER NOT NULL REFERENCES categorias (id_categoria),
    origen       TEXT NOT NULL DEFAULT 'sistema' CHECK (origen IN ('historico', 'sistema'))
);

-- ===== TABLAS TRANSACCIONALES =====

CREATE TABLE IF NOT EXISTS pedidos (
    id_pedido        TEXT PRIMARY KEY,
    id_cliente       TEXT NOT NULL REFERENCES clientes (id_cliente),
    estado           TEXT NOT NULL REFERENCES estados_pedido (codigo),
    fecha_compra     TEXT NOT NULL,
    fecha_aprobacion TEXT,
    fecha_envio      TEXT,
    fecha_entrega    TEXT,
    fecha_estimada   TEXT NOT NULL,
    origen           TEXT NOT NULL DEFAULT 'sistema' CHECK (origen IN ('historico', 'sistema')),
    CHECK (fecha_entrega IS NULL OR fecha_entrega >= fecha_compra),
    CHECK (estado <> 'delivered' OR fecha_entrega IS NOT NULL)
);

CREATE TABLE IF NOT EXISTS items_pedido (
    id_pedido   TEXT NOT NULL REFERENCES pedidos (id_pedido) ON DELETE CASCADE,
    num_item    INTEGER NOT NULL CHECK (num_item >= 1),
    id_producto TEXT NOT NULL REFERENCES productos (id_producto),
    precio      REAL NOT NULL CHECK (precio > 0),
    flete       REAL NOT NULL DEFAULT 0 CHECK (flete >= 0),
    PRIMARY KEY (id_pedido, num_item)
);

-- ===== INDICES PARA ACELERAR CONSULTAS DEL DASHBOARD =====

CREATE INDEX IF NOT EXISTS idx_pedidos_fecha  ON pedidos (fecha_compra);
CREATE INDEX IF NOT EXISTS idx_pedidos_estado ON pedidos (estado);
CREATE INDEX IF NOT EXISTS idx_items_producto ON items_pedido (id_producto);

-- ===== DATOS INICIALES DE LA TABLA MAESTRA DE ESTADOS =====

INSERT OR IGNORE INTO estados_pedido (codigo, nombre, orden) VALUES
    ('created',     'Creado',          1),
    ('approved',    'Aprobado',        2),
    ('invoiced',    'Facturado',       3),
    ('processing',  'En preparación',  4),
    ('shipped',     'Enviado',         5),
    ('delivered',   'Entregado',       6),
    ('canceled',    'Cancelado',       7),
    ('unavailable', 'No disponible',   8);
