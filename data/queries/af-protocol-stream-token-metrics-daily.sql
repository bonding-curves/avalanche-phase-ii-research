-- Dataset: af.protocol-stream-token-metrics-daily
-- The Foundation's daily revenue and cost streams for BENQI's liquid staking token sAVAX, and the issuer yield of the
-- stablecoin issuers and the holder yield of the tokenised bill funds, one row per protocol, day, stream, token and
-- chain, each amount in tokens, USD and AVAX. The window is half-open on the date. Nothing is filtered or filled here.
SELECT protocol_id, date AS date_utc, stream_id, stream_type, denomination_token_address, denomination_token_symbol,
       amount_token::FLOAT AS amount_token, amount_usd::FLOAT AS amount_usd, amount_avax::FLOAT AS amount_avax,
       amount_usd_ref::FLOAT AS amount_usd_ref, amount_avax_ref::FLOAT AS amount_avax_ref, chain_id
FROM AF.GROSS_CHAIN_PRODUCT.PROTOCOL_STREAM_TOKEN_METRICS_DAILY
WHERE (protocol_id = 'benqi-staked-avax' OR stream_type IN ('issuer_yield', 'holder_yield'))
  AND date >= %(start)s::DATE AND date < %(end)s::DATE
ORDER BY protocol_id, date, stream_id, denomination_token_address, chain_id
