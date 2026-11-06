-- Dataset: allium.metrics-overview-daily
-- Allium's daily C-Chain overview: blocks, transactions, the fees paid in AVAX and USD, active and new addresses, and
-- the median AVAX price. Every C-Chain fee is burned. The window is half-open on the activity date. Nothing is filtered
-- or filled here.
SELECT chain, activity_date::DATE AS date_utc, total_blocks, total_transactions, success_transactions, failed_transactions,
       transaction_fees, transaction_fees_usd, active_addresses, new_addresses, native_token_price_median_usd
FROM AVALANCHE.METRICS.OVERVIEW
WHERE activity_date >= %(start)s::TIMESTAMP_NTZ AND activity_date < %(end)s::TIMESTAMP_NTZ
ORDER BY chain, activity_date
