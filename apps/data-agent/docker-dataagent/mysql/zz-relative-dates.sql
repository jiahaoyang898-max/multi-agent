-- ============================================================================
-- 把演示数据整体平移到「最后一天 = 今天」（幂等，可反复执行）
-- ----------------------------------------------------------------------------
-- 背景：
--   dw 的演示订单原本固定在 2025-01-01 ~ 2025-03-31。而查询链路中的
--   add_extra_context 节点会把「系统当天日期」注入提示词，大模型据此生成
--   WHERE d.year = 2026 AND d.month = 9 之类的相对时间条件，结果永远命中 0 行，
--   前端就显示「查询成功，但该条件下没有匹配到任何数据行」。
--
-- 做法：
--   把 fact_order（含 order_id 里内嵌的日期）与 dim_date 整体平移 delta 天，
--   使数据窗口变成「最近约 3 个月、最后一天 = 今天」。
--   这样「上个月 / 最近 30 天 / 本季度 / 上季度」等相对时间提问都能命中数据。
--
-- 幂等性：
--   再次执行时 delta = 0，数据不动，可安全重复运行。
--
-- 适用：MySQL 8.0
-- ============================================================================

-- 偏移量 = 今天 - 数据中最后一天
SET @anchor_old := (SELECT MAX(STR_TO_DATE(CAST(date_id AS CHAR), '%Y%m%d')) FROM fact_order);
SET @delta := IFNULL(DATEDIFF(CURDATE(), @anchor_old), 0);

-- 1) 平移订单日期
UPDATE fact_order
SET date_id = CAST(DATE_FORMAT(
        DATE_ADD(STR_TO_DATE(CAST(date_id AS CHAR), '%Y%m%d'), INTERVAL @delta DAY),
        '%Y%m%d') AS UNSIGNED);

-- 2) 同步订单号里内嵌的日期：ORD + YYYYMMDD + 3 位序号
UPDATE fact_order
SET order_id = CONCAT('ORD', CAST(date_id AS CHAR), SUBSTRING(order_id, 12));

-- 3) 依据平移后的订单日期重建日期维度
--    注意：这里刻意用「派生表」而不是 TEMPORARY TABLE 来造数字序列，
--    因为 MySQL 不允许在同一条语句里多次引用同一个临时表（会报 1137 Can't reopen table）。
DELETE FROM dim_date;

INSERT INTO dim_date (date_id, year, quarter, month, day)
SELECT CAST(DATE_FORMAT(x.dt, '%Y%m%d') AS UNSIGNED),
       YEAR(x.dt),
       CONCAT('Q', QUARTER(x.dt)),
       MONTH(x.dt),
       DAY(x.dt)
FROM (
         SELECT DATE_ADD(
                        (SELECT MIN(STR_TO_DATE(CAST(date_id AS CHAR), '%Y%m%d')) FROM fact_order),
                        INTERVAL t.n DAY) AS dt
         FROM (SELECT a.n + b.n * 10 + c.n * 100 AS n
               FROM (SELECT 0 n UNION SELECT 1 UNION SELECT 2 UNION SELECT 3 UNION SELECT 4
                     UNION SELECT 5 UNION SELECT 6 UNION SELECT 7 UNION SELECT 8 UNION SELECT 9) a
               JOIN (SELECT 0 n UNION SELECT 1 UNION SELECT 2 UNION SELECT 3 UNION SELECT 4
                     UNION SELECT 5 UNION SELECT 6 UNION SELECT 7 UNION SELECT 8 UNION SELECT 9) b
               JOIN (SELECT 0 n UNION SELECT 1 UNION SELECT 2 UNION SELECT 3 UNION SELECT 4
                     UNION SELECT 5 UNION SELECT 6 UNION SELECT 7 UNION SELECT 8 UNION SELECT 9) c
              ) t
     ) x
WHERE x.dt <= (SELECT MAX(STR_TO_DATE(CAST(date_id AS CHAR), '%Y%m%d')) FROM fact_order);
