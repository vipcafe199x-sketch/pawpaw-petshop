"""Bounded process-local failed-login throttle (not a distributed WAF or MFA)."""
import hashlib
import math
import time
from collections import OrderedDict, deque
from threading import RLock


class FailedLoginLimiter:
    def __init__(self,window=900,account_limit=8,ip_limit=40,capacity=4096,clock=time.monotonic):
        self.window=window;self.account_limit=account_limit;self.ip_limit=ip_limit
        self.capacity=capacity;self.clock=clock;self.buckets=OrderedDict();self.lock=RLock()

    @staticmethod
    def _account_key(ip,email):
        # Fixed-size identity: an arbitrarily long login input must not occupy
        # an arbitrarily large persistent cache key, or retain the raw email.
        return ('account',ip,hashlib.sha256(email.encode('utf-8')).digest())

    def _bucket(self,key,now,create=False):
        bucket=self.buckets.get(key)
        if bucket is not None:
            while bucket and now-bucket[0]>=self.window: bucket.popleft()
            if not bucket:
                del self.buckets[key];bucket=None
        if bucket is None and create:
            bucket=deque();self.buckets[key]=bucket
        if bucket is not None: self.buckets.move_to_end(key)
        while len(self.buckets)>self.capacity: self.buckets.popitem(last=False)
        return bucket

    def retry_after(self,ip,email):
        with self.lock:
            now=self.clock();wait=0
            for key,limit in ((('ip',ip),self.ip_limit),(self._account_key(ip,email),self.account_limit)):
                bucket=self._bucket(key,now)
                if bucket is not None and len(bucket)>=limit:
                    wait=max(wait,math.ceil(self.window-(now-bucket[0])))
            return wait

    def failure(self,ip,email):
        with self.lock:
            now=self.clock()
            for key in (('ip',ip),self._account_key(ip,email)):
                self._bucket(key,now,True).append(now)

    def success(self,ip,email):
        with self.lock:
            self.buckets.pop(self._account_key(ip,email),None)
            # A valid account must not clear other accounts or the aggregate IP limit.
