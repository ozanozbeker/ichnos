CREATE TABLE mart.customer_segments AS
WITH totals AS (
  SELECT d.customer_id,
         SUM(d.net_amount) AS net_amount_12m,
         COUNT(DISTINCT d.sales_date) AS active_days
    FROM mart.customer_daily_sales d
   WHERE d.sales_date >= ADD_MONTHS(TRUNC(SYSDATE), -12)
   GROUP BY d.customer_id
)
SELECT c.customer_id,
       c.customer_name,
       t.net_amount_12m,
       CASE
         WHEN t.net_amount_12m >= 100000 THEN 'KEY'
         WHEN t.active_days >= 12 THEN 'REGULAR'
         ELSE 'OCCASIONAL'
       END AS segment
  FROM sales.customers c
  JOIN totals t ON t.customer_id = c.customer_id;
