SELECT LEVEL AS depth,
       category_id,
       LPAD(' ', 2 * (LEVEL - 1)) || category_name AS category_path
  FROM inv.product_categories
 START WITH parent_category_id IS NULL
CONNECT BY PRIOR category_id = parent_category_id
 ORDER SIBLINGS BY category_name;
