# 
#[ Eric Jeschke (eric@naoj.org) --
#  Last edit: Fri Oct 22 21:24:15 HST 2010
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

        vframe = gtk.VPaned()

        ulhframe = gtk.HPaned()
        ulhframe.set_size_request(-1, 400)
        llhframe = gtk.HPaned()
        umhframe = gtk.HPaned()
        umhframe.set_size_request(-1, 400)
        lmhframe = gtk.HPaned()
        ulhframe.add2(umhframe)
        llhframe.add2(lmhframe)
        
        frame.pack_start(vframe, fill=True, expand=True)

        ul = gtk.VBox()
        ul.set_size_request(850, 400)
        ll = gtk.VBox()
        ll.set_size_request(550, -1)
        um = gtk.VBox()
        um.set_size_request(0, -1)
        lm = gtk.VBox()
        lm.set_size_request(460, -1)
        ur = gtk.VBox()
        lr = gtk.VBox()

        ulhframe.add1(ul)
        llhframe.add1(ll)
        umhframe.add1(um)
        lmhframe.add1(lm)
        umhframe.add2(ur)
        lmhframe.add2(lr)

        vframe.add1(ulhframe)
        vframe.add2(llhframe)
        
        self.ws_fr = {
            'll': ll,
            'ul': ul,
            'lm': lm,
            'um': um,
            'lr': lr,
            'ur': ur,
            }

        self.ws = {}
        self.lock = threading.RLock()

        vframe.show_all()


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

    def gui_moveto_workspace(self, src_ws, page):
        
        def move_page(w, rsp, went):
            name = went.get_text()
            w.destroy()
            if rsp == 1:
                dst_ws = self.getWorkspace(name)
                self.move_page(src_ws, page, dst_ws)
            return True

        dialog = gtk.MessageDialog(flags=gtk.DIALOG_DESTROY_WITH_PARENT,
                                   type=gtk.MESSAGE_QUESTION,
                                   buttons=gtk.BUTTONS_OK_CANCEL,
                                   message_format="To workspace:")
        dialog.set_title("Move page")
        # Add a combo box to the content area containing the names of the
        # current workspaces
        vbox = dialog.get_content_area()
        cbox = gtk.combo_box_new_text()
        index = 0
        names = []
        for name in self.getNames():
            cbox.insert_text(index, name)
            names.append(name)
            index += 1
        cbox.set_active(0)
        vbox.add(cbox)
        cbox.show()
        dialog.connect("response", move_page, cbox, names)
        dialog.show()


    def move_page(self, src_ws, page, dst_ws):
        src_ws.move_page(page, dst_ws)
        
#END
