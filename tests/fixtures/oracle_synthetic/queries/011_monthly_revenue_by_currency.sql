WITH paid_orders AS (
  SELECT o.order_id, o.order_date, o.currency_code
    FROM sales.orders o
   WHERE o.status IN ('PAID', 'SHIPPED')
),
line_totals AS (
  SELECT ol.order_id, SUM(ol.quantity * ol.unit_price * (1 - NVL(ol.discount_pct, 0) / 100)) AS net_amount
    FROM sales.order_lines ol
   GROUP BY ol.order_id
)
SELECT TRUNC(po.order_date, 'MM') AS month_start,
       cur.currency_name,
       SUM(lt.net_amount) AS revenue
  FROM paid_orders po
  JOIN line_totals lt ON lt.order_id = po.order_id
  JOIN ref.currencies cur ON cur.currency_code = po.currency_code
 GROUP BY TRUNC(po.order_date, 'MM'), cur.currency_name
 ORDER BY month_start;
