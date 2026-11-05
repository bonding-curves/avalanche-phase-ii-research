-- Dataset: af.benchmark-rates-daily
-- Every row of the Foundation's daily benchmark rates: the rate identifier, the annual rate as a decimal, and the
-- source label, which marks the days carried forward or filled back from a published value. The window is half-open
-- on the date.
SELECT date AS date_utc, rate_id, rate_annual, source
FROM AF.GROSS_CHAIN_PRODUCT.BENCHMARK_RATES_DAILY
WHERE date >= %(start)s::DATE AND date < %(end)s::DATE
ORDER BY date, rate_id
