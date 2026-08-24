import unittest
import time
from rate_limiter import TokenBucket

class TestTokenBucket(unittest.TestCase):
    def test_consume_tokens(self):
        bucket = TokenBucket(capacity=5, refill_rate=1.0)
        for _ in range(5):
            self.assertTrue(bucket.consume(1))
        self.assertFalse(bucket.consume(1))

    def test_refill_tokens(self):
        bucket = TokenBucket(capacity=2, refill_rate=5.0)
        self.assertTrue(bucket.consume(2))
        self.assertFalse(bucket.consume(1))
        time.sleep(0.3)
        self.assertTrue(bucket.consume(1))

if __name__ == "__main__":
    unittest.main()

