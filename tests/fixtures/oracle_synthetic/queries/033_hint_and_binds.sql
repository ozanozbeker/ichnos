SELECT /*+ INDEX(o orders_customer_ix) */
       o.order_id, o.order_date, o.status
  FROM sales.orders o
 WHERE o.customer_id = :customer_id
   AND o.order_date BETWEEN :start_date AND :end_date;
