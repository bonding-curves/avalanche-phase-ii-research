-- Dataset: snowflake.primary-burn-daily
-- One row per UTC date and chain (P or X) with the AVAX burned by that chain's transactions, in nAVAX.
-- A transaction's burn is its recorded BURNED_AVAX when the share has one that is not negative (three 2022
-- imports carry a negative record and are treated as unrecorded). Otherwise: AdvanceTimeTx and
-- RewardValidatorTx burn nothing; genesis transactions burn nothing; a transaction whose consumed AVAX UTXOs
-- are in the share burns its inputs minus its non-reward outputs; any other transaction stays unresolved and
-- is listed by hash so a separately captured Data API record can settle it. Reward outputs are excluded from
-- outputs because they are minted later and keyed by the staking transaction hash.
-- The three P-Chain transaction types that fund an L1 validator balance carry that deposit inside BURNED_AVAX;
-- the deposit is subtracted and reported apart, because it is consumed later as the continuous L1 validator
-- fee that the P-Chain counters (L1_VALIDATOR_ACCRUED_FEES times the active count) accrue between transactions.
WITH calendar AS (
  SELECT date_utc
  FROM (SELECT DATEADD(day, SEQ4(), %(start)s::DATE) AS date_utc FROM TABLE(GENERATOR(ROWCOUNT => 20000)))
  WHERE date_utc < %(end)s::DATE
),
chains AS (SELECT 'P' AS chain UNION ALL SELECT 'X'),
p_tx AS (
  SELECT transaction_hash, MIN(timestamp) AS accepted_at, ANY_VALUE(type) AS tx_type, MIN(block_height) AS block_height,
         MAX(IFF(burned_avax >= 0, burned_avax, NULL)) AS recorded_navax
  FROM AVALANCHE_PRIMARY_NETWORK_DATA.PRIMARY.P_TRANSACTIONS
  WHERE timestamp >= %(start)s AND timestamp < %(end)s
  GROUP BY 1
),
p_balances AS (
  SELECT transaction_hash, SUM(balance) AS l1_balance_navax
  FROM (SELECT DISTINCT transaction_hash, l1_validation_id, l1_validator_payg_balance AS balance
        FROM AVALANCHE_PRIMARY_NETWORK_DATA.PRIMARY.P_TRANSACTIONS
        WHERE type IN ('IncreaseL1ValidatorBalanceTx', 'RegisterL1ValidatorTx', 'ConvertSubnetToL1Tx')
          AND timestamp >= %(start)s AND timestamp < %(end)s AND l1_validator_payg_balance IS NOT NULL)
  GROUP BY 1
),
x_tx AS (
  SELECT transaction_hash, MIN(timestamp) AS accepted_at, ANY_VALUE(type) AS tx_type, MIN(block_height) AS block_height,
         MAX(IFF(burned_avax >= 0, burned_avax, NULL)) AS recorded_navax
  FROM AVALANCHE_PRIMARY_NETWORK_DATA.PRIMARY.X_TRANSACTIONS
  WHERE timestamp >= %(start)s AND timestamp < %(end)s
  GROUP BY 1
),
gaps AS (
  SELECT transaction_hash FROM p_tx WHERE recorded_navax IS NULL AND tx_type NOT IN ('AdvanceTimeTx', 'RewardValidatorTx')
  UNION ALL
  SELECT transaction_hash FROM x_tx WHERE recorded_navax IS NULL
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
),
derived AS (
  SELECT g.transaction_hash,
         SUM(IFF(u.consuming_transaction_hash = g.transaction_hash, u.amount, 0)) AS input_navax,
         SUM(IFF(u.transaction_hash = g.transaction_hash AND NOT COALESCE(u.reward, FALSE), u.amount, 0)) AS output_navax,
         COUNT_IF(u.consuming_transaction_hash = g.transaction_hash) AS input_utxos
  FROM gaps g
  LEFT JOIN utxos u ON u.consuming_transaction_hash = g.transaction_hash OR u.transaction_hash = g.transaction_hash
  GROUP BY 1
),
resolved AS (
  SELECT 'P' AS chain, t.transaction_hash, t.accepted_at,
         CASE WHEN t.recorded_navax IS NOT NULL THEN 'recorded'
              WHEN t.tx_type IN ('AdvanceTimeTx', 'RewardValidatorTx') THEN 'system'
              WHEN t.block_height = -1 OR t.accepted_at = '2020-09-10'::TIMESTAMP THEN 'genesis'
              WHEN d.input_utxos > 0 THEN 'utxo'
              ELSE 'unresolved' END AS basis,
         CASE WHEN t.recorded_navax IS NOT NULL THEN t.recorded_navax - COALESCE(b.l1_balance_navax, 0)
              WHEN t.tx_type IN ('AdvanceTimeTx', 'RewardValidatorTx') THEN 0
              WHEN t.block_height = -1 OR t.accepted_at = '2020-09-10'::TIMESTAMP THEN 0
              WHEN d.input_utxos > 0 THEN d.input_navax - d.output_navax
              ELSE NULL END AS burned_navax,
         COALESCE(b.l1_balance_navax, 0) AS l1_balance_navax
  FROM p_tx t
  LEFT JOIN p_balances b USING (transaction_hash)
  LEFT JOIN derived d USING (transaction_hash)
  UNION ALL
  SELECT 'X', t.transaction_hash, t.accepted_at,
         CASE WHEN t.recorded_navax IS NOT NULL THEN 'recorded'
              WHEN t.accepted_at = '2020-09-10'::TIMESTAMP THEN 'genesis'
              WHEN d.input_utxos > 0 THEN 'utxo'
              ELSE 'unresolved' END,
         CASE WHEN t.recorded_navax IS NOT NULL THEN t.recorded_navax
              WHEN t.accepted_at = '2020-09-10'::TIMESTAMP THEN 0
              WHEN d.input_utxos > 0 THEN d.input_navax - d.output_navax
              ELSE NULL END,
         0
  FROM x_tx t
  LEFT JOIN derived d USING (transaction_hash)
),
daily AS (
  SELECT chain, accepted_at::DATE AS date_utc,
         COUNT(*) AS transactions,
         SUM(burned_navax) AS burned_navax,
         COUNT_IF(basis = 'recorded') AS recorded_transactions,
         COUNT_IF(basis = 'system') AS system_transactions,
         COUNT_IF(basis = 'genesis') AS genesis_transactions,
         COUNT_IF(basis = 'utxo') AS utxo_derived_transactions,
         COUNT_IF(basis = 'unresolved') AS unresolved_transactions,
         LISTAGG(IFF(basis = 'unresolved', transaction_hash, NULL), ',') WITHIN GROUP (ORDER BY transaction_hash) AS unresolved_hashes,
         SUM(l1_balance_navax) AS l1_balance_deposited_navax
  FROM resolved
  GROUP BY 1, 2
),
counters AS (
  SELECT timestamp, transaction_hash, acc, cnt,
         LAG(acc) OVER (ORDER BY timestamp, transaction_hash) AS previous_acc,
         LAG(cnt) OVER (ORDER BY timestamp, transaction_hash) AS previous_cnt
  FROM (SELECT transaction_hash, timestamp, MAX(l1_validator_accrued_fees) AS acc, MAX(l1_validator_active_count) AS cnt
        FROM AVALANCHE_PRIMARY_NETWORK_DATA.PRIMARY.P_TRANSACTIONS
        WHERE l1_validator_accrued_fees IS NOT NULL
        GROUP BY 1, 2)
),
l1_fees AS (
  SELECT timestamp::DATE AS date_utc, SUM(previous_cnt * (acc - previous_acc)) AS l1_validator_fees_navax
  FROM counters
  WHERE timestamp >= %(start)s AND timestamp < %(end)s AND previous_acc IS NOT NULL
  GROUP BY 1
)
SELECT c.date_utc, ch.chain,
       COALESCE(d.transactions, 0) AS transactions,
       COALESCE(d.burned_navax, 0) AS burned_navax,
       COALESCE(d.recorded_transactions, 0) AS recorded_transactions,
       COALESCE(d.system_transactions, 0) AS system_transactions,
       COALESCE(d.genesis_transactions, 0) AS genesis_transactions,
       COALESCE(d.utxo_derived_transactions, 0) AS utxo_derived_transactions,
       COALESCE(d.unresolved_transactions, 0) AS unresolved_transactions,
       d.unresolved_hashes,
       COALESCE(d.l1_balance_deposited_navax, 0) AS l1_balance_deposited_navax,
       IFF(ch.chain = 'P', COALESCE(l.l1_validator_fees_navax, 0), 0) AS l1_validator_fees_navax
FROM calendar c
CROSS JOIN chains ch
LEFT JOIN daily d ON d.date_utc = c.date_utc AND d.chain = ch.chain
LEFT JOIN l1_fees l ON ch.chain = 'P' AND l.date_utc = c.date_utc
ORDER BY c.date_utc, ch.chain
