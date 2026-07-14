""" Misc Python utilities,  DaveP April-May 26
    Dave Parkinson, dhparki@outlook.com
"""

import os
from time import perf_counter

def stfu(func):
    """Decorator to suppress stderr output from a function"""
    def wrapper(*args, **kwargs):
        null_fd = os.open(os.devnull, os.O_RDWR)
        save_fd = os.dup(2)     # save stderr
        os.dup2(null_fd, 2)     # redirect stderr to /dev/null
        try:
            retval = func(*args, **kwargs)
        finally:
            os.dup2(save_fd, 2)     # restore all
            os.close(null_fd)
            os.close(save_fd)
        return retval
    return wrapper

def timeit(func):
    """Decorator to time a function in ms (2dp)"""
    def wrapper(*args, **kwargs):
        t1 = perf_counter()
        retval = func(*args, **kwargs)
        t2 = perf_counter()
        print(f'{func.__name__} took {(t2 - t1)*1000:.2f}ms')
        return retval
    return wrapper
