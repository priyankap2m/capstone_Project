-- Mamaearth Returns & Growth Intelligence Pipeline
-- Part 1, Task 3: Reports
--
-- Run against the RAW (uncleaned) data loaded by schema.sql + seed_data.sql.
-- Every result below was produced by actually executing these queries with
-- NOTE on NULL handling: seed_data.sql loads orders via generated INSERT
-- statements (see sql/seed_data.sql), so blank discount_pct/rating cells
-- already arrive as SQL NULL. If you instead load orders.csv with SQLite's
-- `.import` CLI, every blank cell lands as an empty string '', not NULL --
-- confirm with `SELECT typeof(rating) FROM orders;` before running anything
-- below. Left uncorrected this silently breaks report (b), since
-- COUNT(rating) would then count those empty strings as present. If you use
-- `.import`, run this cleanup immediately after it and before any report:
--   UPDATE orders SET discount_pct = NULL WHERE discount_pct = '';
--   UPDATE orders SET rating = NULL WHERE rating = '';

-- =====================================================================
-- a) Order totals: COUNT(*), total revenue, average order value.
--    revenue per row = quantity * price * (1 - discount_pct/100), NULL
--    discount treated as 0% via COALESCE. Joins orders to products.
-- =====================================================================
-- Result:
-- total_orders | total_revenue | avg_order_value
-- 180          | 99860.2       | 554.78
SELECT
    COUNT(*) AS total_orders,
    ROUND(SUM(o.quantity * p.price * (1 - COALESCE(o.discount_pct, 0) / 100.0)), 2) AS total_revenue,
    ROUND(AVG(o.quantity * p.price * (1 - COALESCE(o.discount_pct, 0) / 100.0)), 2) AS avg_order_value
FROM orders o
JOIN products p ON p.product_id = o.product_id;


-- =====================================================================
-- b) COUNT(*) vs COUNT(column): COUNT(*) counts every row including NULLs;
--    COUNT(rating) skips NULL ratings, so the difference is the number of
--    orders with no rating yet.
-- =====================================================================
-- Result:
-- total_orders | rated_orders | unrated_orders
-- 180          | 165          | 15
SELECT
    COUNT(*) AS total_orders,
    COUNT(rating) AS rated_orders,
    COUNT(*) - COUNT(rating) AS unrated_orders
FROM orders;


-- =====================================================================
-- c) LEFT JOIN with a genuine zero-match row: find any customer with zero
--    orders. Verified independently with a NOT IN query so the LEFT JOIN
--    result isn't trusted blindly.
-- =====================================================================
-- Result (query 1, LEFT JOIN):
-- customer_id | name   | order_count
-- C045        | Vihaan | 0
SELECT
    c.customer_id,
    c.name,
    COUNT(o.order_id) AS order_count
FROM customers c
LEFT JOIN orders o ON o.customer_id = c.customer_id
GROUP BY c.customer_id, c.name
HAVING COUNT(o.order_id) = 0;

-- Result (query 2, NOT IN -- confirms the same customer):
-- customer_id | name
-- C045        | Vihaan
SELECT customer_id, name
FROM customers
WHERE customer_id NOT IN (SELECT DISTINCT customer_id FROM orders);


-- =====================================================================
-- d) GROUP BY + HAVING: return rate by city, filtered to cities above 20%.
-- =====================================================================
-- Result (3 rows, ordered by return_rate_pct DESC):
-- city      | total_orders | returned_orders | return_rate_pct
-- Jaipur    | 19           | 8               | 42.1
-- Lucknow   | 49           | 15              | 30.6
-- Bangalore | 33           | 8               | 24.2
-- (Mumbai 17.9% and Delhi 17.4% are correctly excluded by HAVING > 20.)
SELECT
    c.city,
    COUNT(*) AS total_orders,
    SUM(o.returned) AS returned_orders,
    ROUND(100.0 * SUM(o.returned) / COUNT(*), 1) AS return_rate_pct
FROM orders o
JOIN customers c ON c.customer_id = o.customer_id
GROUP BY c.city
HAVING return_rate_pct > 20
ORDER BY return_rate_pct DESC;


