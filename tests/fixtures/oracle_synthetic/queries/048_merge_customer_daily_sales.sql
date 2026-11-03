-- The USING subquery names its columns differently from the target columns.
MERGE INTO mart.customer_daily_sales tgt
USING (SELECT f.customer_id,
              f.sales_date,
              f.currency_code,
              COUNT(*) AS lines_today,
              SUM(f.units) AS units_today,
              SUM(f.net_amount) AS amount_today
         FROM mart.order_line_facts f
        WHERE f.sales_date = TRUNC(SYSDATE)
        GROUP BY f.customer_id, f.sales_date, f.currency_code) src
   ON (tgt.customer_id = src.customer_id
       AND tgt.sales_date = src.sales_date
       AND tgt.currency_code = src.currency_code)
 WHEN MATCHED THEN
   UPDATE SET tgt.line_count = src.lines_today,
              tgt.units = src.units_today,
              tgt.net_amount = src.amount_today
 WHEN NOT MATCHED THEN
   INSERT (customer_id, sales_date, currency_code, line_count, units, net_amount)
   VALUES (src.customer_id, src.sales_date, src.currency_code,
           src.lines_today, src.units_today, src.amount_today);
