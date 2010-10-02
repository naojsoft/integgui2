# 
#[ Eric Jeschke (eric@naoj.org) --
#  Last edit: Thu Sep 30 17:46:24 HST 2010
#]

# remove once we're certified on python 2.6
from __future__ import with_statement

import threading
import gtk

import Workspace


class Desktop(object):
    
    def __init__(self, frame, name, title):
        self.frame = frame
        self.name = name
        self.title = title

        self.count = 1
        self.detached = []
        
        # TODO: should generalize to number of rows and columns

        paned = gtk.HPaned()
        self.hframe = paned
        paned.show()

        frame.pack_start(paned, fill=True, expand=True)

        lframe = gtk.VPaned()
        rframe = gtk.VPaned()

        paned.add1(lframe)
        paned.add2(rframe)

        ul = gtk.VBox()
        lframe.add1(ul)
        ll = gtk.VBox()
        lframe.add2(ll)

        ur = gtk.VBox()
        rframe.add1(ur)
        lr = gtk.VBox()
        rframe.add2(lr)

        self.ws_fr = {
            'll': ll,
            'ul': ul,
            'lr': lr,
            'ur': ur,
            }

        self.ws = {}
        self.lock = threading.RLock()

        paned.show_all()


    def get_wsframe(self, name):
        with self.lock:
            return self.ws_fr[name]

    def addws(self, loc, name, title):

        with self.lock:
            if self.ws.has_key(name):
                raise Exception("A workspace with name '%s' already exists!" % name)

            frame = self.get_wsframe(loc)

            ws = Workspace.Workspace(frame, name, title)
            # Some attributes we force on our children
            ws.logger = self.logger
            ws.parent = self

            frame.show_all()

            self.count += 1
            self.ws[name] = ws
            return ws

    def add_detached(self, name, title, x=None, y=None):
        with self.lock:
            if self.ws.has_key(name):
                raise Exception("A workspace with name '%s' already exists!" % name)
            root = gtk.Window(gtk.WINDOW_TOPLEVEL)
            root.set_title(title)
            # TODO: this needs to be more sophisticated
            root.connect("delete_event", lambda w, e: w.hide())
            root.set_border_width(2)

            # create main frame
            frame = gtk.VBox(spacing=2)
            root.add(frame)

            ws = Workspace.Workspace(frame, name, title)
            # Some attributes we force on our children
            ws.logger = self.logger
            ws.parent = self

            self.detached.append(root)
            root.show_all()
            if x:
                root.move(x, y)
            
            self.count += 1
            self.ws[name] = ws
            return ws

    def add_detached_noname(self, x=None, y=None):
        with self.lock:
            while self.ws.has_key('ws%d' % self.count):
                self.count += 1
            name = 'ws%d' % self.count
            title = 'Workspace %d' % self.count
            return self.add_detached(name, title, x=x, y=y)
        
    def getWorkspace(self, name):
        with self.lock:
            return self.ws[name]

    def getWorkspaces(self):
        with self.lock:
            return self.ws.values()

    def getNames(self):
        with self.lock:
            return self.ws.keys()


#END
