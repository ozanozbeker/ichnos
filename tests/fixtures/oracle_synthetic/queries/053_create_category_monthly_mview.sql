CREATE MATERIALIZED VIEW mart.mv_category_monthly AS
SELECT TRUNC(f.sales_date, 'MM') AS sales_month,
       pc.category_name,
       f.currency_code,
       SUM(f.net_amount) AS net_amount,
       COUNT(DISTINCT f.order_id) AS order_count
  FROM mart.order_line_facts f
  JOIN inv.product_categories pc ON pc.category_id = f.category_id
 GROUP BY TRUNC(f.sales_date, 'MM'), pc.category_name, f.currency_code;
