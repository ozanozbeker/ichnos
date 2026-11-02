INSERT INTO sales.orders (order_id, customer_id, order_date, status, sales_rep_id,
                          ship_to_address_id, bill_to_address_id, currency_code, created_at)
VALUES (sales.orders_seq.NEXTVAL, :customer_id, SYSDATE, 'NEW', :sales_rep_id,
        :ship_to_address_id, :bill_to_address_id, :currency_code, SYSDATE);
