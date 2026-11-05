-- Dataset: af.economy-gas-fees-daily
-- Every row of the Foundation's daily C-Chain gas fees counted by its Gross Chain Product economy, in AVAX and USD,
-- with the columns valued at the pipeline's fixed reference price. The window is half-open on the date.
SELECT date AS date_utc, gas_used_avax, gas_used_usd, gas_used_usd_ref, gas_used_avax_ref
FROM AF.GROSS_CHAIN_PRODUCT.ECONOMY_GAS_FEES_DAILY
WHERE date >= %(start)s::DATE AND date < %(end)s::DATE
ORDER BY date
