DELETE FROM sales.promotions pr
 WHERE pr.ends_on < ADD_MONTHS(SYSDATE, -12)
   AND NOT EXISTS (SELECT 1 FROM sales.order_promotions op WHERE op.promo_id = pr.promo_id);
