-- Dataset: snowflake.subnet-validator-transactions
-- Every P-Chain transaction that adds, removes, converts, registers, or disables a Subnet or L1 validator.
-- AddSubnetValidatorTx carries its node, Subnet, and period, and REMOVAL_TIME when a RemoveSubnetValidatorTx ended it
-- early. RemoveSubnetValidatorTx itself carries no node. ConvertSubnetToL1Tx carries one row per initial L1
-- validator, so its hash repeats once per node. RegisterL1ValidatorTx and DisableL1ValidatorTx carry the node and the
-- L1 validator weight. No Subnet was added by AddPermissionlessValidatorTx outside the Primary Network (checked
-- 2026-09-29), so that type is not selected.
SELECT type AS tx_type, transaction_hash, timestamp AS accepted_at, block_height, node_id, subnet_id,
       start_time, end_time, removal_time, l1_validator_weight
FROM AVALANCHE_PRIMARY_NETWORK_DATA.PRIMARY.P_TRANSACTIONS
WHERE type IN ('AddSubnetValidatorTx', 'RemoveSubnetValidatorTx', 'ConvertSubnetToL1Tx', 'RegisterL1ValidatorTx',
               'DisableL1ValidatorTx')
  AND timestamp >= %(start)s AND timestamp < %(end)s
QUALIFY ROW_NUMBER() OVER (
  PARTITION BY transaction_hash, COALESCE(node_id, '')
  ORDER BY load_timestamp DESC
) = 1
ORDER BY accepted_at, transaction_hash, node_id
