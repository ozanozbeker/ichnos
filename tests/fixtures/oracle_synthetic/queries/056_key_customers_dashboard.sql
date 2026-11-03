SELECT customer_id, customer_name, net_amount_12m
  FROM mart.v_key_customers
 ORDER BY net_amount_12m DESC;
