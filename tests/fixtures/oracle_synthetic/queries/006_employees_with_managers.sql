SELECT e.employee_id,
       e.last_name,
       m.last_name AS manager_last_name
  FROM hr.employees e, hr.employees m
 WHERE e.manager_id = m.employee_id (+)
   AND e.status = 'A';
