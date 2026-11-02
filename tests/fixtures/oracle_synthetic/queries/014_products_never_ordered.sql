SELECT product_id, sku, product_name
  FROM inv.products
 WHERE status = 'ACTIVE'
   AND product_id NOT IN (SELECT product_id FROM sales.order_lines);
