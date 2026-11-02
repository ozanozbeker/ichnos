SELECT o.order_id, o.order_date, pr.promo_code, pr.percent_off
  FROM sales.orders o
  JOIN sales.order_promotions op ON op.order_id = o.order_id
  JOIN sales.promotions pr ON pr.promo_id = op.promo_id
 WHERE pr.promo_code LIKE 'SPRING%';
