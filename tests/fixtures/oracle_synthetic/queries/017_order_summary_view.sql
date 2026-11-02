SELECT v.order_id, v.customer_name, v.line_count, v.gross_amount
  FROM sales.v_order_summary v
 WHERE v.status = 'NEW'
   AND v.line_count > 5;
