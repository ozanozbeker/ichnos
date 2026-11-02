SELECT *
  FROM (SELECT c.customer_id, c.customer_name, SUM(o.order_total) AS lifetime_value
          FROM sales.customers c
          JOIN sales.orders o ON o.customer_id = c.customer_id
         GROUP BY c.customer_id, c.customer_name
         ORDER BY lifetime_value DESC)
 WHERE ROWNUM <= 10;
