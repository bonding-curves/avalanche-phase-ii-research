-- Dataset: allium.lending-interest-rates
-- Every lending rate update Allium records on Avalanche for WAVAX, native AVAX, sAVAX, USDC and USDt, one row per
-- update, matched on the upper-cased token symbol: each market's supply and borrow rates in percent a year, the
-- amount supplied in tokens and in USD, and the amount lent out. The bridged USDC.e and USDT.e are not matched.
-- The window is half-open on the block timestamp. Nothing is filtered, deduplicated or filled here.
SELECT project, protocol, market_address, token_address, token_symbol, block_timestamp, block_number, unique_id,
       supply_apy, variable_borrow_apy, stable_borrow_apy, supplied_amount, supplied_amount_usd, outstanding_loans,
       usd_exchange_rate
FROM AVALANCHE.LENDING.INTEREST_RATES
WHERE UPPER(token_symbol) IN ('WAVAX', 'AVAX', 'SAVAX', 'USDC', 'USDT')
  AND block_timestamp >= %(start)s::TIMESTAMP_NTZ AND block_timestamp < %(end)s::TIMESTAMP_NTZ
ORDER BY block_timestamp, unique_id
