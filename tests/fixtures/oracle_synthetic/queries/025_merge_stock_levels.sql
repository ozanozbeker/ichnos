MERGE INTO inv.stock_levels tgt
USING (SELECT p.product_id, w.id AS warehouse_id
         FROM inv.products p
        CROSS JOIN inv.warehouses w
        WHERE p.created_at >= TRUNC(SYSDATE)) src
   ON (tgt.product_id = src.product_id AND tgt.warehouse_id = src.warehouse_id)
 WHEN NOT MATCHED THEN
   INSERT (product_id, warehouse_id, qty_on_hand, updated_at)
   VALUES (src.product_id, src.warehouse_id, 0, SYSDATE);
