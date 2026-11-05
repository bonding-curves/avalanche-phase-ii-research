-- Dataset: allium.identity-labels-atomic
-- Allium's entity label of each C-Chain address that sent an export to the P-Chain or received an import from it in the
-- window, one row per labelled address, with the time of its first such transaction. Labels name entities such as
-- exchanges and custodians, as Allium attributes them, with the attribution date. The window is half-open on the block
-- timestamp of the atomic transactions. An address without a label has no row.
WITH atomic AS (
  SELECT CASE WHEN source_chain = 'c-chain' THEN from_address ELSE to_address END AS address,
         MIN(block_timestamp) AS first_atomic_at
  FROM AVALANCHE.RAW.SUBNET_TRANSACTIONS
  WHERE 'p-chain' IN (source_chain, destination_chain)
    AND block_timestamp >= %(start)s::TIMESTAMP_NTZ AND block_timestamp < %(end)s::TIMESTAMP_NTZ
  GROUP BY 1
)
SELECT l.address, l.primary_label, l.primary_entity, l.primary_category, TO_JSON(l.subcategory) AS subcategory_json,
       l.confidence, l.attribution_date, l.source_type, l.source_system, l.source_priority, l.entity_ranking,
       a.first_atomic_at
FROM atomic a JOIN AVALANCHE.IDENTITY.LABELS l ON l.address = a.address AND l.chain = 'avalanche'
ORDER BY l.address
