-- Dataset: snowflake.c-chain-evm-burn-daily
-- C-Chain EVM fees are the sum of receipt gas used times effective gas price.
-- Both quantities are integers; the product and daily total are integer wei.
-- The share repeats some blocks and receipts (two days of 2025 are loaded twice) and lacks some blocks and some
-- receipts (three days of 2023 and about forty of 2025), so blocks and receipts are read once each, and the burn
-- is summed only over complete blocks: blocks whose distinct receipts equal their declared transaction count.
-- A short block (fewer receipts than transactions) and an absent block (a height missing between the day's first
-- and last) are counted and left to the C-Chain block-fee capture, which reads those blocks from the Data API.
WITH blocks AS (
  SELECT blocknumber, blocktransactionlen, blocktimestamp, partition_date
  FROM AVALANCHE_PRIMARY_NETWORK_DATA.PRIMARY.C_BLOCKS
  WHERE partition_date >= DATEADD(day, -1, %(start)s::DATE)
    AND partition_date <= %(end)s::DATE
  QUALIFY ROW_NUMBER() OVER (PARTITION BY blocknumber ORDER BY partition_date, blocktimestamp) = 1
),
receipts AS (
  SELECT blocknumber, transactionhash, transactionreceiptgasused, transactionreceipteffectivegasprice
  FROM AVALANCHE_PRIMARY_NETWORK_DATA.PRIMARY.C_RECEIPTS
  WHERE partition_date >= %(start)s AND partition_date < %(end)s
  QUALIFY ROW_NUMBER() OVER (PARTITION BY transactionhash ORDER BY blocknumber) = 1
),
receipt_rows AS (
  SELECT partition_date AS date_utc, COUNT(*) AS receipt_rows
  FROM AVALANCHE_PRIMARY_NETWORK_DATA.PRIMARY.C_RECEIPTS
  WHERE partition_date >= %(start)s AND partition_date < %(end)s
  GROUP BY partition_date
),
per_block AS (
  SELECT b.partition_date AS date_utc, b.blocknumber, b.blocktransactionlen, b.blocktimestamp,
         COUNT(r.transactionhash) AS receipts,
         COUNT_IF(r.transactionhash IS NOT NULL AND (r.transactionreceiptgasused IS NULL OR r.transactionreceipteffectivegasprice IS NULL)) AS missing_fee_inputs,
         COALESCE(SUM(r.transactionreceiptgasused * r.transactionreceipteffectivegasprice), 0) AS burned_wei
  FROM blocks b
  LEFT JOIN receipts r ON r.blocknumber = b.blocknumber
  GROUP BY 1, 2, 3, 4
),
daily AS (
  SELECT date_utc,
         SUM(IFF(receipts = blocktransactionlen, burned_wei, 0)) AS burned_wei,
         COUNT(*) AS block_count,
         MIN(blocknumber) AS first_block,
         MAX(blocknumber) AS last_block,
         COUNT_IF(receipts < blocktransactionlen) AS short_blocks,
         SUM(IFF(receipts < blocktransactionlen, blocktransactionlen, 0)) AS short_block_transactions,
         SUM(blocktransactionlen) AS expected_receipts,
         SUM(receipts) AS distinct_receipts,
         SUM(missing_fee_inputs) AS missing_fee_inputs,
         MIN(blocktimestamp) AS first_epoch,
         MAX(blocktimestamp) AS last_epoch
  FROM per_block
  GROUP BY date_utc
),
sequenced AS (
  SELECT *,
         last_block - first_block + 1 - block_count AS absent_blocks,
         LAG(last_block) OVER (ORDER BY date_utc) AS previous_last_block,
         LEAD(first_block) OVER (ORDER BY date_utc) AS next_first_block
  FROM daily
)
SELECT d.date_utc, d.burned_wei,
       d.block_count, d.first_block, d.last_block, d.absent_blocks, d.short_blocks, d.short_block_transactions,
       d.previous_last_block, d.next_first_block,
       d.expected_receipts, COALESCE(r.receipt_rows, 0) AS receipt_rows, d.distinct_receipts,
       d.missing_fee_inputs, d.first_epoch, d.last_epoch
FROM sequenced d
LEFT JOIN receipt_rows r USING (date_utc)
WHERE d.date_utc >= %(start)s::DATE AND d.date_utc < %(end)s::DATE
ORDER BY d.date_utc
