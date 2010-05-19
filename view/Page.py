#
#[ Eric Jeschke (eric@naoj.org) --
#  Last edit: Fri May 14 13:39:50 HST 2010
#]
#
import threading

class Page(object):

    def __init__(self, frame, name, title):

        self.frame = frame
        self.name = name
        self.title = title

        self.closed = False

        # every page has a lock
        self.lock = threading.RLock()

    def close(self):
        # parent attribute is added by parent workspace
        self.parent.delpage(self.name)

        self.closed = True


#END
