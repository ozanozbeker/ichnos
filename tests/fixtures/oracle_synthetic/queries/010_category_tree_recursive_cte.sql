WITH category_tree (category_id, category_name, root_id, depth) AS (
  SELECT pc.category_id, pc.category_name, pc.category_id, 1
    FROM inv.product_categories pc
   WHERE pc.parent_category_id IS NULL
  UNION ALL
  SELECT child.category_id, child.category_name, ct.root_id, ct.depth + 1
    FROM inv.product_categories child
    JOIN category_tree ct
      ON child.parent_category_id = ct.category_id
)
SELECT ct.root_id, ct.category_name, ct.depth, COUNT(p.product_id) AS product_count
  FROM category_tree ct
  LEFT JOIN inv.products p
    ON p.category_id = ct.category_id
 GROUP BY ct.root_id, ct.category_name, ct.depth;
