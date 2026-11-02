-- Two statements in one file.
SELECT COUNT(*) AS new_orders
  FROM sales.orders
 WHERE order_date >= TRUNC(SYSDATE);

SELECT COUNT(*) AS new_customers
  FROM sales.customers
 WHERE created_at >= TRUNC(SYSDATE);
