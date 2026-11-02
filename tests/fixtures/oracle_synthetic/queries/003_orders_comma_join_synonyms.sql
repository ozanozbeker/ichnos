-- Old-style join through public synonyms, with no schema prefix.
select orders.order_id, orders.order_date, customers.customer_name, customers.customer_type
  from orders, customers
 where orders.customer_id = customers.customer_id
   and customers.customer_type = 'TRADE'
