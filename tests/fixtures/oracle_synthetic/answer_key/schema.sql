-- Answer key for the synthetic Oracle corpus.
-- ichnos must never read this file as input. Tests compare inferred output against it.
-- The queries in ../queries run as APP_RO, a user that owns no objects, so an unprefixed
-- name resolves through the public synonyms at the end of this file. The pipeline files 045 to
-- 053 run as MART and qualify every name.

------------------------------------------------------------------------------
-- REF: lookup tables with natural character keys
------------------------------------------------------------------------------

CREATE TABLE ref.countries (
  country_code CHAR(2)      NOT NULL,
  country_name VARCHAR2(80) NOT NULL,
  region       VARCHAR2(30),
  CONSTRAINT countries_pk PRIMARY KEY (country_code)
);

CREATE TABLE ref.currencies (
  currency_code CHAR(3)      NOT NULL,
  currency_name VARCHAR2(60) NOT NULL,
  minor_units   NUMBER(1)    NOT NULL,
  CONSTRAINT currencies_pk PRIMARY KEY (currency_code)
);

------------------------------------------------------------------------------
-- HR
------------------------------------------------------------------------------

CREATE TABLE hr.departments (
  department_id    NUMBER(6)     NOT NULL,
  department_name  VARCHAR2(60)  NOT NULL,
  manager_id       NUMBER(8),
  location_country CHAR(2),
  CONSTRAINT departments_pk PRIMARY KEY (department_id)
);

CREATE TABLE hr.employees (
  employee_id   NUMBER(8)     NOT NULL,
  first_name    VARCHAR2(40)  NOT NULL,
  last_name     VARCHAR2(40)  NOT NULL,
  email         VARCHAR2(120) NOT NULL,
  hire_date     DATE          NOT NULL,
  job_title     VARCHAR2(60),
  salary        NUMBER(10, 2),
  department_id NUMBER(6),
  manager_id    NUMBER(8),
  status        CHAR(1)       NOT NULL,
  CONSTRAINT employees_pk PRIMARY KEY (employee_id),
  CONSTRAINT employees_email_uk UNIQUE (email)
);

-- No query in the corpus reads this table.
CREATE TABLE hr.job_history (
  employee_id   NUMBER(8) NOT NULL,
  start_date    DATE      NOT NULL,
  end_date      DATE      NOT NULL,
  job_title     VARCHAR2(60),
  department_id NUMBER(6),
  CONSTRAINT job_history_pk PRIMARY KEY (employee_id, start_date)
);

------------------------------------------------------------------------------
-- SALES
------------------------------------------------------------------------------

CREATE TABLE sales.customers (
  customer_id        NUMBER(10)    NOT NULL,
  customer_name      VARCHAR2(120) NOT NULL,
  email              VARCHAR2(120),
  customer_type      VARCHAR2(10)  NOT NULL,
  credit_limit       NUMBER(12, 2),
  account_manager_id NUMBER(8),
  status             VARCHAR2(10)  NOT NULL,
  created_at         DATE          NOT NULL,
  CONSTRAINT customers_pk PRIMARY KEY (customer_id)
);

CREATE TABLE sales.customer_addresses (
  address_id   NUMBER(10)    NOT NULL,
  customer_id  NUMBER(10)    NOT NULL,
  address_type VARCHAR2(4)   NOT NULL,
  line_1       VARCHAR2(120) NOT NULL,
  city         VARCHAR2(60)  NOT NULL,
  postal_code  VARCHAR2(12),
  country_code CHAR(2)       NOT NULL,
  CONSTRAINT customer_addresses_pk PRIMARY KEY (address_id)
);

CREATE TABLE sales.orders (
  order_id           NUMBER(12)    NOT NULL,
  customer_id        NUMBER(10)    NOT NULL,
  order_date         DATE          NOT NULL,
  status             VARCHAR2(10)  NOT NULL,
  sales_rep_id       NUMBER(8),
  ship_to_address_id NUMBER(10),
  bill_to_address_id NUMBER(10),
  currency_code      CHAR(3)       NOT NULL,
  order_total        NUMBER(12, 2),
  created_at         DATE          NOT NULL,
  CONSTRAINT orders_pk PRIMARY KEY (order_id)
);

