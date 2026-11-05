-- Dataset: allium.c-chain-daily-last-blocks
-- The last and first C-Chain block of each UTC day in Allium's block table, with the last block's hash and time and the
-- day's block count. A state read at a day's last block gives the state at the day's close. The window is half-open on
-- the block timestamp. Nothing is filtered or filled here.
SELECT timestamp::DATE AS date_utc,
       MAX(number) AS last_block_number,
       MAX_BY(hash, number) AS last_block_hash,
       MAX(timestamp) AS last_block_timestamp,
       MIN(number) AS first_block_number,
       COUNT(*) AS blocks
FROM AVALANCHE.RAW.BLOCKS
WHERE timestamp >= %(start)s::TIMESTAMP_NTZ AND timestamp < %(end)s::TIMESTAMP_NTZ
GROUP BY 1
ORDER BY 1
