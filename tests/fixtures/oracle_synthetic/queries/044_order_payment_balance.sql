SELECT o.order_id,
       o.order_total,
       NVL(SUM(p.amount), 0) AS paid,
       o.order_total - NVL(SUM(p.amount), 0) AS balance
  FROM sales.orders o, sales.payments p
 WHERE p.order_id (+) = o.order_id
   AND p.currency_code (+) = o.currency_code
 GROUP BY o.order_id, o.order_total
HAVING o.order_total - NVL(SUM(p.amount), 0) > 0;
