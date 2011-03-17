# 
#[ Eric Jeschke (eric@naoj.org) --
#  Last edit: Mon Feb 28 11:14:46 HST 2011
#]

# remove once we're certified on python 2.6
from __future__ import with_statement

import sys
import threading
import traceback

import gtk

import common

# module-level var used for drag-and-drop of pages
drag_src = None


class Workspace(object):
    
    def __init__(self, frame, name, title):

        self.frame = frame
        self.name = name
        self.title = title

        # Holds my pages
        self.pages = {}
        self.pages_w = {}

        # For handling dynamic pop-ups
        self.stack = []
        self.transients = []
        self.fn_close = None
        # Mutex
        self.lock = threading.RLock()

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
        nb.connect("switch-page", self._page_switched)
        # Allows dragging pages to create top-level detached workspaces
        #nb.connect("create-window", self._detach_page)

        # workspace context menu
        #nb.popup_enable()
        self.wsmenu = self.build_menu()
        nb.connect("event", self.popup_menu, self.wsmenu)

        nb.show()

        self.nb = nb
        frame.pack_start(self.nb, expand=True, fill=True,
                         padding=2)


    def popup_menu(self, w, event, menu):
        if (event.type == gtk.gdk.BUTTON_PRESS) and \
               (event.button == 3):
            menu.popup(None, None, None, event.button, event.time)
            return True
        return False
    
    def build_menu(self):
        wsmenu = gtk.Menu()

        tpmenu = gtk.Menu()
        item = gtk.MenuItem(label="Tab position")
        wsmenu.append(item)
        item.show()
        item.set_submenu(tpmenu)

        item = gtk.MenuItem(label="Top")
        tpmenu.append(item)
        item.connect_object("activate", lambda w: self.set_tab_pos(gtk.POS_TOP),
                            "pos.Top")
        item.show()

        item = gtk.MenuItem(label="Left")
        tpmenu.append(item)
        item.connect_object("activate", lambda w: self.set_tab_pos(gtk.POS_LEFT),
                            "pos.Left")
        item.show()

        item = gtk.MenuItem(label="Bottom")
        tpmenu.append(item)
        item.connect_object("activate", lambda w: self.set_tab_pos(gtk.POS_BOTTOM),
                            "pos.Bottom")
        item.show()

        item = gtk.MenuItem(label="Right")
        tpmenu.append(item)
        item.connect_object("activate", lambda w: self.set_tab_pos(gtk.POS_RIGHT),
                            "pos.Right")
        item.show()

        item = gtk.MenuItem(label="Close")
        wsmenu.append(item)
        item.connect_object("activate", lambda w: self.close(),
                            "close")
        # currently disabled
        item.set_sensitive(False)
        item.show()
        self.menu_close = item

        return wsmenu


    def build_tabmenu(self):
        tabmenu = gtk.Menu()
        item = gtk.MenuItem(label="Nop")
        tabmenu.append(item)
        item.show()

        return tabmenu


    def set_tab_pos(self, pos):
        self.nb.set_tab_pos(pos)
        
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

            # workspace context menu
            # NOTE: currently seems to be masked by the workspace
            # context menu--never pops up
            tabmenu = self.build_tabmenu()
            label.connect("event", self.popup_menu, tabmenu)

            # Add the page to the notebook
            self.nb.append_page(child, label)

            self.nb.set_tab_reorderable(child, True)
            self.nb.set_tab_detachable(child, True)
            
            # Some attributes we force on our children
            pageobj.logger = self.logger
            # ?? cyclical reference causes problems for gc?
            pageobj.parent = self
            pageobj.tablbl = label
            pageobj.tabmenu = tabmenu

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
            self.nb.remove_page(i)

            try:
                del self.pages[name]
                # this needs to index by widget
                #del self.pages_w[name]
            except KeyError:
                pass
            # Remove from stack if stacked
            try:
                self.stack.remove(name)
            except:
                pass

    def delall(self):
        with self.lock:
            for name in self.pages.keys():
                self.delpage(name)
            
    def select(self, name):
        i = self.getIndexByName(name)
        self.nb.set_current_page(i)

    def getNames(self):
        with self.lock:
            return self.pages.keys()

    def getPage(self, name):
        with self.lock:
            return self.pages[name]

    def getCurrentPage(self):
        with self.lock:
            i = self.nb.get_current_page()
            for page in self.getPages():
                if self.nb.page_num(page.frame) == i:
                    return page

            # ???
            return None

    def getIndexByName(self, name):
        with self.lock:
            page = self.getPage(name)
            return self.nb.page_num(page.frame)
        
    def pushRaise(self, name, fn_open=None, fn_close=None):
        # If a function was provided to 
        if fn_open:
            fn_open()
            self.fn_close = fn_close
            
        with self.lock:
            # Push current top page onto stack
            currentPage = self.getCurrentPage()
            if currentPage:
                self.stack.insert(0, currentPage.name)

            # Add this page into a list of "transients" and
            # switch to it
            self.transients.insert(0, name)
            self.select(name)
            
    def popRaise(self):
        # A dialog is finished.  Pop the page off the list of "transients"
        # and go to the 
        with self.lock:
            try:
                self.transients.pop(0)
            except:
                pass

            if len(self.stack) > 0:
                name = self.stack.pop(0)
                self.select(name)

            if (len(self.stack) == 0) and (self.fn_close != None):
                self.fn_close()
            
    def getPages(self):
        with self.lock:
            return self.pages.values()

    def close(self):
        def _close(res):
            if res == 'yes':
                return super(Workspace, self).close()
        
        if len(self.pages) > 0:
            common.view.popup_confirm("Close Workspace",
                                      "Workspace '%s' has pages.  Really close?" % (
                self.name), _close)

    def move_page(self, page, workspace):
        self.logger.info("moving page '%s' to workspace '%s'" % (
            page.name, workspace.name))
        self.delpage(page.name)
        workspace._addpage(page.name, page.title, page.frame, page)
        

    def _page_switched(self, nb, child, page_num):
        with self.lock:
            if len(self.stack) <= 0:
                return True
            
            for page in self.getPages():
                if self.nb.page_num(page.frame) == page_num:
                    if not page.name in self.transients:
                        self.stack[0] = page.name
                    break
                    

    # DRAG AND DROP TABS
    def _page_added(self, nb, child, page_num):
        self.logger.debug("page added %d" % page_num)
        with self.lock:
            if not self.pages_w.has_key(child):
                pageobj = child.get_data('ig_page')
                self.pages[pageobj.name] = pageobj
                self.pages_w[child] = pageobj
                pageobj.parent = self
                #self.nb.set_tab_label_text(child, pageobj.title)
                
            return True

    def _page_removed(self, nb, child, page_num):
        self.logger.debug("page removed %d" % page_num)
        with self.lock:
            try:
                pageobj = child.get_data('ig_page')
                del self.pages[pageobj.name]
                del self.pages_w[child]
                try:
                    self.stack.remove(pageobj.name)
                except:
                    pass
            except Exception, e:
                self.logger.error('Error removing page: %s' % str(e))
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
