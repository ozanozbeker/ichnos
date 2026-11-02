-- ORDERS references CUSTOMER_ADDRESSES twice, once per role.
SELECT o.order_id,
       ship.city AS ship_city,
       ship_country.country_name AS ship_country,
       bill.city AS bill_city,
       bill_country.country_name AS bill_country
  FROM sales.orders o
  JOIN sales.customer_addresses ship ON ship.address_id = o.ship_to_address_id
  JOIN ref.countries ship_country ON ship_country.country_code = ship.country_code
  JOIN sales.customer_addresses bill ON bill.address_id = o.bill_to_address_id
  JOIN ref.countries bill_country ON bill_country.country_code = bill.country_code
 WHERE ship.country_code <> bill.country_code;
