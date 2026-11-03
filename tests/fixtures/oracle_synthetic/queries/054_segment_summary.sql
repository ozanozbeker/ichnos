SELECT segment,
       COUNT(*) AS customer_count,
       SUM(net_amount_12m) AS net_amount
  FROM mart.customer_segments
 GROUP BY segment
 ORDER BY net_amount DESC;
