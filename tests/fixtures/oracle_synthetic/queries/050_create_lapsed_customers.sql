CREATE TABLE mart.lapsed_customers AS
SELECT d.customer_id
  FROM mart.customer_daily_sales d
 WHERE d.sales_date >= ADD_MONTHS(TRUNC(SYSDATE), -24)
MINUS
SELECT d.customer_id
  FROM mart.customer_daily_sales d
 WHERE d.sales_date >= ADD_MONTHS(TRUNC(SYSDATE), -12);
