SELECT o.order_id,
       o.order_date,
       o.order_total,
       c.customer_name
  FROM sales.orders o
  JOIN sales.customers c
    ON c.customer_id = o.customer_id
 WHERE o.status = 'PAID';
