-- Dataset: allium.dex-token-prices-hourly
-- Every hourly WAVAX price that Allium derives from trades on Avalanche decentralised exchanges, one row per hour,
-- with its median price, its MEDIAN_SAFE_PRICE, and the hour's USD volume, traders and trades.
-- The window is half-open on the hour timestamp. Nothing is filtered, deduplicated or filled here.
SELECT chain, address, symbol, timestamp AS hour_utc, price, median_price, median_safe_price,
       usd_trading_volume, traders, trade_count
FROM AVALANCHE.DEX.TOKEN_PRICES_HOURLY
WHERE address = '0xb31f66aa3c1e785363f0875a1b74e27b85fd66c7'
  AND timestamp >= %(start)s::TIMESTAMP_NTZ AND timestamp < %(end)s::TIMESTAMP_NTZ
ORDER BY timestamp
