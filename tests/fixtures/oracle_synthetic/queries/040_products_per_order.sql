SELECT ol.order_id,
       LISTAGG(p.sku, ', ') WITHIN GROUP (ORDER BY ol.line_no) AS skus
  FROM order_lines ol
  JOIN products p ON p.product_id = ol.product_id
 GROUP BY ol.order_id
HAVING COUNT(*) > 1;