CREATE TABLE sales.order_lines (
  order_id     NUMBER(12)    NOT NULL,
  line_no      NUMBER(4)     NOT NULL,
  product_id   NUMBER(10)    NOT NULL,
  quantity     NUMBER(8)     NOT NULL,
  unit_price   NUMBER(12, 2) NOT NULL,
  discount_pct NUMBER(5, 2),
  CONSTRAINT order_lines_pk PRIMARY KEY (order_id, line_no)
);

CREATE TABLE sales.payments (
  payment_id    NUMBER(12)    NOT NULL,
  order_id      NUMBER(12)    NOT NULL,
  paid_at       TIMESTAMP     NOT NULL,
  amount        NUMBER(12, 2) NOT NULL,
  currency_code CHAR(3)       NOT NULL,
  method        VARCHAR2(10)  NOT NULL,
  "ExternalRef" VARCHAR2(64),
  CONSTRAINT payments_pk PRIMARY KEY (payment_id)
);

CREATE TABLE sales.promotions (
  promo_id    NUMBER(8)     NOT NULL,
  promo_code  VARCHAR2(20)  NOT NULL,
  description VARCHAR2(200),
  starts_on   DATE          NOT NULL,
  ends_on     DATE,
  percent_off NUMBER(5, 2)  NOT NULL,
  CONSTRAINT promotions_pk PRIMARY KEY (promo_id),
  CONSTRAINT promotions_code_uk UNIQUE (promo_code)
);

-- A junction table: orders and promotions are many-to-many.
CREATE TABLE sales.order_promotions (
  order_id NUMBER(12) NOT NULL,
  promo_id NUMBER(8)  NOT NULL,
  CONSTRAINT order_promotions_pk PRIMARY KEY (order_id, promo_id)
);

CREATE SEQUENCE sales.orders_seq;
CREATE SEQUENCE sales.payments_seq;

------------------------------------------------------------------------------
-- INV
------------------------------------------------------------------------------

CREATE TABLE inv.product_categories (
  category_id        NUMBER(6)    NOT NULL,
  category_name      VARCHAR2(60) NOT NULL,
  parent_category_id NUMBER(6),
  CONSTRAINT product_categories_pk PRIMARY KEY (category_id)
);

CREATE TABLE inv.products (
  product_id   NUMBER(10)    NOT NULL,
  sku          VARCHAR2(30)  NOT NULL,
  product_name VARCHAR2(120) NOT NULL,
  category_id  NUMBER(6)     NOT NULL,
  list_price   NUMBER(12, 2) NOT NULL,
  status       VARCHAR2(12)  NOT NULL,
  created_at   DATE          NOT NULL,
  CONSTRAINT products_pk PRIMARY KEY (product_id),
  CONSTRAINT products_sku_uk UNIQUE (sku)
);

-- A legacy table: its key is ID, not WAREHOUSE_ID.
CREATE TABLE inv.warehouses (
  id             NUMBER(4)    NOT NULL,
  warehouse_code VARCHAR2(8)  NOT NULL,
  name           VARCHAR2(60) NOT NULL,
  country_code   CHAR(2)      NOT NULL,
  CONSTRAINT warehouses_pk PRIMARY KEY (id),
  CONSTRAINT warehouses_code_uk UNIQUE (warehouse_code)
);

CREATE TABLE inv.stock_levels (
  product_id    NUMBER(10) NOT NULL,
  warehouse_id  NUMBER(4)  NOT NULL,
  qty_on_hand   NUMBER(10) NOT NULL,
  reorder_point NUMBER(10),
  updated_at    DATE       NOT NULL,
  CONSTRAINT stock_levels_pk PRIMARY KEY (product_id, warehouse_id)
);

CREATE TABLE inv.shipments (
  shipment_id  NUMBER(12)   NOT NULL,
  order_id     NUMBER(12)   NOT NULL,
  warehouse_id NUMBER(4)    NOT NULL,
  ship_date    DATE,
  carrier      VARCHAR2(30),
  tracking_no  VARCHAR2(40),
  status       VARCHAR2(10) NOT NULL,
  CONSTRAINT shipments_pk PRIMARY KEY (shipment_id)
);

