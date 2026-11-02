INSERT INTO sales.order_lines (order_id, line_no, product_id, quantity, unit_price)
SELECT :new_order_id, src.line_no, src.product_id, src.quantity, p.list_price
  FROM sales.order_lines src
  JOIN inv.products p ON p.product_id = src.product_id
 WHERE src.order_id = :source_order_id
   AND p.status = 'ACTIVE';
