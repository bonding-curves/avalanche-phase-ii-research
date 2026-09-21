-- Dataset: snowflake.primary-burn-events
-- One P- or X-Chain transaction per row, with its recorded AVAX burn in nAVAX.
-- A P-Chain transaction may appear more than once in the share. Prefer the row
-- with a non-null burn, then the latest loaded row; never sum repeated rows.
WITH p AS (
  SELECT transaction_hash, timestamp AS accepted_at, block_height, type AS tx_type,
         burned_avax AS burned_navax, fee AS fee_navax
  FROM AVALANCHE_PRIMARY_NETWORK_DATA.PRIMARY.P_TRANSACTIONS
  WHERE timestamp >= %(start)s AND timestamp < %(end)s
  QUALIFY ROW_NUMBER() OVER (
    PARTITION BY transaction_hash
    ORDER BY burned_avax DESC NULLS LAST, load_timestamp DESC
  ) = 1
),
x AS (
  SELECT transaction_hash, timestamp AS accepted_at, block_height, type AS tx_type,
         burned_avax AS burned_navax, fee AS fee_navax
  FROM AVALANCHE_PRIMARY_NETWORK_DATA.PRIMARY.X_TRANSACTIONS
  WHERE timestamp >= %(start)s AND timestamp < %(end)s
  QUALIFY ROW_NUMBER() OVER (
    PARTITION BY transaction_hash
    ORDER BY burned_avax DESC NULLS LAST, load_timestamp DESC
  ) = 1
)
SELECT 'P' AS chain, transaction_hash, accepted_at, block_height, tx_type,
       burned_navax, fee_navax
FROM p
UNION ALL
SELECT 'X' AS chain, transaction_hash, accepted_at, block_height, tx_type,
       burned_navax, fee_navax
FROM x
ORDER BY accepted_at, chain, transaction_hash
