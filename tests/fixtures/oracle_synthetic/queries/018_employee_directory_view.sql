SELECT ed.full_name, ed.work_email, ed.dept_name, ed.manager_name
  FROM hr.emp_directory ed
  JOIN hr.departments d
    ON d.department_id = ed.dept_no
 WHERE d.location_country = 'DE';
