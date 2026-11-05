-- Dataset: allium.prices-hourly
-- Every hourly USD price that Allium's price service holds for native AVAX (the zero address), WAVAX, and the
-- liquid staking tokens sAVAX, ggAVAX (listed under the symbol stAVAX) and yyAVAX, one row per token and hour.
-- PRICE is stored as text in the source and is captured as that text; the build reads it as a number.
-- The window is half-open on the hour timestamp. Nothing is filtered, deduplicated or filled here.
SELECT chain, id, symbol, address, decimals, timestamp AS hour_utc, price AS price_text, _created_at AS created_at
FROM AVALANCHE.PRICES.HOURLY
WHERE address IN (
    '0x0000000000000000000000000000000000000000',
    '0xb31f66aa3c1e785363f0875a1b74e27b85fd66c7',
    '0x2b2c81e08f1af8835a78bb2a90ae924ace0ea4be',
    '0xa25eaf2906fa1a3a13edac9b9657108af7b703e3',
    '0xf7d9281e8e363584973f946201b82ba72c965d27'
  )
  AND timestamp >= %(start)s::TIMESTAMP_NTZ AND timestamp < %(end)s::TIMESTAMP_NTZ
ORDER BY address, timestamp
