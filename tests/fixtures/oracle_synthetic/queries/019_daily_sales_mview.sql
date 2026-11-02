SELECT sales_date, currency_code, order_count, revenue
  FROM sales.mv_daily_sales
 WHERE sales_date BETWEEN :start_date AND :end_date
 ORDER BY sales_date;
