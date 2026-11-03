CREATE TABLE mart.order_line_facts AS
SELECT o.order_id,
       ol.line_no,
       o.customer_id,
       TRUNC(o.order_date) AS sales_date,
       o.currency_code,
       ol.product_id,
       p.category_id,
       ol.quantity AS units,
       ol.quantity * ol.unit_price * (1 - NVL(ol.discount_pct, 0) / 100) AS net_amount
  FROM sales.orders o
  JOIN sales.order_lines ol ON ol.order_id = o.order_id
  JOIN inv.products p ON p.product_id = ol.product_id
 WHERE o.status <> 'CANCELLED';
