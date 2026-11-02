SELECT order_id, customer_id, order_date, order_total, 'CURRENT' AS source
  FROM sales.orders
 WHERE customer_id = :customer_id
UNION ALL
SELECT order_id, customer_id, order_date, order_total, 'ARCHIVE' AS source
  FROM sales.orders@archive
 WHERE customer_id = :customer_id;
