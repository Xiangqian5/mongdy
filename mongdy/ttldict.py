from collections import UserDict
from threading import RLock, Lock
import time

class TTLDict(UserDict):
    def __init__(self, *args, **kwargs):
        self._rlock = RLock()
        self._lock = Lock()

        super().__init__(*args, **kwargs)

    def __repr__(self):
        #return '<TTLDict@%#08x; %r;>' % (id(self), self.data)
        return '<TTLDict %r>' % (self.data)

    def set_ttl(self, key, ttl, now=None):
        """ Set TTL for the given key """
        if now is None:
            now = time.time()
        with self._rlock:
            _expire, value = self.data[key]
            self.data[key] = (now + ttl, value)

    def get_ttl(self, key, now=None):
        """ Return remaining TTL for a key """
        if now is None:
            now = time.time()
        with self._rlock:
            expire, _value = self.data[key]
            return expire - now

    def setex(self, key, ttl, value):
        """ Set TTL and value for the given key """
        with self._rlock:
            expire = time.time() + ttl
            self.data[key] = (expire, value)

    def is_expired(self, key, now=None, remove=False):
        """ Check if key has expired """
        with self._rlock:
            if now is None:
                now = time.time()
                if key in self.data:
                    expire, _value = self.data[key]
                    if expire is None:
                        return False
                    expired = expire < now
                    if expired and remove:
                        del self.data[key]
                    return expired
                return True

    def __len__(self):
        with self._rlock:
            for key in self.data.keys():
                self.is_expired(key, remove=True)
            return len(self.data)

    def __iter__(self):
        with self._rlock:
            for key in self.data.keys():
                if not self.is_expired(key, remove=True):
                    yield key

    def __setitem__(self, key, value):
        with self._lock:
            self.data[key] = (None, value)

    def __delitem__(self, key):
        with self._lock:
            del self.data[key]

    def __getitem__(self, key):
        with self._rlock:
            self.is_expired(key, remove=True)
            return self.data[key][1] if key in self.data else None
        
if __name__ == "__main__":
        ttld = TTLDict()
        ttld["a"] = "A"
        ttld["b"] = "B"
        for k,v in (ttld.items()):
            print(k,v)
        ttld.set_ttl("a", 5)
        ttld.setex("c", 10, "C")
        print(ttld)
        time.sleep(6)
        print(ttld)
