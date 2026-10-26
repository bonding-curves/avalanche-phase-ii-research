"""Independent tiny events for the monetary auto-renew bridge, with no provider data."""
import json
from datetime import UTC, datetime

import duckdb
import pytest

from avalanche_research.core.catalog import DataError
from avalanche_research.datasets.derived import cycle_accounting as ca
from avalanche_research.datasets.derived.pstaking import CYCLE_COLUMNS


def fixture(terminal=True, passed=True):
    c = duckdb.connect()
    c.execute("CREATE TABLE staking_periods(transaction_hash VARCHAR,node_id VARCHAR,role VARCHAR,tx_type VARCHAR,"
              "start_time TIMESTAMP,end_time TIMESTAMP,stake_navax BIGINT,cycles INTEGER,last_cycle_end_time TIMESTAMP)")
    # 2,000 AVAX with small nAVAX reward integers makes exact accounting hand-auditable.
    weight = 2000 * 10**9
    c.execute("INSERT INTO staking_periods VALUES ('a','node','validator','AddAutoRenewedValidatorTx',"
              "'2026-09-22','2026-09-24',?,2,'2026-09-26')", [weight])
    c.execute("CREATE TABLE staking_rewards(staking_transaction_hash VARCHAR,rewarded_at TIMESTAMP,realized_reward_navax BIGINT)")
    # Ordinary delegator net reward remains; the terminal auto cash row must not also become new issuance.
    c.execute("INSERT INTO staking_rewards VALUES ('delegator','2026-09-24',8),('a','2026-09-26',999)")
    c.execute("CREATE TABLE staking_cycles(" + ','.join(f'{k} {v}' for k, v in CYCLE_COLUMNS.items()) + ')')
    first = ('a','node',1,datetime(2026,9,22),datetime(2026,9,24),weight,10,500000,172800,
             'r1',True,2,5,1,5,1)
    second = ('a','node',2,datetime(2026,9,24),datetime(2026,9,26),weight+6,20,500000,0,
              'r2',passed,4,0,0,20 if passed else 0,4) if terminal else (
             'a','node',2,datetime(2026,9,24),datetime(2026,9,26),weight+6,20,500000,None,None,None,None,None,None,None,None)
    c.executemany('INSERT INTO staking_cycles VALUES ('+','.join('?'for _ in CYCLE_COLUMNS)+')',[first,second])
    c.execute("CREATE TABLE cycle_blocks(block_height BIGINT,block_id VARCHAR,parent_id VARCHAR,block_time TIMESTAMP,"
              "block_type VARCHAR,transaction_hash VARCHAR,tx_type VARCHAR,unsigned_tx VARCHAR)")
    c.execute("INSERT INTO cycle_blocks(block_height,block_id,parent_id,block_time,block_type,transaction_hash,tx_type) VALUES (10,'p1','prev','2026-09-24','proposal','r1','RewardAutoRenewedValidatorTx'),"
              "(11,'o1','p1','2026-09-24','commit',NULL,NULL)")
    c.execute("UPDATE cycle_blocks SET unsigned_tx=? WHERE transaction_hash='r1'", [json.dumps({"txID":"a","timestamp":int(datetime(2026,9,24,tzinfo=UTC).timestamp())})])
    if terminal:
        c.execute("INSERT INTO cycle_blocks(block_height,block_id,parent_id,block_time,block_type,transaction_hash,tx_type) VALUES (20,'p2','prev2','2026-09-26','proposal','r2','RewardAutoRenewedValidatorTx'),"
                  "(21,'o2','p2','2026-09-26',?,NULL,NULL)", ['commit' if passed else 'abort'])
        c.execute("UPDATE cycle_blocks SET unsigned_tx=? WHERE transaction_hash='r2'", [json.dumps({"txID":"a","timestamp":int(datetime(2026,9,26,tzinfo=UTC).timestamp())})])
    return c