-- =====================================================================
-- e) Ranking with ORDER BY + LIMIT/OFFSET: top spenders by customer.
--    Tie-break on customer_id ASC after total_spend DESC: SQLite (like
--    most SQL engines) does not guarantee row order among ties on a single
--    ORDER BY key, so without a deterministic tie-break, ranks 3-5 could
--    return a different row set (or a different order) each run -- and, in
--    particular, could disagree with a separately-run LIMIT 5 query,
--    which is exactly the property the second query below depends on.
-- =====================================================================
-- Result (top 5):
-- customer_id | name    | total_spend
-- C043        | Reyansh | 12920.0
-- C026        | Isha    | 8371.6
-- C008        | Meera   | 4564.6
-- C011        | Arjun   | 4111.0
-- C042        | Sanya   | 3785.0
SELECT
    c.customer_id,
    c.name,
    ROUND(SUM(o.quantity * p.price * (1 - COALESCE(o.discount_pct, 0) / 100.0)), 2) AS total_spend
FROM orders o
JOIN products p ON p.product_id = o.product_id
JOIN customers c ON c.customer_id = o.customer_id
GROUP BY c.customer_id, c.name
ORDER BY total_spend DESC, c.customer_id ASC
LIMIT 5;

-- Result (ranks 3-5, LIMIT 3 OFFSET 2 -- exactly the last three rows above,
-- in the same order, confirming the tie-break makes both queries agree):
-- customer_id | name   | total_spend
-- C008        | Meera  | 4564.6
-- C011        | Arjun  | 4111.0
-- C042        | Sanya  | 3785.0
SELECT
    c.customer_id,
    c.name,
    ROUND(SUM(o.quantity * p.price * (1 - COALESCE(o.discount_pct, 0) / 100.0)), 2) AS total_spend
FROM orders o
JOIN products p ON p.product_id = o.product_id
JOIN customers c ON c.customer_id = o.customer_id
GROUP BY c.customer_id, c.name
ORDER BY total_spend DESC, c.customer_id ASC
LIMIT 3 OFFSET 2;


-- =====================================================================
-- f) Three-table JOIN with GROUP BY: revenue and order count by category.
--    customers is joined too (though only orders+products are strictly
--    needed here) to confirm the three-way join compiles cleanly, since
--    Part 3's findings depend on the same join shape working correctly.
-- =====================================================================
-- Result (ordered by category_revenue DESC):
-- category     | order_count | category_revenue
-- Haircare     | 54          | 44956.1
-- Skincare     | 60          | 27346.0
-- Babycare     | 30          | 16805.0
-- PersonalCare | 36          | 10753.1
SELECT
    p.category,
    COUNT(*) AS order_count,
    ROUND(SUM(o.quantity * p.price * (1 - COALESCE(o.discount_pct, 0) / 100.0)), 2) AS category_revenue
FROM orders o
JOIN products p ON p.product_id = o.product_id
JOIN customers c ON c.customer_id = o.customer_id
GROUP BY p.category
ORDER BY category_revenue DESC;


-- =====================================================================
-- g) LIKE pattern match: customers whose name starts with 'A'.
-- =====================================================================
-- Result: 10 rows -- C001 Aarav, C003 Aditi, C004 Ananya, C011 Arjun,
-- C021 Aryan, C030 Anika, C031 Aditya, C036 Aisha, C041 Ayaan, C044 Aria.
SELECT customer_id, name
FROM customers
WHERE name LIKE 'A%'
ORDER BY customer_id;


-- =====================================================================
-- h) DISTINCT acquisition sources used across all customers.
-- =====================================================================
-- Result: 4 rows -- Ad, Organic, Referral, Social.
SELECT DISTINCT acquisition_source
FROM customers
ORDER BY acquisition_source;


-- =====================================================================
-- i) ALTER TABLE + UPDATE with CASE: derive a loyalty_tier from city_tier.
-- =====================================================================
ALTER TABLE customers ADD COLUMN loyalty_tier VARCHAR(10);

UPDATE customers
SET loyalty_tier = CASE WHEN city_tier = 1 THEN 'Gold' ELSE 'Silver' END;

-- Result:
-- loyalty_tier | COUNT(*)
-- Gold         | 28
-- Silver       | 17
SELECT loyalty_tier, COUNT(*)
FROM customers
GROUP BY loyalty_tier;
