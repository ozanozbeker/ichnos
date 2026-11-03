-- SEGMENT derives from itself and from another column of the same table.
UPDATE mart.customer_segments
   SET segment = CASE WHEN net_amount_12m >= 250000 THEN 'STRATEGIC' ELSE segment END
 WHERE segment = 'KEY';