CREATE TABLE inv.shipment_lines (
  shipment_id NUMBER(12) NOT NULL,
  order_id    NUMBER(12) NOT NULL,
  line_no     NUMBER(4)  NOT NULL,
  qty_shipped NUMBER(8)  NOT NULL,
  CONSTRAINT shipment_lines_pk PRIMARY KEY (shipment_id, order_id, line_no)
);

------------------------------------------------------------------------------
-- MART: a reporting pipeline over the tables above. 045, 047, 049 and 050 create
-- these tables with CREATE TABLE ... AS SELECT. Oracle copies NOT NULL only for a
-- column that the select list names bare, and a DBA added the keys afterwards.
------------------------------------------------------------------------------

CREATE TABLE mart.order_line_facts (
  order_id      NUMBER(12) NOT NULL,
  line_no       NUMBER(4)  NOT NULL,
  customer_id   NUMBER(10) NOT NULL,
  sales_date    DATE,
  currency_code CHAR(3)    NOT NULL,
  product_id    NUMBER(10) NOT NULL,
  category_id   NUMBER(6)  NOT NULL,
  units         NUMBER(8)  NOT NULL,
  net_amount    NUMBER,
  CONSTRAINT order_line_facts_pk PRIMARY KEY (order_id, line_no)
);

CREATE TABLE mart.customer_daily_sales (
  customer_id   NUMBER(10) NOT NULL,
  sales_date    DATE       NOT NULL,
  currency_code CHAR(3)    NOT NULL,
  line_count    NUMBER,
  units         NUMBER,
  net_amount    NUMBER,
  CONSTRAINT customer_daily_sales_pk PRIMARY KEY (customer_id, sales_date, currency_code)
);

CREATE TABLE mart.customer_segments (
  customer_id    NUMBER(10)    NOT NULL,
  customer_name  VARCHAR2(120) NOT NULL,
  net_amount_12m NUMBER,
  segment        VARCHAR2(10),
  CONSTRAINT customer_segments_pk PRIMARY KEY (customer_id)
);

CREATE TABLE mart.lapsed_customers (
  customer_id NUMBER(10) NOT NULL,
  CONSTRAINT lapsed_customers_pk PRIMARY KEY (customer_id)
);

------------------------------------------------------------------------------
-- Foreign keys. Every relationship in the schema is declared here.
------------------------------------------------------------------------------

ALTER TABLE hr.departments ADD CONSTRAINT departments_manager_fk
  FOREIGN KEY (manager_id) REFERENCES hr.employees (employee_id);
ALTER TABLE hr.departments ADD CONSTRAINT departments_country_fk
  FOREIGN KEY (location_country) REFERENCES ref.countries (country_code);
ALTER TABLE hr.employees ADD CONSTRAINT employees_department_fk
  FOREIGN KEY (department_id) REFERENCES hr.departments (department_id);
ALTER TABLE hr.employees ADD CONSTRAINT employees_manager_fk
  FOREIGN KEY (manager_id) REFERENCES hr.employees (employee_id);
ALTER TABLE hr.job_history ADD CONSTRAINT job_history_employee_fk
  FOREIGN KEY (employee_id) REFERENCES hr.employees (employee_id);
ALTER TABLE hr.job_history ADD CONSTRAINT job_history_department_fk
  FOREIGN KEY (department_id) REFERENCES hr.departments (department_id);

ALTER TABLE sales.customers ADD CONSTRAINT customers_account_manager_fk
  FOREIGN KEY (account_manager_id) REFERENCES hr.employees (employee_id);
ALTER TABLE sales.customer_addresses ADD CONSTRAINT customer_addresses_customer_fk
  FOREIGN KEY (customer_id) REFERENCES sales.customers (customer_id);
ALTER TABLE sales.customer_addresses ADD CONSTRAINT customer_addresses_country_fk
  FOREIGN KEY (country_code) REFERENCES ref.countries (country_code);
ALTER TABLE sales.orders ADD CONSTRAINT orders_customer_fk
  FOREIGN KEY (customer_id) REFERENCES sales.customers (customer_id);
