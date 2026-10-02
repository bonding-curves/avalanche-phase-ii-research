-- Dataset: snowflake.primary-validator-stakes
-- One row per accepted validator staking transaction on the Avalanche Primary Network.
-- Parameters %(start)s and %(end)s bound the acceptance timestamp as a half-open UTC interval.
-- Amounts stay in nAVAX integers here. Unit conversion happens once, in the typed transformation.
-- The staked-UTXO columns reconcile the transaction's declared stake weight against the UTXOS relation.
-- UTXOS repeats identical rows, so distinct UTXO identities are taken before summing.
-- reward_addresses is the transaction's list of reward owner addresses as a JSON array string; reward_address is its first
-- element and reward_address_count its length. A reward address is a proxy for the operator, never proof of one.
WITH validators AS (
  SELECT
    transaction_hash,
    timestamp AS accepted_at,
    block_height,
    type AS tx_type,
    node_id,
    start_time,
    end_time,
    TRY_PARSE_JSON(metadata):validator:weight::NUMBER AS stake_navax,
    TRY_PARSE_JSON(metadata):shares::NUMBER AS delegation_fee_shares,
    potential_reward AS potential_reward_navax,
    rewarded,
    TO_JSON(reward_addresses) AS reward_addresses,
    reward_addresses[0]::STRING AS reward_address,
    COALESCE(ARRAY_SIZE(reward_addresses), 0) AS reward_address_count
  FROM AVALANCHE_PRIMARY_NETWORK_DATA.PRIMARY.P_TRANSACTIONS
  WHERE subnet_id = '11111111111111111111111111111111LpoYY'
    AND type IN ('AddValidatorTx', 'AddPermissionlessValidatorTx')
    AND timestamp >= %(start)s
    AND timestamp < %(end)s
),
staked AS (
  SELECT transaction_hash, COUNT(*) AS staked_utxo_count, SUM(amount) AS utxo_stake_navax
  FROM (
    SELECT DISTINCT utxo_id, transaction_hash, amount
    FROM AVALANCHE_PRIMARY_NETWORK_DATA.PRIMARY.UTXOS
    WHERE staked = TRUE
  )
  GROUP BY transaction_hash
)
SELECT
  v.transaction_hash,
  v.accepted_at,
  v.block_height,
  v.tx_type,
  v.node_id,
  v.start_time,
  v.end_time,
  v.stake_navax,
  v.delegation_fee_shares,
  v.potential_reward_navax,
  v.rewarded,
  v.reward_addresses,
  v.reward_address,
  v.reward_address_count,
  COALESCE(s.staked_utxo_count, 0) AS staked_utxo_count,
  s.utxo_stake_navax
FROM validators v
LEFT JOIN staked s ON s.transaction_hash = v.transaction_hash
ORDER BY v.accepted_at, v.transaction_hash
