#!/usr/bin/env
#-*- coding:utf-8 -*- 

import threading
import os
import sys
 
class _Timer(threading.Thread):
    def __init__(self, interval, function, args=[], kwargs={}):
        threading.Thread.__init__(self)
        self.interval = interval 
        self.function = function
        self.args = args
        self.kwargs = kwargs
        self.finished = threading.Event()
 
    def cancel(self):
        self.finished.set() 
 
    def run(self):
        self.finished.wait(self.interval) 
        if not self.finished.is_set():
            self.function(*self.args, **self.kwargs)
            self.finished.set()
     
class CycleTimer(_Timer):
    def __init__(self, interval, function, *args, **kwargs):
        _Timer.__init__(self, interval, function, *args, **kwargs)
 
    def run(self):
        while True:
            if not self.finished.is_set():
                self.finished.wait(self.interval)
                self.function(*self.args, **self.kwargs) 
            else:
                break


def test(*args, **kwargs):
    print("CycleTimer", args, kwargs)

if __name__ == "__main__":
    c_t = CycleTimer(1, test, [1,2], {"b":2, "c":3})
    c_t.start()
    #c_t.cancel()
