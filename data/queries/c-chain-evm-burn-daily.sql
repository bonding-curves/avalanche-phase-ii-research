-- Dataset: snowflake.c-chain-evm-burn-daily
-- C-Chain EVM fees are the sum of receipt gas used times effective gas price.
-- Both quantities are integers; the product and daily total are integer wei.
WITH blocks AS (
  SELECT partition_date AS date_utc,
         COUNT(*) AS block_count,
         COUNT(DISTINCT blocknumber) AS distinct_blocks,
         MIN(blocknumber) AS first_block,
         MAX(blocknumber) AS last_block,
         SUM(blocktransactionlen) AS expected_receipts,
         MIN(blocktimestamp) AS first_epoch,
         MAX(blocktimestamp) AS last_epoch
  FROM AVALANCHE_PRIMARY_NETWORK_DATA.PRIMARY.C_BLOCKS
  WHERE partition_date >= DATEADD(day, -1, %(start)s::DATE)
    AND partition_date <= %(end)s::DATE
  GROUP BY partition_date
),
sequenced_blocks AS (
  SELECT *, LAG(last_block) OVER (ORDER BY date_utc) AS previous_last_block,
         LEAD(first_block) OVER (ORDER BY date_utc) AS next_first_block
  FROM blocks
),
receipts AS (
  SELECT partition_date AS date_utc,
         COUNT(*) AS receipt_count,
         COUNT(DISTINCT transactionhash) AS distinct_receipts,
         COUNT_IF(transactionreceiptgasused IS NULL OR transactionreceipteffectivegasprice IS NULL) AS missing_fee_inputs,
         SUM(transactionreceiptgasused * transactionreceipteffectivegasprice) AS burned_wei
  FROM AVALANCHE_PRIMARY_NETWORK_DATA.PRIMARY.C_RECEIPTS
  WHERE partition_date >= %(start)s AND partition_date < %(end)s
  GROUP BY partition_date
)
SELECT b.date_utc, COALESCE(r.burned_wei, 0) AS burned_wei,
       b.block_count, b.distinct_blocks, b.first_block, b.last_block,
       b.previous_last_block, b.next_first_block,
       b.expected_receipts, COALESCE(r.receipt_count, 0) AS receipt_count,
       COALESCE(r.distinct_receipts, 0) AS distinct_receipts,
       COALESCE(r.missing_fee_inputs, 0) AS missing_fee_inputs,
       b.first_epoch, b.last_epoch
FROM sequenced_blocks b
LEFT JOIN receipts r USING (date_utc)
WHERE b.date_utc >= %(start)s::DATE AND b.date_utc < %(end)s::DATE
ORDER BY b.date_utc
