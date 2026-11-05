-- Dataset: allium.p-chain-atomic-transactions
-- Every atomic transaction between the C-Chain and the P-Chain that Allium records, one row per transaction: an export
-- from the C-Chain names its C-Chain sender in FROM_ADDRESS and its P-Chain outputs, each with its owner addresses, in
-- OUTPUT; an import to the C-Chain names its P-Chain sender in FROM_ADDRESS and its C-Chain recipient in TO_ADDRESS.
-- The amount is in AVAX and its nAVAX integer as Allium records it. The window is half-open on the block timestamp.
-- Nothing is filtered, deduplicated or filled here.
SELECT hash, source_chain, destination_chain, from_address, to_address, raw_amount AS amount_navax_text, amount AS amount_avax,
       fees AS fees_avax, CASE WHEN output = 'NaN' THEN NULL ELSE output END AS output_json, block_timestamp, block_number
FROM AVALANCHE.RAW.SUBNET_TRANSACTIONS
WHERE 'p-chain' IN (source_chain, destination_chain)
  AND block_timestamp >= %(start)s::TIMESTAMP_NTZ AND block_timestamp < %(end)s::TIMESTAMP_NTZ
ORDER BY block_timestamp, hash
