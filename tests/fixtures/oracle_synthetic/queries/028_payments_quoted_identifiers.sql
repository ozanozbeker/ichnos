SELECT p.payment_id,
       p."ExternalRef",
       p.amount AS "Paid Amount",
       p.paid_at AS "Paid At"
  FROM "SALES"."PAYMENTS" p
 WHERE p."ExternalRef" IS NOT NULL;
