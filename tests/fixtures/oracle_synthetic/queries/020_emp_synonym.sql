-- EMP is a public synonym for HR.EMPLOYEES.
SELECT emp.employee_id, emp.first_name, emp.last_name, d.department_name
  FROM emp
  JOIN hr.departments d
    ON d.department_id = emp.department_id
 WHERE emp.hire_date >= DATE '2024-01-01';
