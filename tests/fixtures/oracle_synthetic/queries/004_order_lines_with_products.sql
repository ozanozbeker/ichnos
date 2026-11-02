SELECT ol.order_id,
       ol.line_no,
       p.sku,
       p.product_name,
       ol.quantity,
       ol.unit_price
  FROM sales.order_lines ol
  LEFT JOIN inv.products p
    ON p.product_id = ol.product_id
 WHERE ol.order_id = :order_id
 ORDER BY ol.line_no;
