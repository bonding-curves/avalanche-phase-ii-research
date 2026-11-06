-- Dataset: snowflake.p-chain-l1-fee-state-daily
-- One row per UTC date of the ACP-77 L1 validator fee state in the P-Chain block table, from block 20,107,576, the
-- first block with the state, on 2024-12-16: the day's blocks and heights, and at its last block the active L1
-- validator count, the fee each active validator has accrued since the state began, the excess gas that sets the
-- fee's price, and the fee state's capacity and excess. The day's fee is the active count before each block times the
-- rise in the accrued fee at that block, summed over the day's blocks; the rise of the first block of the window reads
-- the block before it. The window is half-open on the block timestamp.
WITH blocks AS (
  SELECT block_height, timestamp, l1_validator_active_count AS active, l1_validator_accrued_fees AS accrued,
         l1_validator_excess_gas AS excess_gas, fee_state_capacity, fee_state_excess,
         LAG(l1_validator_active_count) OVER (ORDER BY block_height) AS previous_active,
         LAG(l1_validator_accrued_fees) OVER (ORDER BY block_height) AS previous_accrued
  FROM AVALANCHE_PRIMARY_NETWORK_DATA.PRIMARY.P_BLOCKS
  WHERE block_height >= 20107576
)
SELECT timestamp::DATE AS date_utc,
       COUNT(*) AS blocks,
       MIN(block_height) AS first_block_height,
       MAX(block_height) AS last_block_height,
       MAX(timestamp) AS last_block_timestamp,
       MAX_BY(active, block_height) AS active_l1_validators,
       MAX(active) AS peak_active_l1_validators,
       MAX_BY(accrued, block_height) AS accrued_fee_navax,
       COALESCE(SUM(previous_active * (accrued - previous_accrued)), 0) AS l1_validator_fees_navax,
       MAX_BY(excess_gas, block_height) AS excess_gas,
       MAX_BY(fee_state_capacity, block_height) AS fee_state_capacity,
       MAX_BY(fee_state_excess, block_height) AS fee_state_excess
FROM blocks
WHERE timestamp >= %(start)s::TIMESTAMP_NTZ AND timestamp < %(end)s::TIMESTAMP_NTZ
GROUP BY 1
ORDER BY 1
