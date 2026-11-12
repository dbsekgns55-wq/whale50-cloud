# -*- coding: utf-8 -*-
"""GitHub Actions scheduled, static read-only Whale50 publisher.

This DOES NOT run anywhere until the user publishes it to GitHub and enables
Actions + Pages. Reads public SEC filings and Binance equity perpetual 24/7 market bars.
"""
from __future__ import annotations
from datetime import datetime, timedelta, timezone
from pathlib import Path
import json
import os
import shutil
import time
import whale50
import whale50_signals as sig
import whale50_binance as market
import whale50_validation as valid

ROOT=Path(__file__).resolve().parent
SITE=ROOT/'site'


def has_fresh_sec(con, hours=22):
    last=con.execute('SELECT MAX(checked) FROM checks').fetchone()[0]
    if not last:return False
    try:
        age=datetime.now(timezone.utc)-datetime.fromisoformat(last).astimezone(timezone.utc)
        return age.total_seconds()<hours*3600
    except ValueError:return False


def update_market(con):
    targets,_=whale50.signal_targets()
    utcnow=datetime.now(timezone.utc)
    # Binance equity perpetual data: 15m closed bars checked each invocation;
    # higher frames are refreshed hourly/day. First run always initializes.
    source_intervals={'15m':900,'30m':1800,'1h':3600,'4h':14400,'1d':86400,'1wk':86400,'1mo':86400}
    try:active_pairs=market.active_equity_pairs()
    except Exception as e:
        print('BINANCE exchangeInfo unavailable; preserving cached signals:',e,flush=True)
        return
    for r in targets:
        ticker=r['ticker']
        if ticker not in active_pairs:
            print('UNAVAILABLE EQUITY PERP',ticker,flush=True)
            continue
        key=whale50.market_cache_key(ticker)
        cache=whale50._read_signal_cache(con,key)
        for frame,(interval,period) in sig.SOURCE.items():
            existing=cache.get(frame)
            if existing and existing['checked']:
                try:
                    age=(utcnow-datetime.fromisoformat(existing['checked']).astimezone(timezone.utc)).total_seconds()
                    if age<source_intervals[frame]:continue
                except ValueError:pass
            print('BINANCE EQUITY PERP',ticker,active_pairs[ticker],frame,flush=True)
            try:
                bars=sig.fetch_ohlcv(ticker,interval,period)
                previous=existing['bars'] if existing else []
                merged=sig.merge_bars(previous,bars)
                con.execute('''INSERT OR REPLACE INTO signal_bars(ticker,interval,bars,checked,error)
                           VALUES(?,?,?,?,?)''',(key,frame,json.dumps(merged),utcnow.isoformat(),''))
                cache[frame]={'bars':merged,'checked':utcnow.isoformat(),'error':''}
            except Exception as ex:
                err=str(ex)[:250]
                print('PRICE ERROR',ticker,frame,err,flush=True)
                if existing:
                    con.execute('''UPDATE signal_bars SET error=? WHERE ticker=? AND interval=?''',(err,key,frame))
                else:
                    con.execute('''INSERT OR IGNORE INTO signal_bars(ticker,interval,bars,checked,error)
                               VALUES(?,?,?,?,?)''',(key,frame,'[]',utcnow.isoformat(),err))
            con.commit()
            time.sleep(.07)
        for frame,bars in valid.frame_bars({k:v['bars'] for k,v in cache.items()}).items():
            valid.record_forward(con,key,frame,bars)


def export_site():
    SITE.mkdir(exist_ok=True)
    payload=whale50.get_payload()
    payload['config']={'configured':True}
    signals=whale50.signal_view()
    performance=whale50.performance_view()
    for name,value in [('data.json',payload),('signals.json',signals),('performance.json',performance)]:
        (SITE/name).write_text(json.dumps(value,ensure_ascii=False,separators=(',',':')),encoding='utf-8')
    page=(ROOT/'dashboard.html').read_text(encoding='utf-8')
    page=page.replace('<script>\n\'use strict\';',"<script>window.WHALE50_CLOUD=true;</script>\n<script>\n'use strict';")
    (SITE/'index.html').write_text(page,encoding='utf-8')
    (SITE/'.nojekyll').write_text('',encoding='utf-8')
    # CHECKPOINT: git commits a single database file, not a dangling WAL.
    con=whale50.db_open()
    con.execute('PRAGMA wal_checkpoint(TRUNCATE)')
    con.close()
    print('SITE EXPORTED',len(signals['rows']),'stocks; historical',len(performance['rows']),'rows')


def main():
    os.environ['WHALE50_CLOUD']='1'
    con=whale50.db_open()
    due=not has_fresh_sec(con)
    con.close()
    email=whale50.load_config().get('email','')
    if due and email:
        print('SEC: Checking public filings ...')
        whale50.run_update()
    elif due:
        print('SEC: No contact secret configured. Configure WHALE50_SEC_EMAIL in GitHub Actions secrets.')
    con=whale50.db_open()
    try:update_market(con)
    finally:con.close()
    export_site()


if __name__=='__main__':main()
