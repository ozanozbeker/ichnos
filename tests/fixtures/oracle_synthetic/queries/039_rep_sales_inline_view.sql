SELECT e.employee_id, e.last_name, t.order_count, t.revenue
  FROM hr.employees e
  JOIN (SELECT sales_rep_id, COUNT(*) AS order_count, SUM(order_total) AS revenue
          FROM sales.orders
         WHERE status <> 'CANCELLED'
         GROUP BY sales_rep_id) t
    ON t.sales_rep_id = e.employee_id
 ORDER BY t.revenue DESC;
