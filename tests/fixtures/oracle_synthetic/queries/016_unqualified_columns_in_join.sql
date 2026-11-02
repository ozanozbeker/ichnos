-- Each unqualified column exists in only one of the two tables.
SELECT order_id, order_date, customer_name, credit_limit
  FROM sales.orders o
  JOIN sales.customers c
    ON o.customer_id = c.customer_id
 WHERE order_total > credit_limit;
