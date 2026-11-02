SELECT o.order_id, o.order_total
  FROM sales.orders o
 WHERE EXISTS (SELECT 1
                 FROM sales.payments p
                WHERE p.order_id = o.order_id
                  AND p.method = 'CARD');