def test_current_recognition_excludes_prior_release_and_auto_cash():
    c=fixture();s=ca.prepare(c,'2026-09-26')
    assert s['cycle_recognised_navax']==36  # 10+2, then 20+4.
    assert s['prior_accrual_released_navax']==6
    assert c.execute('SELECT sum(recognised_reward_navax) FROM monetary_reward_events').fetchone()[0]==44  # ordinary net8 + cycles36.
    assert c.execute('SELECT liquid_total_navax FROM cycle_events WHERE cycle=2').fetchone()[0]==30  # current24 + prior6.
    assert c.execute("SELECT stake_navax FROM effective_stake_intervals WHERE start_time='2026-09-24'").fetchone()[0]==2000*10**9+6
    # Exactly at the cycle boundary the old weight leaves and the new weight enters.
    assert c.execute("SELECT sum(stake_navax) FROM effective_stake_intervals WHERE start_time<='2026-09-24' AND end_time>'2026-09-24'").fetchone()[0]==2000*10**9+6


def test_abort_forfeits_only_current_self_reward_but_pays_commission_and_prior_accrual():
    c=fixture(passed=False);s=ca.prepare(c,'2026-09-26')
    assert s['cycle_recognised_navax']==16
    assert c.execute('SELECT liquid_total_navax,current_validation_navax,current_delegatee_navax FROM cycle_events WHERE cycle=2').fetchone()==(10,0,4)


@pytest.mark.parametrize('mutation',[
 "DELETE FROM cycle_blocks WHERE block_id='o2'",
 "UPDATE cycle_blocks SET block_type='abort' WHERE block_id='o2'",
 "UPDATE cycle_blocks SET parent_id='wrong' WHERE block_id='o2'",
 "UPDATE cycle_blocks SET block_time=block_time+INTERVAL '1 second' WHERE block_id='p2'",
 "UPDATE staking_cycles SET weight_navax=weight_navax+1 WHERE cycle=2",
 "DELETE FROM staking_cycles WHERE cycle=1",
 "UPDATE staking_cycles SET withdrawn_validation_navax=999 WHERE cycle=2",
 "UPDATE cycle_blocks SET unsigned_tx='{}' WHERE transaction_hash='r1'",
 "UPDATE cycle_blocks SET block_type='standard' WHERE block_id='p1'",
 "UPDATE cycle_blocks SET block_id=NULL WHERE block_id='o1'",
 "UPDATE cycle_blocks SET block_height=NULL WHERE block_id='p1'",
 "UPDATE staking_cycles SET next_period_seconds=86400 WHERE cycle=1",
 "UPDATE staking_periods SET stake_navax=-100; UPDATE staking_cycles SET weight_navax=CASE WHEN cycle=1 THEN -100 ELSE -94 END",
 "UPDATE staking_periods SET stake_navax=0; UPDATE staking_cycles SET weight_navax=CASE WHEN cycle=1 THEN 0 ELSE 6 END",
])
def test_unsupported_or_inconsistent_cycles_refuse(mutation):
    c=fixture();c.execute(mutation)
    with pytest.raises(DataError):ca.prepare(c,'2026-09-26')


def test_open_cycle_is_not_a_terminal_exit_or_a_zero_reward():
    c=fixture(terminal=False);s=ca.prepare(c,'2026-09-25')
    assert s['closed_events']==1
    assert c.execute("SELECT sum(stake_navax) FROM effective_stake_intervals WHERE start_time<='2026-09-25' AND end_time>'2026-09-25'").fetchone()[0]==2000*10**9+6
    with pytest.raises(DataError,match='unresolved cycle'):ca.prepare(c,'2026-09-26')


def test_auto_parent_without_cycles_refuses_instead_of_using_original_stake():
    c=fixture();c.execute('DROP TABLE staking_cycles')
    with pytest.raises(DataError,match='complete cycle histories'):ca.prepare(c,'2026-09-26')
