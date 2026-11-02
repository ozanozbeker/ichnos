SELECT s.shipment_id, s.order_id, s.carrier, s.tracking_no, s.ship_date
  FROM inv.shipments s
 WHERE s.status = 'SHIPPED'
 ORDER BY s.ship_date DESC
 FETCH FIRST 50 ROWS ONLY;
