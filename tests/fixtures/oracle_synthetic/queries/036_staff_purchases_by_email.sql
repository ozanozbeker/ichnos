-- The join on EMAIL matches values. No foreign key links the two columns.
SELECT e.employee_id, e.last_name, c.customer_id, c.customer_name
  FROM hr.employees e
  JOIN sales.customers c
    ON LOWER(c.email) = LOWER(e.email);
