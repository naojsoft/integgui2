# 
#[ Eric Jeschke (eric@naoj.org) --
#  Last edit: Fri Oct  1 16:35:35 HST 2010
#]

# remove once we're certified on python 2.6
from __future__ import with_statement

import sys
import threading
import traceback

import gtk

# module-level var used for drag-and-drop of pages
drag_src = None


class Workspace(object):
    
    def __init__(self, frame, name, title):
        self.frame = frame
        self.name = name
        self.title = title

        nb = gtk.Notebook()
        nb.set_tab_pos(gtk.POS_TOP)
        nb.set_scrollable(True)
        nb.set_show_tabs(True)
        nb.set_show_border(True)
        nb.set_size_request(900, 500)
        # Allows drag-and-drop between notebooks
        nb.set_group_id(1)
        nb.connect("page-added", self._page_added)
        nb.connect("page-removed", self._page_removed)
        # Allows dragging pages to create top-level detached workspaces
        #nb.connect("create-window", self._detach_page)
        #nb.popup_enable()

        nb.show()

        self.widget = nb
        frame.pack_start(self.widget, expand=True, fill=True,
                         padding=2)

        # Holds my pages
        self.pages = {}
        self.pages_w = {}
        self.lock = threading.RLock()


    def makename(self, name):
        with self.lock:
            if not self.pages.has_key(name):
                return name

            for i in xrange(2, 100000):
                possname = '%s(%d)' % (name, i)
                if not self.pages.has_key(possname):
                    return possname

            raise Exception("A page with name '%s' already exists!" % name)


    def _addpage(self, name, title, child, pageobj):
        with self.lock:
            if self.pages.has_key(name):
                if not adjname:
                    raise Exception("A page with name '%s' already exists!" % name)
                newname = self.makename(name)
                if title == name:
                    title = newname
                name = newname

            # Create a label for the notebook tab
            label = gtk.Label(title)
            label.show()

            # Add the page to the notebook
            self.widget.append_page(child, label)

            self.widget.set_tab_reorderable(child, True)
            self.widget.set_tab_detachable(child, True)
            
            # Some attributes we force on our children
            pageobj.logger = self.logger
            # ?? cyclical reference causes problems for gc?
            pageobj.parent = self
            pageobj.tablbl = label

            # store away our handles to the page
            self.pages[name] = pageobj
            self.pages_w[child] = pageobj

            # select the new page
            self.select(name)

            return pageobj

        
    def addpage(self, name, title, klass, adjname=True):
        with self.lock:
            if self.pages.has_key(name):
                if not adjname:
                    raise Exception("A page with name '%s' already exists!" % name)
                newname = self.makename(name)
                if title == name:
                    title = newname
                name = newname

            # Make a frame for the notebook tab content
            child = gtk.VBox()

            # Create the new object in the frame
            try:
                pageobj = klass(child, name, title)

            except Exception, e:
                try:
                    (type, value, tb) = sys.exc_info()
                    print "Traceback:\n%s" % \
                                      "".join(traceback.format_tb(tb))
                    self.logger.debug("Traceback:\n%s" % \
                                      "".join(traceback.format_tb(tb)))
                    tb = None
                    raise e

                except Exception, e:
                    self.logger.debug("Traceback information unavailable.")
                    raise e

            child.set_data('ig_page', pageobj)
            child.show()

            self._addpage(name, title, child, pageobj)
            return pageobj


    def delpage(self, name):
        with self.lock:
            i = self.getIndexByName(name)
            self.widget.remove_page(i)

            try:
                del self.pages[name]
                del self.pages_w[name]
            except KeyError:
                pass

    def delall(self):
        with self.lock:
            for name in self.pages.keys():
                self.delpage(name)
            
    def select(self, name):
        i = self.getIndexByName(name)
        self.widget.set_current_page(i)

    def getNames(self):
        with self.lock:
            return self.pages.keys()

    def getPage(self, name):
        with self.lock:
            return self.pages[name]

    def getIndexByName(self, name):
        with self.lock:
            page = self.getPage(name)
            return self.widget.page_num(page.frame)
        
    def getPages(self):
        with self.lock:
            return self.pages.values()

       
    # DRAG AND DROP TABS
    def _page_added(self, nb, child, page_num):
        self.logger.info("page added %d" % page_num)
        with self.lock:
            if not self.pages_w.has_key(child):
                pageobj = child.get_data('ig_page')
                self.pages[pageobj.name] = pageobj
                self.pages_w[child] = pageobj
                
            return True

    def _page_removed(self, nb, child, page_num):
        self.logger.info("page removed %d" % page_num)
        with self.lock:
            try:
                pageobj = child.get_data('ig_page')
                del self.pages[pageobj.name]
                del self.pages_w[child]
            except KeyError:
                pass
            return True
    
    def _detach_page(self, source, widget, x, y):
        # Detach page to new top-level workspace
        page = self.widgetToPage(widget)
        if not page:
            return None
        
        self.logger.info("detaching page %s" % (page.name))
        ws = self.parent.add_detached_noname(x=x, y=y)
        return ws.widget



#END