ALTER TABLE sales.orders ADD CONSTRAINT orders_sales_rep_fk
  FOREIGN KEY (sales_rep_id) REFERENCES hr.employees (employee_id);
ALTER TABLE sales.orders ADD CONSTRAINT orders_ship_to_fk
  FOREIGN KEY (ship_to_address_id) REFERENCES sales.customer_addresses (address_id);
ALTER TABLE sales.orders ADD CONSTRAINT orders_bill_to_fk
  FOREIGN KEY (bill_to_address_id) REFERENCES sales.customer_addresses (address_id);
ALTER TABLE sales.orders ADD CONSTRAINT orders_currency_fk
  FOREIGN KEY (currency_code) REFERENCES ref.currencies (currency_code);
ALTER TABLE sales.order_lines ADD CONSTRAINT order_lines_order_fk
  FOREIGN KEY (order_id) REFERENCES sales.orders (order_id);
ALTER TABLE sales.order_lines ADD CONSTRAINT order_lines_product_fk
  FOREIGN KEY (product_id) REFERENCES inv.products (product_id);
ALTER TABLE sales.payments ADD CONSTRAINT payments_order_fk
  FOREIGN KEY (order_id) REFERENCES sales.orders (order_id);
ALTER TABLE sales.payments ADD CONSTRAINT payments_currency_fk
  FOREIGN KEY (currency_code) REFERENCES ref.currencies (currency_code);
ALTER TABLE sales.order_promotions ADD CONSTRAINT order_promotions_order_fk
  FOREIGN KEY (order_id) REFERENCES sales.orders (order_id);
ALTER TABLE sales.order_promotions ADD CONSTRAINT order_promotions_promo_fk
  FOREIGN KEY (promo_id) REFERENCES sales.promotions (promo_id);

ALTER TABLE inv.product_categories ADD CONSTRAINT product_categories_parent_fk
  FOREIGN KEY (parent_category_id) REFERENCES inv.product_categories (category_id);
ALTER TABLE inv.products ADD CONSTRAINT products_category_fk
  FOREIGN KEY (category_id) REFERENCES inv.product_categories (category_id);
ALTER TABLE inv.warehouses ADD CONSTRAINT warehouses_country_fk
  FOREIGN KEY (country_code) REFERENCES ref.countries (country_code);
ALTER TABLE inv.stock_levels ADD CONSTRAINT stock_levels_product_fk
  FOREIGN KEY (product_id) REFERENCES inv.products (product_id);
ALTER TABLE inv.stock_levels ADD CONSTRAINT stock_levels_warehouse_fk
  FOREIGN KEY (warehouse_id) REFERENCES inv.warehouses (id);
ALTER TABLE inv.shipments ADD CONSTRAINT shipments_order_fk
  FOREIGN KEY (order_id) REFERENCES sales.orders (order_id);
ALTER TABLE inv.shipments ADD CONSTRAINT shipments_warehouse_fk
  FOREIGN KEY (warehouse_id) REFERENCES inv.warehouses (id);
ALTER TABLE inv.shipment_lines ADD CONSTRAINT shipment_lines_shipment_fk
  FOREIGN KEY (shipment_id) REFERENCES inv.shipments (shipment_id);
ALTER TABLE inv.shipment_lines ADD CONSTRAINT shipment_lines_order_line_fk
  FOREIGN KEY (order_id, line_no) REFERENCES sales.order_lines (order_id, line_no);

ALTER TABLE mart.order_line_facts ADD CONSTRAINT order_line_facts_order_line_fk
  FOREIGN KEY (order_id, line_no) REFERENCES sales.order_lines (order_id, line_no);
ALTER TABLE mart.order_line_facts ADD CONSTRAINT order_line_facts_customer_fk
  FOREIGN KEY (customer_id) REFERENCES sales.customers (customer_id);
ALTER TABLE mart.order_line_facts ADD CONSTRAINT order_line_facts_currency_fk
  FOREIGN KEY (currency_code) REFERENCES ref.currencies (currency_code);
ALTER TABLE mart.order_line_facts ADD CONSTRAINT order_line_facts_product_fk
  FOREIGN KEY (product_id) REFERENCES inv.products (product_id);
