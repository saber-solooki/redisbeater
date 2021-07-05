import json
from datetime import datetime, timedelta

from celery.utils.time import maybe_make_aware

from redisbeater import RedisBeaterSchedulerEntry
from redisbeater.decoder import RedisBeaterJSONDecoder, from_timestamp, to_timestamp
from tests.basecase import RedisBeaterCase

CELERY_CONFIG_DEFAULT_KWARGS = {}


class test_RedisBeaterEntry(RedisBeaterCase):
    def test_basic_save(self):
        e = self.create_entry()
        e.save()

        expected = {
            'name': 'test',
            'task': 'tasks.test',
            'schedule': e.schedule,
            'args': None,
            'kwargs': CELERY_CONFIG_DEFAULT_KWARGS,
            'options': {},
            'enabled': True,
        }
        expected_key = self.app.redisbeater_conf.key_prefix + 'test'

        redis = self.app.redisbeater_redis
        value = redis.hget(expected_key, 'definition')
        self.assertEqual(expected, json.loads(value, cls=RedisBeaterJSONDecoder))
        self.assertEqual(redis.zrank(self.app.redisbeater_conf.schedule_key, e.key), 0)
        self.assertEqual(redis.zscore(self.app.redisbeater_conf.schedule_key, e.key), e.score)

    def test_from_key_nonexistent_key(self):
        with self.assertRaises(KeyError):
            RedisBeaterSchedulerEntry.from_key('doesntexist', self.app)

    def test_from_key_missing_meta(self):
        initial = self.create_entry().save()

        loaded = RedisBeaterSchedulerEntry.from_key(initial.key, self.app)
        self.assertEqual(initial.task, loaded.task)
        self.assertIsNotNone(loaded.last_run_at)

    def test_next(self):
        initial = self.create_entry().save()
        now = self.app.now()
        # 3.x is naive but 4.x is aware
        now = maybe_make_aware(now)

        n = initial.next(last_run_at=now)

        self.assertIsNotNone(now.tzinfo)
        self.assertEqual(n.last_run_at, now)
        self.assertEqual(initial.total_run_count + 1, n.total_run_count)

        # updated meta was stored into redis
        loaded = RedisBeaterSchedulerEntry.from_key(initial.key, app=self.app)
        self.assertEqual(loaded.last_run_at, now)
        self.assertEqual(loaded.total_run_count, initial.total_run_count + 1)

        # new entry updated the schedule
        redis = self.app.redisbeater_redis
        self.assertEqual(redis.zscore(self.app.redisbeater_conf.schedule_key, n.key), n.score)

    def test_next_only_update_last_run_at(self):
        initial = self.create_entry()

        n = initial.next(only_update_last_run_at=True)
        self.assertGreater(n.last_run_at, initial.last_run_at)
        self.assertEqual(n.total_run_count, initial.total_run_count)

    def test_delete(self):
        initial = self.create_entry()
        initial.save()

        e = RedisBeaterSchedulerEntry.from_key(initial.key, app=self.app)
        e.delete()

        exists = self.app.redisbeater_redis.exists(initial.key)
        self.assertFalse(exists)

        score = self.app.redisbeater_redis.zrank(self.app.redisbeater_conf.schedule_key, initial.key)
        self.assertIsNone(score)

    def test_due_at_never_run(self):
        entry = self.create_entry(last_run_at=datetime.min)

        before = entry._default_now()
        due_at = entry.due_at
        after = entry._default_now()

        self.assertLess(before, due_at)
        self.assertLess(due_at, after)

    def test_due_at(self):
        entry = self.create_entry()

        now = entry._default_now()

        entry.last_run_at = now
        due_at = entry.due_at

        self.assertLess(now, due_at)
        self.assertLess(due_at, now + entry.schedule.run_every)

    def test_due_at_overdue(self):
        last_run_at = self.app.now() - timedelta(hours=10)
        entry = self.create_entry(last_run_at=last_run_at)

        before = entry._default_now()
        due_at = entry.due_at

        self.assertLess(last_run_at, due_at)
        self.assertGreater(due_at, before)

    def test_score(self):
        run_every = 61 * 60
        entry = self.create_entry(run_every=run_every)
        entry = entry._next_instance()

        score = entry.score
        expected = entry.last_run_at + timedelta(seconds=run_every)
        expected = expected.replace(microsecond=0)  # discard microseconds, lost in timestamp
        # 3.x returns naive, but 4.x returns aware
        expected = maybe_make_aware(expected)

        self.assertEqual(score, to_timestamp(expected))
        self.assertEqual(expected, from_timestamp(score))
