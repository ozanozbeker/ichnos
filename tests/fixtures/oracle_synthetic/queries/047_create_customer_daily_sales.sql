CREATE TABLE mart.customer_daily_sales AS
SELECT f.customer_id,
       f.sales_date,
       f.currency_code,
       COUNT(*) AS line_count,
       SUM(f.units) AS units,
       SUM(f.net_amount) AS net_amount
  FROM mart.order_line_facts f
 GROUP BY f.customer_id, f.sales_date, f.currency_code;
