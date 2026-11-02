SELECT c.country_name, d.department_name, mgr.last_name AS manager_last_name
  FROM hr.departments d
  JOIN ref.countries c ON c.country_code = d.location_country
  LEFT JOIN hr.employees mgr ON mgr.employee_id = d.manager_id
 ORDER BY c.country_name, d.department_name;
