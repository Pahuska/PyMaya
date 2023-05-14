import time
from maya.api import OpenMaya as om2
from collections import OrderedDict


def timeit(name='timer', log=False, verbose=True):
    def wrapper(func):
        def timed(*args, **kwargs):
            with Timer(name=name, log=log, verbose=verbose):
                result = func(*args, **kwargs)
            return result
        return timed
    return wrapper


class Timer:
    resultDic = OrderedDict()

    def __init__(self, name='timer', log=False, verbose=True):
        self.start = None
        self.end = None
        self.verbose = verbose
        self.name = name
        self.log = log
        self.interval = None

    def __enter__(self):
        self.start = time.time()
        return self

    def timeit(self):
        self.end = time.time()
        self.interval = self.end - self.start

        if self.log is not None:
            if self.name not in self.resultDic:
                self.resultDic[self.name] = 0.0
            self.resultDic[self.name] += self.interval

        if self.verbose:
            print(self.name, ':', self.interval)

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.timeit()

    @classmethod
    def printDic(cls, clear=False):
        for k, v in cls.resultDic.items():
            print('{} : {}'.format(k, v))
        if clear:
            cls.clearDic()

    @classmethod
    def clearDic(cls, **kwargs):
        if len(kwargs):
            for k, v in kwargs.items():
                if k in cls.resultDic and v:
                    del cls.resultDic[k]
        else:
            cls.resultDic = OrderedDict()


def uniqueObjExists(name):
    try:
        sel = om2.MSelectionList()
        sel.add(name)
        return True
    except:
        return False


# TODO: Any use for this ?
class Iterator(object):
    def __init__(self, data):
        self.data = data
        self.max = len(data) - 1
        self._isDone = False
        self.n = 0

    def __len__(self):
        return len(self.data)

    def __iter___(self):
        self.n = 0
        return self

    def __next__(self):
        if self.n < self.max:
            result = self.data[self.n]
            self.n += 1
            return result
        else:
            self._isDone = True

    def next(self):
        self.__next__()

    def isDone(self):
        return self._isDone

    def currentItem(self):
        return self.data[self.n]

    def currentIndex(self):
        return self.n


def prodList(lst):
    count = 1
    for n in lst:
        count *= n
    return count