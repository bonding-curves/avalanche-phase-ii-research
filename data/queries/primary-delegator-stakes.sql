-- Dataset: snowflake.primary-delegator-stakes
-- One row per accepted delegation transaction on the Avalanche Primary Network.
-- Parameters %(start)s and %(end)s bound the acceptance timestamp as a half-open UTC interval.
-- Amounts stay in nAVAX integers here. Unit conversion happens once, in the typed transformation.
-- validator_transaction_hash names the validator staking period on the same node that contains the delegation period.
-- delegator_address is the address funding the largest share of the staked UTXOs; delegator_address_count records how many addresses funded them.
-- UTXOS repeats identical rows, so distinct UTXO identities are taken before counting and summing.
WITH delegations AS (
  SELECT
    transaction_hash,
    timestamp AS accepted_at,
    block_height,
    type AS tx_type,
    node_id,
    start_time,
    end_time,
    TRY_PARSE_JSON(metadata):validator:weight::NUMBER AS stake_navax,
    potential_reward AS potential_reward_navax,
    rewarded
  FROM AVALANCHE_PRIMARY_NETWORK_DATA.PRIMARY.P_TRANSACTIONS
  WHERE subnet_id = '11111111111111111111111111111111LpoYY'
    AND type IN ('AddDelegatorTx', 'AddPermissionlessDelegatorTx')
    AND timestamp >= %(start)s
    AND timestamp < %(end)s
),
validators AS (
  SELECT transaction_hash, node_id, start_time, end_time
  FROM AVALANCHE_PRIMARY_NETWORK_DATA.PRIMARY.P_TRANSACTIONS
  WHERE subnet_id = '11111111111111111111111111111111LpoYY'
    AND type IN ('AddValidatorTx', 'AddPermissionlessValidatorTx')
),
containing AS (
  SELECT d.transaction_hash, v.transaction_hash AS validator_transaction_hash
  FROM delegations d
  JOIN validators v
    ON v.node_id = d.node_id
   AND v.start_time <= d.start_time
   AND v.end_time >= d.end_time
  QUALIFY ROW_NUMBER() OVER (PARTITION BY d.transaction_hash ORDER BY v.start_time DESC, v.transaction_hash) = 1
),
staked_utxos AS (
  SELECT DISTINCT u.utxo_id, u.transaction_hash, u.amount, u.address
  FROM AVALANCHE_PRIMARY_NETWORK_DATA.PRIMARY.UTXOS u
  JOIN delegations d ON d.transaction_hash = u.transaction_hash
  WHERE u.staked = TRUE
),
staked AS (
  SELECT transaction_hash, COUNT(*) AS staked_utxo_count, SUM(amount) AS utxo_stake_navax, COUNT(DISTINCT address) AS delegator_address_count
  FROM staked_utxos
  GROUP BY transaction_hash
),
funding AS (
  SELECT transaction_hash, address AS delegator_address
  FROM (
    SELECT transaction_hash, address, SUM(amount) AS amount
    FROM staked_utxos
    GROUP BY transaction_hash, address
  )
  QUALIFY ROW_NUMBER() OVER (PARTITION BY transaction_hash ORDER BY amount DESC, address) = 1
)
SELECT
  d.transaction_hash,
  d.accepted_at,
  d.block_height,
  d.tx_type,
  d.node_id,
  c.validator_transaction_hash,
  f.delegator_address,
  COALESCE(s.delegator_address_count, 0) AS delegator_address_count,
  d.start_time,
  d.end_time,
  d.stake_navax,
  d.potential_reward_navax,
  d.rewarded,
  COALESCE(s.staked_utxo_count, 0) AS staked_utxo_count,
  s.utxo_stake_navax
FROM delegations d
LEFT JOIN containing c ON c.transaction_hash = d.transaction_hash
LEFT JOIN staked s ON s.transaction_hash = d.transaction_hash
LEFT JOIN funding f ON f.transaction_hash = d.transaction_hash
ORDER BY d.accepted_at, d.transaction_hash
