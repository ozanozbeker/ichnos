SELECT o.order_id,
       o.status,
       (SELECT MAX(p.paid_at)
          FROM sales.payments p
         WHERE p.order_id = o.order_id) AS last_paid_at
  FROM sales.orders o
 WHERE o.order_date >= ADD_MONTHS(SYSDATE, -1);
