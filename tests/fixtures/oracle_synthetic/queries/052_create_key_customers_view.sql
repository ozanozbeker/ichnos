CREATE VIEW mart.v_key_customers AS
SELECT *
  FROM mart.customer_segments
 WHERE segment IN ('KEY', 'STRATEGIC');
