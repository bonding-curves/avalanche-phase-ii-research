-- Dataset: snowflake.primary-staking-rewards
-- One row per reward transaction, which closes one validator or delegator staking period on the Avalanche Primary Network.
-- Parameters %(start)s and %(end)s bound the reward transaction timestamp as a half-open UTC interval.
-- The staking period is named by the reward transaction's METADATA txID. Reward UTXOs are keyed by that staking
-- transaction hash, not by the reward transaction hash. UTXOS repeats identical rows, so distinct UTXO identities are summed.
-- Amounts stay in nAVAX integers here. Unit conversion and the fee transfer happen in the typed transformation.
WITH rewards AS (
  SELECT
    transaction_hash AS reward_transaction_hash,
    timestamp AS rewarded_at,
    block_height,
    TRY_PARSE_JSON(metadata):txID::STRING AS staking_transaction_hash
  FROM AVALANCHE_PRIMARY_NETWORK_DATA.PRIMARY.P_TRANSACTIONS
  WHERE type = 'RewardValidatorTx'
    AND timestamp >= %(start)s
    AND timestamp < %(end)s
),
periods AS (
  SELECT transaction_hash, type AS staking_tx_type, node_id, start_time, end_time, rewarded, potential_reward
  FROM AVALANCHE_PRIMARY_NETWORK_DATA.PRIMARY.P_TRANSACTIONS
  WHERE subnet_id = '11111111111111111111111111111111LpoYY'
    AND type IN ('AddValidatorTx', 'AddPermissionlessValidatorTx', 'AddDelegatorTx', 'AddPermissionlessDelegatorTx')
),
paid AS (
  SELECT transaction_hash, COUNT(*) AS reward_utxo_count, SUM(amount) AS realized_reward_navax
  FROM (
    SELECT DISTINCT u.utxo_id, u.transaction_hash, u.amount
    FROM AVALANCHE_PRIMARY_NETWORK_DATA.PRIMARY.UTXOS u
    JOIN rewards r ON r.staking_transaction_hash = u.transaction_hash
    WHERE u.reward = TRUE
  )
  GROUP BY transaction_hash
)
SELECT
  r.reward_transaction_hash,
  r.rewarded_at,
  r.block_height,
  r.staking_transaction_hash,
  p.staking_tx_type,
  p.node_id,
  p.start_time AS period_start_time,
  p.end_time AS period_end_time,
  p.rewarded,
  p.potential_reward AS potential_reward_navax,
  COALESCE(paid.realized_reward_navax, 0) AS realized_reward_navax,
  COALESCE(paid.reward_utxo_count, 0) AS reward_utxo_count
FROM rewards r
LEFT JOIN periods p ON p.transaction_hash = r.staking_transaction_hash
LEFT JOIN paid ON paid.transaction_hash = r.staking_transaction_hash
ORDER BY r.rewarded_at, r.reward_transaction_hash
