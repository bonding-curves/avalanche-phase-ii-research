-- Dataset: af.address-mapping-atomic
-- The Foundation's entity mapping of each C-Chain address that sent an export to the P-Chain or received an import from
-- it in the window, one row per mapped address, with the time of its first such transaction. The window is half-open on
-- the block timestamp of the atomic transactions. An address without a mapping has no row.
WITH atomic AS (
  SELECT CASE WHEN source_chain = 'c-chain' THEN from_address ELSE to_address END AS address,
         MIN(block_timestamp) AS first_atomic_at
  FROM AVALANCHE.RAW.SUBNET_TRANSACTIONS
  WHERE 'p-chain' IN (source_chain, destination_chain)
    AND block_timestamp >= %(start)s::TIMESTAMP_NTZ AND block_timestamp < %(end)s::TIMESTAMP_NTZ
  GROUP BY 1
)
SELECT m.address, m.entity, m.sub_entity, m.category, m.sector, m.source, m.priority, a.first_atomic_at
FROM atomic a JOIN AF.GROSS_CHAIN_PRODUCT.ADDRESS_MAPPING m ON m.address = a.address
ORDER BY m.address
