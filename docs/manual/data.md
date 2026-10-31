# 5. Data identity and accounting preserve meaning

*Draft for review.*

A dataset is useful for research when its observations, coverage and construction are understood. A file hash identifies bytes, but it does not establish that a source is fresh or that a derived quantity means what its name suggests.

The [data guide](https://github.com/AVL-Foundation/ext-bcrg-validator-research/blob/milestone-2/data/README.md) and [dataset reference](datasets.md) identify the supported sources and contracts. The model's initial state is built from the selected staking and monetary inputs, while other datasets support descriptive research or development extensions.

## Captures and derived tables answer different questions

A source adapter records external responses and request metadata. A builder turns a capture into normalized columns and records schema and output identities. A derived dataset joins or reconstructs quantities from existing inputs. For example, a staking-period table combines transaction and reward information into commitments that can be followed over time.

A checked derived table can support several consumers, but its population remains explicit. Validator periods, delegated periods, automatic-renewal cycles, nodes and operators are different units. Acceptance time and start time also differ. The period accepted before an origin may be known even when its start lies after that origin.

## Pins fix inputs rather than retrieving them

A pin names exact runs, file sizes and hashes, with recorded checks and optional source-code identity. It prevents an experiment from silently selecting a newer input. The pin checker authenticates local bytes and stored check status. It does not rerun every original dataset check or download missing data.

The central report replay distributes a compact authenticated bundle. Other historical inputs are separate. Generic model-run examples require the datasets named by their pin to be installed. The CLI walkthrough states these requirements before each operation.

## Stocks, flows and time-weighted amounts stay distinct

**Active stake** is AVAX in open commitments at an instant. **Gross committed AVAX** sums amounts across starts in a window. The same capital can appear repeatedly in that flow. **Scheduled AVAX-days** multiply an amount by its full scheduled duration, including days after the observation window.

A 2,000 AVAX commitment lasting 14 days contains 28,000 scheduled AVAX-days. If the same AVAX starts another commitment later, summing both commitments does not create 4,000 distinct AVAX. These definitions explain why an increase in commitments need not imply the same increase in active stake.

The model stores stake and rewards in integer nAVAX, with one AVAX equal to one billion nAVAX. C-Chain observations may use wei, a different denomination. Conversion must follow the source contract. Large integer monetary quantities should not be routed through a floating-point column merely for convenience.

## A supply counter is not a wallet-balance total

The protocol reward calculation uses the P-Chain supply counter. That accounting counter includes reward reservations according to protocol semantics. Realized supply concerns AVAX actually issued and burned. Circulating supply adds assumptions about availability. These bases cannot be substituted without changing a rate or ratio.

The central model records validator reward promises, rather than every reward payment during the horizon. Its plotted supply construction includes validator issuance and fixed burn while omitting delegated issuance. Its inflation proxy is consequently narrower than network-wide AVAX inflation. The [monetary source audit](https://github.com/AVL-Foundation/ext-bcrg-validator-research/blob/milestone-2/data/monetary-source-audit.md) explains the distinctions used by the data layer.

## Checks establish particular properties

Schema checks establish column and type requirements. Hash checks establish identity. Reconciliation checks establish agreement between selected quantities or sources. Reward reconstruction checks the protocol calculation. Coverage and freshness checks establish which observations have arrived.

Agreement between two sources is useful evidence when they measure the same population and quantity. A successful query or valid key does not prove the source has continued loading. Retain the source's coverage date beside results, and keep unavailable or mismatched observations explicit.

Before fitting, identify the origin cutoff, observation windows and incomplete follow-up. Before reporting, identify the population, supply basis, unit and comparator. Those choices are part of the research method.

[Manual contents](README.md)
