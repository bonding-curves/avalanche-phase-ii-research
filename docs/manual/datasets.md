# Dataset dispatch reference

*Draft for review.*

The CLI dispatches 69 dataset identifiers to the implementations below. These identifiers describe supported contracts, not local data availability. Use `avalanche data describe ID` for its catalog description and `avalanche data runs ID` for installed runs. Provider-specific parameters belong to the corresponding source module.

| Dataset identifier | Implementation |
| --- | --- |
| `binance.avax-usdt-daily` | `avalanche_research.sources.binance` |
| `builder-hub.validator-uptime` | `avalanche_research.sources.builderhub` |
| `c-chain-rpc.atomic-transactions` | `avalanche_research.sources.catx` |
| `c-chain-rpc.block-receipt-fees` | `avalanche_research.sources.cblocks` |
| `c-chain-rpc.receipt-gap-repairs` | `avalanche_research.sources.cchain_rpc` |
| `c-chain-rpc.token-supply-monthly` | `avalanche_research.sources.gci` |
| `coingecko.avax-market-daily` | `avalanche_research.sources.coingecko` |
| `data-api.avax-supply` | `avalanche_research.sources.dataapi` |
| `data-api.c-chain-atomic-burn` | `avalanche_research.sources.atomic` |
| `data-api.c-chain-block-fees` | `avalanche_research.sources.cblocks` |
| `data-api.c-chain-block-list` | `avalanche_research.sources.clist` |
| `data-api.p-chain-block-list` | `avalanche_research.sources.clist` |
| `data-api.p-chain-staking-transactions` | `avalanche_research.sources.pstakers` |
| `data-api.validators-active` | `avalanche_research.sources.validators_api` |
| `data-api.validators-completed` | `avalanche_research.sources.validators_api` |
| `data-api.validators-completed-recent` | `avalanche_research.sources.validators_api` |
| `defillama.avalanche-fees-daily` | `avalanche_research.sources.gci` |
| `defillama.avax-price-daily` | `avalanche_research.sources.defillama` |
| `defillama.lend-borrow` | `avalanche_research.sources.pool_history` |
| `defillama.pool-history` | `avalanche_research.sources.pool_history` |
| `defillama.pool-yields` | `avalanche_research.sources.yields` |
| `derived.avax-monetary-daily` | `avalanche_research.datasets.derived.monetary` |
| `derived.c-chain-evm-burn-daily` | `avalanche_research.datasets.derived.clist_daily` |
| `derived.gci-monthly` | `avalanche_research.datasets.derived.gci_monthly` |
| `derived.helicon-commitments` | `avalanche_research.datasets.derived.helicon` |
| `derived.market-weeks` | `avalanche_research.datasets.derived.weeks` |
| `derived.monetary-periods` | `avalanche_research.datasets.derived.monetary_periods` |
| `derived.node-table` | `avalanche_research.datasets.derived.nodes` |
| `derived.observed-delegations` | `avalanche_research.datasets.derived.weeks` |
| `derived.operator-attributions` | `avalanche_research.datasets.derived.attributions` |
| `derived.operators` | `avalanche_research.datasets.derived.operators` |
| `derived.opportunity-costs-daily` | `avalanche_research.datasets.derived.opportunity` |
| `derived.p-chain-delegator-stakes` | `avalanche_research.datasets.derived.pstaking` |
| `derived.p-chain-staking-cycles` | `avalanche_research.datasets.derived.pstaking` |
| `derived.p-chain-staking-rewards` | `avalanche_research.datasets.derived.pstaking` |
| `derived.p-chain-staking-supply` | `avalanche_research.datasets.derived.pstaking` |
| `derived.p-chain-validator-stakes` | `avalanche_research.datasets.derived.pstaking` |
| `derived.primary-burn-daily` | `avalanche_research.datasets.derived.pburns` |
| `derived.seamed-burn-daily` | `avalanche_research.datasets.derived.seam` |
| `derived.seamed-c-chain-evm-burn-daily` | `avalanche_research.datasets.derived.seam` |
| `derived.seamed-delegator-stakes` | `avalanche_research.datasets.derived.seam` |
| `derived.seamed-staking-rewards` | `avalanche_research.datasets.derived.seam` |
| `derived.seamed-staking-supply` | `avalanche_research.datasets.derived.seam` |
| `derived.seamed-validator-stakes` | `avalanche_research.datasets.derived.seam` |
| `derived.staking-periods` | `avalanche_research.datasets.derived.staking_periods` |
| `derived.subnet-validation` | `avalanche_research.datasets.derived.subnets` |
| `derived.validator-uptime-hourly` | `avalanche_research.datasets.derived.uptime_hourly` |
| `derived.validator-weeks` | `avalanche_research.datasets.derived.weeks` |
| `etf-issuers.avax-fund-history` | `avalanche_research.sources.etf` |
| `etf-issuers.avax-fund-snapshot` | `avalanche_research.sources.etf` |
| `fred.tbill-3m-daily` | `avalanche_research.sources.gci` |
| `metrics-api.c-chain-activity-daily` | `avalanche_research.sources.metrics` |
| `metrics-api.primary-staking-daily` | `avalanche_research.sources.metrics` |
| `p-chain-rpc.blocks` | `avalanche_research.sources.pblocks` |
| `p-chain-rpc.current-validators` | `avalanche_research.sources.pchain` |
| `p-chain-rpc.reward-utxos` | `avalanche_research.sources.pstakers` |
| `p-chain-rpc.transactions` | `avalanche_research.sources.ptx` |
| `snowflake.c-chain-block-gaps` | `avalanche_research.sources.snowflake` |
| `snowflake.c-chain-evm-burn-daily` | `avalanche_research.sources.snowflake` |
| `snowflake.primary-burn-daily` | `avalanche_research.sources.snowflake` |
| `snowflake.primary-burn-events` | `avalanche_research.sources.snowflake` |
| `snowflake.primary-delegator-stakes` | `avalanche_research.sources.snowflake` |
| `snowflake.primary-staking-rewards` | `avalanche_research.sources.snowflake` |
| `snowflake.primary-staking-supply` | `avalanche_research.sources.snowflake` |
| `snowflake.primary-validator-stakes` | `avalanche_research.sources.snowflake` |
| `snowflake.subnet-validator-transactions` | `avalanche_research.sources.snowflake` |
| `snowpeer.network-summary` | `avalanche_research.sources.snowpeer` |
| `us-treasury.par-yield-daily` | `avalanche_research.sources.treasury` |
| `x-chain-rpc.blocks` | `avalanche_research.sources.pblocks` |
