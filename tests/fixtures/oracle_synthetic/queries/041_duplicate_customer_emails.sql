SELECT c.ROWID AS row_address, c.customer_id, c.email
  FROM sales.customers c
 WHERE c.email IN (SELECT email
                     FROM sales.customers
                    GROUP BY email
                   HAVING COUNT(*) > 1);
