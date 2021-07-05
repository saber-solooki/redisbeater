from unittest import TestCase

from celery.contrib.testing.app import TestApp
from celery.schedules import schedule
from fakeredis import FakeStrictRedis

from redisbeater.schedulers import RedisBeaterSchedulerEntry


class AppCase(TestCase):
    def setUp(self):
        try:
            self.app = TestApp(config=self.config_dict)
        except Exception:
            self.app = TestApp()
        self.setup()


class RedisBeaterCase(AppCase):
    def setup(self):
        self.app.conf.add_defaults(
            {'REDISBEATER_KEY_PREFIX': 'rb-tests:', 'redisbeater_key_prefix': 'rb-tests:'}
        )
        self.app.redisbeater_redis = FakeStrictRedis(decode_responses=True)
        self.app.redisbeater_redis.flushdb()

    def create_entry(self, name=None, task=None, s=None, run_every=60, **kwargs):

        if name is None:
            name = 'test'

        if task is None:
            task = 'tasks.test'

        if s is None:
            s = schedule(run_every=run_every)

        e = RedisBeaterSchedulerEntry(name, task, s, app=self.app, **kwargs)

        return e
