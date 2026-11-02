SELECT customer_id, order_id, order_date
  FROM (SELECT o.customer_id,
               o.order_id,
               o.order_date,
               ROW_NUMBER() OVER (PARTITION BY o.customer_id ORDER BY o.order_date DESC) AS rn
          FROM sales.orders o)
 WHERE rn = 1;
