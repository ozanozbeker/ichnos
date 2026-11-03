SELECT sales_month, category_name, net_amount, order_count
  FROM mart.mv_category_monthly
 WHERE currency_code = 'EUR'
 ORDER BY sales_month, category_name;
