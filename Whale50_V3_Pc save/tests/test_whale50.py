# -*- coding: utf-8 -*-
import unittest,sys,io, tempfile,sqlite3,json
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import whale50 as w
XML=b'''<?xml version="1.0" encoding="UTF-8"?>
<informationTable xmlns="http://www.sec.gov/edgar/document/thirteenf/informationtable">
<infoTable><nameOfIssuer>APPLE INC</nameOfIssuer><titleOfClass>COM</titleOfClass><cusip>037833100</cusip>
<value>30000</value><shrsOrPrnAmt><sshPrnamt>100</sshPrnamt><sshPrnamtType>SH</sshPrnamtType></shrsOrPrnAmt></infoTable>
<infoTable><nameOfIssuer>APPLE INC</nameOfIssuer><titleOfClass>COM</titleOfClass><cusip>037833100</cusip>
<value>6000</value><shrsOrPrnAmt><sshPrnamt>20</sshPrnamt><sshPrnamtType>SH</sshPrnamtType></shrsOrPrnAmt></infoTable>
<infoTable><nameOfIssuer>MICROSOFT</nameOfIssuer><titleOfClass>CALL</titleOfClass><cusip>594918104</cusip>
<value>200000</value><shrsOrPrnAmt><sshPrnamt>200</sshPrnamt><sshPrnamtType>SH</sshPrnamtType></shrsOrPrnAmt><putCall>CALL</putCall></infoTable>
</informationTable>'''

class Logic(unittest.TestCase):
 def test_price_history(self):
  src={'chart':{'result':[{'timestamp':[1770000000,1770086400], 'indicators':{'quote':[{'close':[100,110]}],'adjclose':[{'adjclose':[101,111]}]}}]}}
  bars=w.parse_yahoo_chart(json.dumps(src).encode())
  self.assertEqual([v[1] for v in bars],[101.,111.])
 def test_parsing_aggregate_and_option(self):
  h=w.parse_infotable(XML)
  self.assertEqual(len(h),2)
  self.assertEqual(h[0]['shares'],120)
  self.assertEqual(h[0]['value'],36000)
  self.assertEqual(h[1]['option'],'CALL')
 def test_latest_reports(self):
  j={'filings':{'recent':{'form':['13F-HR/A','13F-HR','13F-HR','13F-HR'],
      'reportDate':['2026-06-30','2026-06-30','2026-03-31','2025-12-31'],
      'filingDate':['2026-09-01','2026-08-14','2026-05-15','2026-02-15'],
      'accessionNumber':['a','b','c','d']}}}
  self.assertEqual([x['accession'] for x in w.listed_reports(j)],['b','c','d'])
 def test_buy_ranking_and_undisclosed(self):
  fund=w.MANAGERS[0]
  prev={'period':'2026-03-31','filed':'2026-05-15','url':'prev','holdings':[
      {'issuer':'APPLE INC','cusip':'037833100','shares':80,'value':16000,'option':''}]}
  current={'period':'2026-06-30','filed':'2026-08-14','url':'current','holdings':w.parse_infotable(XML)}
  ranks,details,managers=w._rankings({fund['cik']:{'2026-03-31':prev,'2026-06-30':current}},'2026-06-30')
  apple=next(x for x in ranks if x['ticker']=='AAPL')
  self.assertEqual(apple['buy_usd'],12000)
  self.assertEqual(apple['buyers'],1)
  self.assertEqual(len(details),1) # excludes options
  self.assertEqual(details[0]['delta_shares'],40)
  self.assertEqual(sum(x['buy_usd'] for x in managers),12000)
  self.assertEqual(len(managers),50)
 def test_new_buy(self):
  fund=w.MANAGERS[0]
  curr={'period':'2026-06-30','filed':'2026-08-14','url':'current','holdings':w.parse_infotable(XML)[:1]}
  prev={'period':'2026-03-31','filed':'2026-05-15','url':'prev','holdings':[{'issuer':'MSFT','cusip':'594918104','shares':10,'value':4000,'option':''}]}
  ranks,details,_=w._rankings({fund['cik']:{'2026-06-30':curr,'2026-03-31':prev}},'latest')
  self.assertEqual(details[0]['action'],'신규')
  self.assertEqual(details[1]['action'],'전량매도')
  self.assertEqual(ranks[0]['new_buyers'],1)

if __name__=='__main__': unittest.main()
