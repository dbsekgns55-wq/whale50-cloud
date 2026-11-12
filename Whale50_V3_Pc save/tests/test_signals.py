import unittest,sys,math
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import whale50_signals as s

def fundrow(cusip,ticker,estimate,cik,action='추가'):
    f={'cik':cik,'fund':cik,'short':cik,'action':action,'estimated_change_usd':estimate,'delta_shares':50,
       'period':'2026-06-30','previous_period':'2026-03-31','filed':'2026-08-14','source':'https://www.sec.gov',}
    return {'cusip':cusip,'ticker':ticker,'name':'ALPHABET INC','buy_usd':estimate,'sell_usd':0,
            'hold_usd':estimate*2,'buyers':1,'holders':1,'new_buyers':int(action=='신규'),
            'periods':['2026-06-30'],'buying_funds':[f],'positions':[{'cik':cik,'value_usd':estimate*2,'period':'2026-06-30'}]}

def candles(direction=1,n=120):
    result=[]
    for i in range(n):
        price=100+direction*i*.25+.3*math.sin(i)
        result.append({'t':1700000000+i*300,'o':price-.1,'h':price+.8,'l':price-.8,'c':price,'v':100+i})
    return result

class SignalTests(unittest.TestCase):
    def test_class_group_and_dedup(self):
        rows=[fundrow('02079K107','GOOG',150,'a','신규'),fundrow('02079K305','GOOGL',200,'a'),fundrow('02079K305','GOOGL',300,'b')]
        result=s.group_company_rankings(rows)
        self.assertEqual(len(result),1)
        self.assertEqual(result[0]['buy_usd'],650)
        self.assertEqual(result[0]['buyers'],2)
        self.assertEqual(result[0]['holders'],2)
        self.assertEqual(result[0]['new_buyers'],1)
        self.assertEqual(result[0]['ticker'],'GOOGL')
    def test_opposing_trends(self):
        bull=s.indicator(candles(1),'5m')
        bear=s.indicator(candles(-.5),'5m')
        self.assertGreater(bull['long'],bull['short'])
        self.assertGreater(bear['short'],bear['long'])
        self.assertEqual(bull['long']+bull['short'],100)
        self.assertEqual(bear['long']+bear['short'],100)
    def test_derived_timeframes(self):
        src={'5m':candles(1,120),'15m':candles(1,260),'1h':candles(1,360),
             '1d':candles(1,200),'1wk':candles(1,120),'1mo':candles(1,120)}
        out=s.build_signals(src)
        self.assertEqual(list(out),s.FRAMES)
        self.assertEqual(out['30m']['status'],'ok')
        self.assertEqual(out['4h']['status'],'ok')
    def test_ichimoku_forward_shift_no_lookahead(self):
        bars=candles(1,130)
        k=s.ichimoku(bars)
        self.assertEqual(k['status'],'ok')
        self.assertEqual(k['shift_bars'],26)
        # Cloud visible today is made from historic spans at t-26, not
        # the freshly calculated spans projected into the future.
        past=bars[:-26]
        mid=lambda xs:(max(x['h'] for x in xs)+min(x['l'] for x in xs))/2
        expected_a=(mid(past[-9:])+mid(past[-26:]))/2
        expected_b=mid(past[-52:])
        self.assertAlmostEqual(k['span_a_now'],round(expected_a,4))
        self.assertAlmostEqual(k['span_b_now'],round(expected_b,4))
        self.assertNotEqual(k['span_a_now'],k['projected_span_a'])
        # Changes to the most recent bar cannot rewrite the *already*
        # visible cloud, which was calculated 26 completed bars ago.
        modified=[dict(b) for b in bars]
        modified[-1]['h']+=25; modified[-1]['c']+=25
        other=s.ichimoku(modified)
        self.assertEqual(k['span_a_now'],other['span_a_now'])
        self.assertEqual(k['span_b_now'],other['span_b_now'])
        self.assertEqual(k['cloud_top'],other['cloud_top'])

    def test_ichimoku_minimum_and_flat(self):
        self.assertEqual(s.ichimoku(candles(n=77))['status'],'insufficient')
        self.assertEqual(s.indicator(candles(n=77),'1mo')['status'],'insufficient')
        bars=[{'t':1700000000+i*300,'o':100.,'h':100.,'l':100.,'c':100.,'v':1000.} for i in range(78)]
        self.assertEqual(s.ichimoku(bars)['status'],'ok')
        signal=s.indicator(bars,'1mo')
        self.assertEqual(signal['long'],50)
        self.assertEqual(signal['ichimoku']['cloud_position'],'구름 안')
        self.assertEqual(signal['ichimoku']['score'],0)

    def test_unavailable(self):
        self.assertEqual(s.indicator([],'5m')['status'],'insufficient')
        self.assertTrue(s.is_etf({'ticker':'SPY','name':'SPDR S&P 500 ETF'}))
        self.assertFalse(s.is_etf({'ticker':'GOOGL','name':'Alphabet'}))

if __name__=='__main__':unittest.main()
