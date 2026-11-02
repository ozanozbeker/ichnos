SELECT c.customer_id, c.customer_name, c.created_at
  FROM sales.customers c, sales.orders o
 WHERE c.customer_id = o.customer_id (+)
   AND o.order_id IS NULL;
