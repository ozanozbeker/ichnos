SELECT customer_id, customer_name, email
  FROM sales.customers
 WHERE status = 'ACTIVE'
 ORDER BY customer_name;
