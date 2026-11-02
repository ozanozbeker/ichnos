SELECT o.order_id,
       DECODE(o.status, 'NEW', 'Open', 'PAID', 'Paid', 'SHIPPED', 'Done', 'Other') AS status_label,
       CASE WHEN o.order_total > 10000 THEN 'LARGE' ELSE 'STANDARD' END AS size_band,
       NVL(o.sales_rep_id, -1) AS rep_id
  FROM sales.orders o
 WHERE o.order_date > SYSDATE - 30;
