-- Dataset: snowflake.c-chain-block-gaps
-- One row per C block the share cannot account for: an absent block, a height missing between two present
-- blocks, or a short block, one present with fewer distinct receipts than its declared transaction count.
-- An absent block is dated by the present block before it; the Data API block record carries its own timestamp.
-- Run over the full history: a hole that straddles the window's first date is not seen.
-- Receipts are counted per block only on the days whose distinct receipts fall short of the declared total.
WITH blocks AS (
  SELECT blocknumber, blocktransactionlen, partition_date
  FROM AVALANCHE_PRIMARY_NETWORK_DATA.PRIMARY.C_BLOCKS
  WHERE partition_date >= %(start)s::DATE AND partition_date < %(end)s::DATE
  QUALIFY ROW_NUMBER() OVER (PARTITION BY blocknumber ORDER BY partition_date) = 1
),
sequenced AS (
  SELECT blocknumber, partition_date,
         LAG(blocknumber) OVER (ORDER BY blocknumber) AS previous_block,
         LAG(partition_date) OVER (ORDER BY blocknumber) AS previous_date
  FROM blocks
),
holes AS (
  SELECT previous_block + 1 AS low, blocknumber - 1 AS high, previous_date AS date_utc
  FROM sequenced
  WHERE blocknumber - previous_block > 1
),
offsets AS (
  SELECT SEQ4() AS n FROM TABLE(GENERATOR(ROWCOUNT => 200000))
),
absent AS (
  SELECT h.low + o.n AS block_height, h.date_utc
  FROM holes h
  JOIN offsets o ON o.n <= h.high - h.low
),
day_receipts AS (
  SELECT partition_date, COUNT(DISTINCT transactionhash) AS distinct_receipts
  FROM AVALANCHE_PRIMARY_NETWORK_DATA.PRIMARY.C_RECEIPTS
  WHERE partition_date >= %(start)s::DATE AND partition_date < %(end)s::DATE
  GROUP BY partition_date
),
short_days AS (
  SELECT b.partition_date
  FROM (SELECT partition_date, SUM(blocktransactionlen) AS declared FROM blocks GROUP BY partition_date) b
  LEFT JOIN day_receipts r USING (partition_date)
  WHERE COALESCE(r.distinct_receipts, 0) < b.declared
),
receipts AS (
  SELECT blocknumber, COUNT(DISTINCT transactionhash) AS distinct_receipts
  FROM AVALANCHE_PRIMARY_NETWORK_DATA.PRIMARY.C_RECEIPTS
  WHERE partition_date IN (SELECT partition_date FROM short_days)
  GROUP BY blocknumber
),
short AS (
  SELECT b.blocknumber AS block_height, b.partition_date AS date_utc, b.blocktransactionlen AS declared_transactions,
         COALESCE(r.distinct_receipts, 0) AS distinct_receipts
  FROM blocks b
  LEFT JOIN receipts r ON r.blocknumber = b.blocknumber
  WHERE b.partition_date IN (SELECT partition_date FROM short_days)
    AND COALESCE(r.distinct_receipts, 0) < b.blocktransactionlen
)
SELECT block_height, 'absent' AS kind, date_utc, NULL AS declared_transactions, NULL AS distinct_receipts FROM absent
UNION ALL
SELECT block_height, 'short' AS kind, date_utc, declared_transactions, distinct_receipts FROM short
ORDER BY block_height
