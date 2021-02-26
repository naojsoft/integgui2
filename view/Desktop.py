#
# Eric Jeschke (eric@naoj.org)
#
import time
import threading

from gi.repository import Gtk

from ginga.misc import Bunch

from . import common
from . import Workspace


class Desktop(object):

    def __init__(self, w_dict, name, title):
        self.w_dict = w_dict
        self.name = name
        self.title = title

        self.count = 1
        self.detached = []
        self.w = Bunch.Bunch()

        self.w.ulh = w_dict['ulh']
        self.w.llh = w_dict['llh']

        ul = w_dict['ul']
        ll = w_dict['ll']
        #um = w_dict['um']
        lm = w_dict['lm']
        ur = w_dict['ur']
        lr = w_dict['lr']

        self.pane = Bunch.Bunch()
        for name in self.w.keys():
            #print('pane name is', name)
            sizes = list(self.w[name].get_sizes())
            bnch = Bunch.Bunch(name=name, sizes=sizes, time=None,
                               widget=self.w[name])
            self.pane[name] = bnch
            #self.w[name].connect('notify', self._get_resize_fn(bnch))

        self.ws_fr = {
            'll': Bunch.Bunch(frame=ll.get_widget(),
                              pane=self.pane.llh, idx=0),
            'ul': Bunch.Bunch(frame=ul.get_widget(),
                              pane=self.pane.ulh, idx=0),
            'lm': Bunch.Bunch(frame=lm.get_widget(),
                              pane=self.pane.llh, idx=1),
            #'um': Bunch.Bunch(frame=um.get_widget(),
            #                  pane=self.pane.ulh, idx=1),
            'lr': Bunch.Bunch(frame=lr.get_widget(),
                              pane=self.pane.llh, idx=2),
            'ur': Bunch.Bunch(frame=ur.get_widget(),
                              pane=self.pane.ulh, idx=1),
            }

        self.ws = {}
        self.lock = threading.RLock()

    def get_wsframe(self, loc):
        with self.lock:
            return self.ws_fr[loc].frame

    def _show_pane(self, loc, size):
        with self.lock:
            pinfo = self.ws_fr[loc].pane
            idx = self.ws_fr[loc].idx
            pane_w = pinfo.widget
            cur_size = pane_w.get_sizes()[idx]
            #print("Setting size for pane %s to %d" % (pinfo.name, size))
            pinfo.time = time.time()
            if cur_size < size:
                sizes = list(pinfo.sizes)
                sizes[idx] = size
                pane_w.set_sizes(sizes)

            return size - cur_size

    def _restore_pane(self, loc):
        with self.lock:
            pinfo = self.ws_fr[loc].pane
            idx = self.ws_fr[loc].idx
            pane_w = pinfo.widget
            old_size = pinfo.sizes[idx]
            #print("Maybe restore position for pane %s" % (pinfo.name))
            try:
                sizes = list(pinfo.sizes)
                sizes[idx] = old_size
                self.logger.debug("Restoring pane to size %d" % (old_size))
                pane_w.set_sizes(sizes)
                return size - old_size
            except:
                return 0

    def show_ws(self, name, size=450):
        with self.lock:
            bnch = self.ws[name]
            self._show_pane(bnch.loc, size)

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
            return [self.getWorkspace(key) for key in self.ws.keys()]

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

    ## def _get_resize_fn(self, bnch):
    ##     #def _pane_resized(pane_w, event):
    ##     def _pane_resized(*args):
    ##         print('resize', *args)
    ##         # Callback function when pane is resized
    ##         pos = pane_w.get_position()
    ##         # Try to determine (via very ugly code) whether resize was
    ##         # a result of programmatic or manual resize by a human
    ##         if bnch.time and (time.time() - bnch.time < 0.5):
    ##             pass
    ##         else:
    ##             # If manually resized, record the new size so we don't
    ##             # undo a resize that was intentional
    ##             self.logger.debug("Pane manually resized to %d" % (pos))
    ##             bnch.pos = pos

    ##     return _pane_resized

#END
