SELECT cn.country_name, w.warehouse_code, COUNT(s.shipment_id) AS shipments
  FROM inv.warehouses w
  JOIN ref.countries cn ON cn.country_code = w.country_code
  LEFT JOIN inv.shipments s ON s.warehouse_id = w.id
 GROUP BY cn.country_name, w.warehouse_code;
