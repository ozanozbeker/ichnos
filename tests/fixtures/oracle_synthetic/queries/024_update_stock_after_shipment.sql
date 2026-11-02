UPDATE inv.stock_levels sl
   SET sl.qty_on_hand = sl.qty_on_hand - (SELECT SUM(shl.qty_shipped)
                                            FROM inv.shipment_lines shl
                                            JOIN sales.order_lines ol
                                              ON ol.order_id = shl.order_id
                                             AND ol.line_no = shl.line_no
                                           WHERE shl.shipment_id = :shipment_id
                                             AND ol.product_id = sl.product_id),
       sl.updated_at = SYSDATE
 WHERE sl.warehouse_id = (SELECT s.warehouse_id FROM inv.shipments s WHERE s.shipment_id = :shipment_id);
