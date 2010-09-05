#
# command.py -- command object and queue object definitions
#
#[ Eric Jeschke (eric@naoj.org) --
#  Last edit: Sat Sep  4 17:09:09 HST 2010
#]

# remove once we're certified on python 2.6
from __future__ import with_statement

import threading


class QueueEmpty(Exception):
    pass


class CommandQueue(object):
    
    def __init__(self, name, logger):
        self.name = name
        self.logger = logger

        self.queue = []
        self.views = []
        self.flag = threading.Event()
        self.lock = threading.RLock()

        self.enable()

    def add_view(self, view):
        with self.lock:
            self.views.append(view)

    def del_view(self, view):
        with self.lock:
            self.views.remove(view)

    def mark_scheduled(self, cmdObjs):
        for cmdObj in cmdObjs:
            cmdObj.mark_status('scheduled')
        
    def mark_unscheduled(self, cmdObjs):
        for cmdObj in cmdObjs:
            cmdObj.mark_status('scheduled')
        
    def redraw(self):
        with self.lock:
            for view in self.views:
                view.redraw()
        
    def enabledP(self):
        return self.flag.isSet()

    def enable(self):
        return self.flag.set()

    def disable(self):
        return self.flag.clear()

    def enableIfPending(self):
        with self.lock:
            if len(self.queue) > 0:
                self.enable()
                return True

            else:
                return False

    def flush(self):
        with self.lock:
            while len(self.queue) > 0:
                cmdObj = self.queue.pop(0)
                cmdObj.mark_status('normal')

            self.redraw()

    def append(self, cmdObj):
        with self.lock:
            self.queue.append(cmdObj)
            cmdObj.mark_status('scheduled')

            self.redraw()
            
    add = append
            
    def prepend(self, cmdObj):
        with self.lock:
            self.queue.insert(0, cmdObj)
            cmdObj.mark_status('scheduled')

            self.redraw()
            
    def extend(self, cmdObjs):
        lstcopy = list(cmdObjs)
        with self.lock:
            self.queue.extend(lstcopy)
            for cmdObj in cmdObjs:
                cmdObj.mark_status('scheduled')
                
            self.redraw()
            
    def replace(self, cmdObjs):
        with self.lock:
            self.flush()
            self.extend(cmdObjs)
            
    def insert(self, i, cmdObjs):
        """Insert command objects before index _i_.
        Indexing is zero based."""
        with self.lock:
            assert len(self.queue) 
            self.queue = self.queue[:i] + cmdObjs + self.queue[i:]
            for cmdObj in cmdObjs:
                cmdObj.mark_status('scheduled')
                
            self.redraw()
            
    def delete(self, i, j):
        """Delete command objects from indexes _i_:_j_.
        Indexing is zero based."""
        with self.lock:
            deleted = self.queue[i:j]
            self.queue = self.queue[:i] + self.queue[j:]
            for cmdObj in deleted:
                cmdObj.mark_status('normal')
                
            self.redraw()
            return deleted
            
    def peek(self):
        with self.lock:
            try:
                return self.queue[0]
            except IndexError:
                raise QueueEmpty('Queue %s is empty' % self.name)


    def peekAll(self):
        with self.lock:
            return list(self.queue)

    def remove(self, cmdObj):
        with self.lock:
            self.queue.remove(cmdObj)
            cmdObj.mark_status('normal')

            self.redraw()

    def get(self):
        with self.lock:
            if not self.enabledP():
                raise QueueEmpty('Queue %s is empty' % self.name)

            try:
                cmdObj = self.queue.pop(0)
                self.redraw()
                return cmdObj
            except IndexError:
                raise QueueEmpty('Queue %s is empty' % self.name)


    def __len__(self):
        with self.lock:
            return len(self.queue)

    def __getitem__(self, key):
        raise Exception("Not yet implemented!")
    
    def __setitem__(self, key, val):
        raise Exception("Not yet implemented!")
    
    def __setslice__(self, i, j, sequence):
        raise Exception("Not yet implemented!")
    
    def __delslice__(self, i, j):
        raise Exception("Not yet implemented!")
    
    def __delitem__(self, key):
        raise Exception("Not yet implemented!")
    
    def __iter__(self, i):
        raise Exception("Not yet implemented!")
    
    def __contains__(self, val):
        raise Exception("Not yet implemented!")
    
#END
