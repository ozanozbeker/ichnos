SELECT w.warehouse_code,
       w.name AS warehouse_name,
       s.product_id,
       s.qty_on_hand,
       s.reorder_point
  FROM inv.stock_levels s
  JOIN inv.warehouses w
    ON w.id = s.warehouse_id
 WHERE s.qty_on_hand <= s.reorder_point;
