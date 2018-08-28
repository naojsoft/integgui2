# 
# Eric Jeschke (eric@naoj.org)
#
from __future__ import absolute_import
from __future__ import print_function
import time
import threading

from gi.repository import Gtk

from ginga.misc import Bunch

from . import common
from . import Workspace

from six.moves import map


class Desktop(object):
    
    def __init__(self, frame, name, title):
        self.frame = frame
        self.name = name
        self.title = title

        self.count = 1
        self.detached = []
        self.w = Bunch.Bunch()
        
        # TODO: should generalize to number of rows and columns

        vframe = Gtk.VPaned()

        self.w.ulh = Gtk.HPaned()
        #self.w.ulh.set_size_request(-1, 400)
        self.w.llh = Gtk.HPaned()
        self.w.umh = Gtk.HPaned()
        #self.w.umh.set_size_request(-1, 400)
        self.w.lmh = Gtk.HPaned()
        self.w.ulh.pack2(self.w.umh, True, True)
        self.w.llh.pack2(self.w.lmh, True, True)
        
        frame.pack_start(vframe, True, True, 0)

        ul = Gtk.VBox()
        #ul.set_size_request(850, 400)
        ll = Gtk.VBox()
        #ll.set_size_request(550, -1)
        um = Gtk.VBox()
        #um.set_size_request(0, -1)
        lm = Gtk.VBox()
        #lm.set_size_request(460, -1)
        ur = Gtk.VBox()
        lr = Gtk.VBox()

        self.w.ulh.pack1(ul, True, True)
        self.w.llh.pack1(ll, True, True)
        self.w.umh.pack1(um, True, True)
        self.w.lmh.pack1(lm, True, True)
        self.w.umh.pack2(ur, True, True)
        self.w.lmh.pack2(lr, True, True)
        self.pane = Bunch.Bunch()
        for name in self.w.keys():
            bnch = Bunch.Bunch(name=name, pos=None, time=None,
                               widget=self.w[name])
            self.pane[name] = bnch
            self.w[name].connect('notify', self._get_resize_fn(bnch))

        vframe.pack1(self.w.ulh, True, True)
        vframe.pack2(self.w.llh, True, True)

        self.ws_fr = {
            'll': Bunch.Bunch(frame=ll, pane=self.pane.llh),
            'ul': Bunch.Bunch(frame=ul, pane=self.pane.ulh),
            'lm': Bunch.Bunch(frame=lm, pane=self.pane.lmh),
            'um': Bunch.Bunch(frame=um, pane=self.pane.umh),
            'lr': Bunch.Bunch(frame=lr, pane=self.pane.lmh),
            'ur': Bunch.Bunch(frame=ur, pane=self.pane.umh),
            }

        self.ws = {}
        self.lock = threading.RLock()

        vframe.show_all()


    def get_wsframe(self, loc):
        with self.lock:
            return self.ws_fr[loc].frame

    def _show_pane(self, loc, pos):
        with self.lock:
            pinfo = self.ws_fr[loc].pane
            pane_w = pinfo.widget
            cur_pos = pane_w.get_position()
            print("Setting position for pane %s to %d" % (pinfo.name, cur_pos))
            pinfo.pos = cur_pos
            pinfo.time = time.time()
            if cur_pos < pos:
                pane_w.set_position(pos)

            return pos - cur_pos
            
    def _restore_pane(self, loc):
        with self.lock:
            pinfo = self.ws_fr[loc].pane
            pane_w = pinfo.widget
            cur_pos = pane_w.get_position()
            print("Maybe restore position for pane %s" % (pinfo.name))
            try:
                pos = pinfo.pos
                self.logger.debug("Restoring pane to pos %d" % (pos))
                pane_w.set_position(pos)
                return pos - cur_pos
            except:
                return 0

    def show_ws(self, name, pos=450):
        with self.lock:
            bnch = self.ws[name]
            self._show_pane(bnch.loc, pos)
    
    def restore_ws(self, name):
        with self.lock:
            bnch = self.ws[name]
            self._restore_pane(bnch.loc)
    
    def addws(self, loc, name, title):
        with self.lock:
            if name in self.ws:
                raise Exception("A workspace with name '%s' already exists!" % name)

            frame = self.get_wsframe(loc)

            ws = Workspace.Workspace(frame, name, title)
            # Some attributes we force on our children
            ws.logger = self.logger
            ws.parent = self

            frame.show_all()

            self.count += 1
            self.ws[name] = Bunch.Bunch(ws=ws, frame=frame, loc=loc)
            return ws

    def add_detached(self, name, title, x=None, y=None):
        with self.lock:
            if name in self.ws:
                raise Exception("A workspace with name '%s' already exists!" % name)
            root = Gtk.Window(Gtk.WindowType.TOPLEVEL)
            root.set_title(title)
            # TODO: this needs to be more sophisticated
            root.connect("delete_event", lambda w, e: w.hide())
            root.set_border_width(2)

            # create main frame
            frame = Gtk.VBox(spacing=2)
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
            self.ws[name] = Bunch.Bunch(ws=ws, frame=frame, loc=None)
            return ws

    def add_detached_noname(self, x=None, y=None):
        with self.lock:
            while 'ws%d' % self.count in self.ws:
                self.count += 1
            name = 'ws%d' % self.count
            title = 'Workspace %d' % self.count
            return self.add_detached(name, title, x=x, y=y)
        
    def getWorkspace(self, name):
        with self.lock:
            return self.ws[name].ws

    def getWorkspaces(self):
        with self.lock:
            return list(map(self.getWorkspace, list(self.ws.keys())))

    def getPages(self, name):
        """Return a list of tuples of (ws, page) for pages matching
        _name_.
        """
        with self.lock:
            res = []
            for ws in self.getWorkspaces():
                try:
                    res.append((ws, ws.getPage(name)))
                except KeyError:
                    pass
            return res

    def getPage(self, name):
        results = self.getPages(name)
        if len(results) == 1:
            return results[0]

        raise KeyError("There are multiple pages with the name '%s'" % name)
    
    def getNames(self):
        with self.lock:
            return list(self.ws.keys())

    def gui_moveto_workspace(self, src_ws, page):
        
        def move_page(w, rsp, went):
            name = went.get_text()
            w.destroy()
            if rsp == 1:
                dst_ws = self.getWorkspace(name)
                self.move_page(src_ws, page, dst_ws)
            return True

        dialog = Gtk.MessageDialog(flags=Gtk.DialogFlags.DESTROY_WITH_PARENT,
                                   type=Gtk.MessageType.QUESTION,
                                   buttons=Gtk.ButtonsType.OK_CANCEL,
                                   message_format="To workspace:")
        dialog.set_title("Move page")
        # Add a combo box to the content area containing the names of the
        # current workspaces
        vbox = dialog.get_content_area()
        cbox = Gtk.ComboBoxText()
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

    def _get_resize_fn(self, bnch):
        def _pane_resized(pane_w, info):
            # Callback function when pane is resized
            pos = pane_w.get_position()
            # Try to determine (via very ugly code) whether resize was
            # a result of programmatic or manual resize by a human
            if bnch.time and (time.time() - bnch.time < 0.5):
                pass
            else:
                # If manually resized, record the new size so we don't
                # undo a resize that was intentional
                self.logger.debug("Pane manually resized to %d" % (pos))
                bnch.pos = pos

        return _pane_resized
        
#END
