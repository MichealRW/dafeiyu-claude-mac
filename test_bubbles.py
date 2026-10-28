"""Timing and content regressions for the animated thought interaction."""
import unittest
from bubbles import BalanceThought


class ThoughtTests(unittest.TestCase):
    def setUp(self):
        self.now=100
        self.thought=BalanceThought(lambda:self.now)

    def test_fast_reply_still_has_a_readable_thinking_intro(self):
        self.thought.begin([])
        self.now+=.05
        self.thought.resolve([{'currency':'CNY','balance':'12.34'}])
        self.assertEqual(self.thought.phase(),'intro')
        self.now+=1.2
        self.assertEqual(self.thought.phase(),'ready')
        self.assertTrue(self.thought.active())

    def test_late_reply_does_not_reopen_expired_bubble(self):
        self.thought.begin([])
        self.now+=15
        self.assertFalse(self.thought.resolve([{'currency':'CNY','balance':'12.34'}]))
        self.assertFalse(self.thought.active())

    def test_failure_preserves_last_known_balance(self):
        rows=[{'currency':'CNY','balance':'12.34'}]
        self.thought.begin(rows)
        self.now+=2
        self.thought.resolve(error=True)
        self.assertEqual(self.thought.phase(),'error')
        self.assertEqual(self.thought.rows,rows)

    def test_thinking_pose_never_enters_unrelated_original_chatter(self):
        self.thought.begin([])
        for offset in range(120):
            self.now=100+offset/10
            self.assertGreaterEqual(self.thought.pose_elapsed(),0)
            self.assertLess(self.thought.pose_elapsed(),2)


if __name__=='__main__':unittest.main()
