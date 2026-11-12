import math,sys,sqlite3,time,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import whale50_signals as sig
import whale50_validation as v

def bars(n=110,trend=.1,start=None):
    start=start or int(time.time())-n*900
    out=[]
    for i in range(n):
        o=100+i*trend;c=o+.1
        out.append({'t':start+i*900,'o':o,'h':max(o,c)+.2,'l':min(o,c)-.2,'c':c,'v':100})
    return out

class ValidationTests(unittest.TestCase):
    def test_history_predictions_evaluated_next_bar(self):
        bs=bars(120)
        s=v.backtest_one(bs,'15m')
        self.assertGreater(s['correct'],0)
        self.assertEqual(s['correct']+s['wrong'],s['evaluated'])
        self.assertLessEqual(s['evaluated'],42)

    def test_no_future_leak(self):
        bs=bars(120)
        a=sig.indicator(bs[:100],'15m')
        bs[100]['c']=100000
        b=sig.indicator(bs[:100],'15m')
        self.assertEqual(a['long'],b['long'])

    def test_forward_only_registered_before_next_bar(self):
        con=sqlite3.connect(':memory:')
        bs=bars(100)
        v.record_forward(con,'TST','15m',bs)
        row=con.execute('SELECT result, side FROM forward_predictions').fetchone()
        self.assertEqual(row[0],'pending')
        count=con.execute('SELECT COUNT(*) FROM forward_predictions').fetchone()[0]
        v.record_forward(con,'TST','15m',bs)
        self.assertEqual(count,con.execute('SELECT COUNT(*) FROM forward_predictions').fetchone()[0])
        bs.append({'t':bs[-1]['t']+900,'o':110,'h':111,'l':109,'c':110.5,'v':100})
        v.record_forward(con,'TST','15m',bs)
        resolved=con.execute('SELECT result FROM forward_predictions ORDER BY signal_bar LIMIT 1').fetchone()[0]
        self.assertIn(resolved,('correct','wrong','flat'))
        c=v.forward_stats(con,'TST','15m')
        self.assertEqual(c['evaluated'],1)
        con.close()

    def test_other_monthframe_and_counts(self):
        con=sqlite3.connect(':memory:')
        result=v.report({'TST':{'1mo':bars(90)}},con)
        self.assertEqual(len(result['frame_order']),7)
        self.assertEqual(len(result['rows']),7)
        self.assertIsNone(result['historical']['15m']['hit_rate'])
        self.assertGreaterEqual(result['historical']['1mo']['evaluated'],0)

if __name__=='__main__': unittest.main()
