-- Audit null P_TRANSACTIONS.BURNED_AVAX values against non-reward AVAX UTXOs.
-- A staking transaction may also be the UTXOS.TRANSACTION_HASH for its later
-- reward output; that REWARD=true output is minted later and must be excluded.
WITH gaps AS (
  SELECT transaction_hash, ANY_VALUE(type) AS tx_type,
         MIN(timestamp) AS accepted_at, MIN(block_height) AS block_height
  FROM AVALANCHE_PRIMARY_NETWORK_DATA.PRIMARY.P_TRANSACTIONS
  WHERE type NOT IN ('RewardValidatorTx', 'AdvanceTimeTx')
  GROUP BY transaction_hash
  HAVING MAX(burned_avax) IS NULL
),
utxos AS (
  SELECT utxo_id, transaction_hash, consuming_transaction_hash, amount, reward
  FROM AVALANCHE_PRIMARY_NETWORK_DATA.PRIMARY.UTXOS
  WHERE asset_id = 'FvwEAhmxKfeiG8SnEvq42hc6whRyY3EFYAvebMqDNDGCgxN5Z'
    AND (transaction_hash IN (SELECT transaction_hash FROM gaps)
         OR consuming_transaction_hash IN (SELECT transaction_hash FROM gaps))
  QUALIFY ROW_NUMBER() OVER (
    PARTITION BY utxo_id ORDER BY last_updated DESC NULLS LAST, load_timestamp DESC NULLS LAST
  ) = 1
)
SELECT g.transaction_hash, g.tx_type, g.accepted_at, g.block_height,
       SUM(IFF(u.consuming_transaction_hash = g.transaction_hash, u.amount, 0)) AS input_navax,
       SUM(IFF(u.transaction_hash = g.transaction_hash AND NOT COALESCE(u.reward, FALSE), u.amount, 0)) AS output_navax,
       COUNT_IF(u.consuming_transaction_hash = g.transaction_hash) AS input_utxos,
       COUNT_IF(u.transaction_hash = g.transaction_hash AND NOT COALESCE(u.reward, FALSE)) AS output_utxos,
       COUNT_IF(u.transaction_hash = g.transaction_hash AND u.reward) AS excluded_reward_utxos
FROM gaps g
LEFT JOIN utxos u ON u.consuming_transaction_hash = g.transaction_hash
                 OR u.transaction_hash = g.transaction_hash
GROUP BY g.transaction_hash, g.tx_type, g.accepted_at, g.block_height
ORDER BY g.accepted_at, g.transaction_hash
