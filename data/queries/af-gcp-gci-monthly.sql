-- Dataset: af.gcp-gci-monthly
-- The Foundation's Gross Chain Product and Gross Chain Income by month for the economy and for the network, one row per
-- layer and month: nominal product with its three parts, the real level, holder and issuer yields, and nominal income,
-- each in USD and AVAX. Product and income join on the month. The window is half-open on the month's first date.
-- Nothing is filtered or filled here.
WITH economy AS (
  SELECT 'economy' AS layer, g.period_start_date, g.period_interval, g.ngcp_usd::FLOAT AS ngcp_usd, g.ngcp_avax::FLOAT AS ngcp_avax,
         g.l_usd::FLOAT AS l_usd, g.p_usd::FLOAT AS p_usd, g.g_usd::FLOAT AS g_usd, g.l_avax::FLOAT AS l_avax,
         g.p_avax::FLOAT AS p_avax, g.g_avax::FLOAT AS g_avax, g.rgcp_level_usd, g.rgcp_level_avax,
         i.holder_yield_usd::FLOAT AS holder_yield_usd, i.issuer_yield_usd::FLOAT AS issuer_yield_usd,
         i.issuer_yield_offchain_usd::FLOAT AS issuer_yield_offchain_usd, i.ngci_usd::FLOAT AS ngci_usd,
         i.ngci_general_usd::FLOAT AS ngci_general_usd, i.holder_yield_avax::FLOAT AS holder_yield_avax,
         i.issuer_yield_avax::FLOAT AS issuer_yield_avax, i.issuer_yield_offchain_avax::FLOAT AS issuer_yield_offchain_avax,
         i.ngci_avax::FLOAT AS ngci_avax, i.ngci_general_avax::FLOAT AS ngci_general_avax
  FROM AF.GROSS_CHAIN_PRODUCT.ECONOMY_GCP_MONTHLY g
  LEFT JOIN AF.GROSS_CHAIN_PRODUCT.ECONOMY_GCI_MONTHLY i USING (period_start_date, period_interval)
), network AS (
  SELECT 'network' AS layer, g.period_start_date, g.period_interval, g.ngcp_usd::FLOAT, g.ngcp_avax::FLOAT,
         g.l_usd::FLOAT, g.p_usd::FLOAT, g.g_usd::FLOAT, g.l_avax::FLOAT, g.p_avax::FLOAT, g.g_avax::FLOAT,
         g.rgcp_level_usd, g.rgcp_level_avax, i.holder_yield_usd::FLOAT, i.issuer_yield_usd::FLOAT,
         i.issuer_yield_offchain_usd::FLOAT, i.ngci_usd::FLOAT, i.ngci_general_usd::FLOAT, i.holder_yield_avax::FLOAT,
         i.issuer_yield_avax::FLOAT, i.issuer_yield_offchain_avax::FLOAT, i.ngci_avax::FLOAT, i.ngci_general_avax::FLOAT
  FROM AF.GROSS_CHAIN_PRODUCT.NETWORK_GCP_MONTHLY g
  LEFT JOIN AF.GROSS_CHAIN_PRODUCT.NETWORK_GCI_MONTHLY i USING (period_start_date, period_interval)
)
SELECT * FROM (SELECT * FROM economy UNION ALL SELECT * FROM network)
WHERE period_start_date >= %(start)s::DATE AND period_start_date < %(end)s::DATE
ORDER BY layer, period_start_date
