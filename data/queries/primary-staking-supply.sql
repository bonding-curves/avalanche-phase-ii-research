-- Dataset: snowflake.primary-staking-supply
-- One row per staking transaction on the Avalanche Primary Network with the AVAX supply context the protocol used
-- when it computed the transaction's potential reward.
-- Parameters %(start)s and %(end)s bound the acceptance timestamp as a half-open UTC interval.
-- P_BLOCKS.CURRENT_SUPPLY is a JSON object keyed by subnet ID holding the supply after the block. The protocol
-- supply counter rises by each new staker's potential reward and falls by the potential reward of each staker
-- that ends unrewarded, so the supply before a transaction is the previous block's supply plus the deltas of
-- earlier supply-changing transactions in the same block. Both the previous and own block supplies are kept so
-- the backtest can report where the provider's block semantics differ by protocol regime.
WITH staking AS (
  SELECT transaction_hash, timestamp AS accepted_at, type AS tx_type, block_hash, block_height, tx_block_position
  FROM AVALANCHE_PRIMARY_NETWORK_DATA.PRIMARY.P_TRANSACTIONS
  WHERE subnet_id = '11111111111111111111111111111111LpoYY'
    AND type IN ('AddValidatorTx', 'AddPermissionlessValidatorTx', 'AddDelegatorTx', 'AddPermissionlessDelegatorTx')
    AND timestamp >= %(start)s
    AND timestamp < %(end)s
),
additions AS (
  SELECT block_hash, tx_block_position, potential_reward AS delta
  FROM AVALANCHE_PRIMARY_NETWORK_DATA.PRIMARY.P_TRANSACTIONS
  WHERE subnet_id = '11111111111111111111111111111111LpoYY'
    AND type IN ('AddValidatorTx', 'AddPermissionlessValidatorTx', 'AddDelegatorTx', 'AddPermissionlessDelegatorTx')
),
removals AS (
  SELECT r.block_hash, r.tx_block_position, -s.potential_reward AS delta
  FROM AVALANCHE_PRIMARY_NETWORK_DATA.PRIMARY.P_TRANSACTIONS r
  JOIN AVALANCHE_PRIMARY_NETWORK_DATA.PRIMARY.P_TRANSACTIONS s
    ON s.transaction_hash = TRY_PARSE_JSON(r.metadata):txID::STRING
  WHERE r.type = 'RewardValidatorTx'
    AND s.rewarded = FALSE
),
deltas AS (
  SELECT block_hash, tx_block_position, SUM(delta) AS delta
  FROM (SELECT * FROM additions UNION ALL SELECT * FROM removals)
  GROUP BY block_hash, tx_block_position
),
positioned AS (
  SELECT
    block_hash,
    tx_block_position,
    COALESCE(SUM(delta) OVER (PARTITION BY block_hash ORDER BY tx_block_position ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING), 0) AS prior_delta,
    SUM(delta) OVER (PARTITION BY block_hash) AS total_delta
  FROM deltas
),
supply AS (
  SELECT block_hash, block_height, PARSE_JSON(current_supply):"11111111111111111111111111111111LpoYY"::NUMBER AS supply_navax
  FROM AVALANCHE_PRIMARY_NETWORK_DATA.PRIMARY.P_BLOCKS
)
SELECT
  st.transaction_hash,
  st.accepted_at,
  st.tx_type,
  st.block_height,
  st.tx_block_position,
  previous.supply_navax AS previous_block_supply_navax,
  own.supply_navax AS block_supply_navax,
  p.prior_delta AS in_block_prior_delta_navax,
  p.total_delta AS in_block_total_delta_navax
FROM staking st
LEFT JOIN supply own ON own.block_hash = st.block_hash
LEFT JOIN supply previous ON previous.block_height = st.block_height - 1
LEFT JOIN positioned p ON p.block_hash = st.block_hash AND p.tx_block_position = st.tx_block_position
ORDER BY st.accepted_at, st.transaction_hash
