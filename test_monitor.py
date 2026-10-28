import unittest
import json
import tempfile
from pathlib import Path
from datetime import datetime
from monitor import UsageReader, BalanceLedger, CST


class MonitorTests(unittest.TestCase):
    def test_streamed_blocks_append_and_day_boundary(self):
        with tempfile.TemporaryDirectory() as t:
            p = Path(t) / 'session.jsonl'
            def event(output, mid='one', ts='2026-10-27T16:01:00Z'):
                return json.dumps({'type':'assistant','timestamp':ts,'sessionId':'s','message':{
                    'id':mid,'model':'deepseek-flash','usage':{'input_tokens':100,'output_tokens':output,
                    'cache_read_input_tokens':50}}}) + '\n'
            p.write_text(event(2) + event(4))
            r = UsageReader(t)
            d = r.read('2026-10-28')
            self.assertEqual((d['calls'],d['input'],d['output']),(1,150,4))
            with p.open('a') as f:
                f.write(event(5))
                f.write(event(3, 'old', '2026-10-27T15:59:00Z'))
            d = r.read('2026-10-28')
            self.assertEqual((d['calls'],d['input'],d['output']),(1,150,5))
            self.assertEqual(r.read('2026-10-27')['calls'],1)
            # A partially-written JSON line must be retried after completion.
            with p.open('a') as f: f.write(event(8,'two')[:-1])
            self.assertEqual(r.read('2026-10-28')['calls'],1)
            with p.open('a') as f: f.write('\n')
            self.assertEqual(r.read('2026-10-28')['calls'],2)
            (Path(t)/'imported.jsonl').write_text(p.read_text())
            self.assertEqual(r.read('2026-10-28')['calls'],2)

    def test_balance_deductions_topups_and_rollover(self):
        with tempfile.TemporaryDirectory() as t:
            led = BalanceLedger(Path(t)/'ledger.json')
            now = datetime(2026,10,28,12,tzinfo=CST)
            def update(n, time=now):
                return led.update({'balance_infos':[{'currency':'CNY','total_balance':str(n)}]},time)[0]
            self.assertEqual(update(8)['spent'],'0')
            self.assertEqual(update(7.9)['spent'],'0.1')
            self.assertEqual(update(20)['spent'],'0.1')
            self.assertEqual(update(19.8)['spent'],'0.3')
            self.assertEqual(update(19.5,datetime(2026,10,29,1,tzinfo=CST))['spent'],'0')


if __name__ == '__main__':
    unittest.main()
