-- Two reports in one file.
SELECT sales_date,
       currency_code,
       SUM(line_count) AS line_count,
       SUM(net_amount) AS net_amount
  FROM mart.customer_daily_sales
 WHERE sales_date >= TRUNC(SYSDATE) - 7
 GROUP BY sales_date, currency_code
 ORDER BY sales_date;

SELECT l.customer_id, c.customer_name, c.email
  FROM mart.lapsed_customers l
  JOIN sales.customers c ON c.customer_id = l.customer_id;
