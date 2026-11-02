SELECT order_id, o.order_date, ol.line_no, ol.quantity
  FROM sales.orders o
  JOIN sales.order_lines ol USING (order_id)
 WHERE o.status = 'NEW';