ALTER TABLE mart.order_line_facts ADD CONSTRAINT order_line_facts_category_fk
  FOREIGN KEY (category_id) REFERENCES inv.product_categories (category_id);
ALTER TABLE mart.customer_daily_sales ADD CONSTRAINT customer_daily_sales_customer_fk
  FOREIGN KEY (customer_id) REFERENCES sales.customers (customer_id);
ALTER TABLE mart.customer_daily_sales ADD CONSTRAINT customer_daily_sales_currency_fk
  FOREIGN KEY (currency_code) REFERENCES ref.currencies (currency_code);
ALTER TABLE mart.customer_segments ADD CONSTRAINT customer_segments_customer_fk
  FOREIGN KEY (customer_id) REFERENCES sales.customers (customer_id);
ALTER TABLE mart.lapsed_customers ADD CONSTRAINT lapsed_customers_customer_fk
  FOREIGN KEY (customer_id) REFERENCES sales.customers (customer_id);

------------------------------------------------------------------------------
-- Views
------------------------------------------------------------------------------

CREATE VIEW sales.v_order_summary AS
SELECT o.order_id,
       o.order_date,
       o.status,
       c.customer_id,
       c.customer_name,
       COUNT(ol.line_no) AS line_count,
       SUM(ol.quantity * ol.unit_price) AS gross_amount
  FROM sales.orders o
  JOIN sales.customers c ON c.customer_id = o.customer_id
  LEFT JOIN sales.order_lines ol ON ol.order_id = o.order_id
 GROUP BY o.order_id, o.order_date, o.status, c.customer_id, c.customer_name;

-- The view renames every column it exposes.
CREATE VIEW hr.emp_directory AS
SELECT e.employee_id AS emp_no,
       e.first_name || ' ' || e.last_name AS full_name,
       e.email AS work_email,
       e.department_id AS dept_no,
       d.department_name AS dept_name,
       m.first_name || ' ' || m.last_name AS manager_name
  FROM hr.employees e
  LEFT JOIN hr.departments d ON d.department_id = e.department_id
  LEFT JOIN hr.employees m ON m.employee_id = e.manager_id
 WHERE e.status = 'A';

CREATE MATERIALIZED VIEW sales.mv_daily_sales AS
SELECT TRUNC(o.order_date) AS sales_date,
       o.currency_code,
       COUNT(*) AS order_count,
       SUM(o.order_total) AS revenue
  FROM sales.orders o
 WHERE o.status <> 'CANCELLED'
 GROUP BY TRUNC(o.order_date), o.currency_code;

-- 052 creates this view with SELECT *. Oracle stores the expanded column list.
CREATE VIEW mart.v_key_customers AS
SELECT customer_id, customer_name, net_amount_12m, segment
  FROM mart.customer_segments
 WHERE segment IN ('KEY', 'STRATEGIC');

CREATE MATERIALIZED VIEW mart.mv_category_monthly AS
SELECT TRUNC(f.sales_date, 'MM') AS sales_month,
       pc.category_name,
       f.currency_code,
       SUM(f.net_amount) AS net_amount,
       COUNT(DISTINCT f.order_id) AS order_count
  FROM mart.order_line_facts f
  JOIN inv.product_categories pc ON pc.category_id = f.category_id
 GROUP BY TRUNC(f.sales_date, 'MM'), pc.category_name, f.currency_code;

------------------------------------------------------------------------------
-- Synonyms. APP_RO reads these names without a schema prefix.
------------------------------------------------------------------------------

CREATE PUBLIC SYNONYM customers FOR sales.customers;
CREATE PUBLIC SYNONYM orders FOR sales.orders;
CREATE PUBLIC SYNONYM order_lines FOR sales.order_lines;
CREATE PUBLIC SYNONYM products FOR inv.products;
-- The synonym name differs from the table name.
CREATE PUBLIC SYNONYM emp FOR hr.employees;

------------------------------------------------------------------------------
-- Database link. ARCHIVE reaches a second database that holds SALES.ORDERS
-- with the same columns as the local table and rows older than two years.
------------------------------------------------------------------------------

CREATE DATABASE LINK archive USING 'ARCHIVE';
