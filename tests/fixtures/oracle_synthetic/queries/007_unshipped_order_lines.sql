-- The (+) sits on the left of each condition, so SHIPMENT_LINES is the optional side.
SELECT ol.order_id, ol.line_no, ol.quantity, NVL(sl.qty_shipped, 0) AS qty_shipped
  FROM sales.order_lines ol, inv.shipment_lines sl
 WHERE sl.order_id (+) = ol.order_id
   AND sl.line_no (+) = ol.line_no
   AND NVL(sl.qty_shipped, 0) < ol.quantity;
