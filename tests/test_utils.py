from celery.utils.time import maybe_make_aware

from redisbeater.decoder import from_timestamp, to_timestamp
from tests.basecase import RedisBeaterCase


class Test_utils(RedisBeaterCase):
    def test_roundtrip(self):
        now = self.app.now()
        # 3.x returns naive, but 4.x returns aware
        now = maybe_make_aware(now)

        roundtripped = from_timestamp(to_timestamp(now))

        # we lose microseconds in the roundtrip, so we need to ignore them
        now = now.replace(microsecond=0)

        self.assertEqual(now, roundtripped)
