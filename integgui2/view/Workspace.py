#
# E. Jeschke
#
import sys
import threading
import traceback

from ginga.gw import Widgets

from . import common

# module-level var used for drag-and-drop of pages
drag_src = None


class Workspace:

    def __init__(self, frame, name, title):

        self.frame = frame
        self.name = name
        self.title = title

        # Holds my pages
        self.pages = {}
        self.pages_w = {}
        self.curpage = None

        # For handling dynamic pop-ups
        self.lastPage = None
        self.transients = []
        # Mutex
        self.lock = threading.RLock()

        nb = Widgets.TabWidget(tabpos='top', reorderable=True,
                               detachable=False, group=1)
        nb.add_callback("page-move", self._page_added)
        nb.add_callback("page-detach", self._page_removed)
        nb.add_callback("page-switch", self._page_switched)
        self.nb = nb
        frame.add_widget(self.nb, stretch=1)

    def build_tabmenu(self):
        tabmenu = Widgets.Menu()
        item = tabmenu.add_name("Nop")
        return tabmenu

    def set_tab_pos(self, pos):
        self.nb.set_tab_position(pos)

    def makename(self, name):
        with self.lock:
            if name not in self.pages:
                return name

            for i in range(2, 100000):
                possname = '%s(%d)' % (name, i)
                if possname not in self.pages:
                    return possname

            raise Exception("A page with name '%s' already exists!" % name)

    def _addpage(self, name, title, child, pageobj, adjname=True):
        with self.lock:
            if name in self.pages:
                if not adjname:
                    raise Exception("A page with name '%s' already exists!" % name)
                newname = self.makename(name)
                if title == name:
                    title = newname
                name = newname

            # workspace context menu
            # NOTE: currently seems to be masked by the workspace
            # context menu--never pops up
            #tabmenu = self.build_tabmenu()
            #label.connect("event", self.popup_menu, tabmenu)

            # Add the page to the notebook
            self.nb.add_widget(child, title=title)

            # Some attributes we force on our children
            pageobj.logger = self.logger
            # ?? cyclical reference causes problems for gc?
            pageobj.parent = self
            #pageobj.tabmenu = tabmenu
            pageobj.widget = child

            # store away our handles to the page
            self.pages[name] = pageobj
            self.pages_w[child] = pageobj

            # select the new page
            self.select(name)

            return pageobj

    def addpage(self, name, title, klass, adjname=True):
        with self.lock:
            if name in self.pages:
                if not adjname:
                    raise Exception("A page with name '%s' already exists!" % name)
                newname = self.makename(name)
                if title == name:
                    title = newname
                name = newname

            # Make a frame for the notebook tab content.  No inter-widget
            # spacing so the menubar sits flush against the page content
            # (pages that want an inset add their own).
            child = Widgets.VBox()
            child.set_spacing(0)

            # Create the new object in the frame
            try:
                pageobj = klass(child, name, title)

            except Exception as e:
                try:
                    (type, value, tb) = sys.exc_info()
                    print("Traceback:\n%s" %
                          "".join(traceback.format_tb(tb)))
                    self.logger.debug("Traceback:\n%s" %
                                      "".join(traceback.format_tb(tb)))
                    tb = None
                    raise e

                except Exception as e:
                    self.logger.debug("Traceback information unavailable.")
                    raise e

            child.ig_page = pageobj
            child.show()

            self._addpage(name, title, child, pageobj)
            return pageobj

    def delpage(self, name):
        with self.lock:
            i = self.getIndexByName(name)
            child = self.nb.index_to_widget(i)
            self.nb.remove(child)

            try:
                del self.pages[name]
                # this needs to index by widget
                #del self.pages_w[name]
            except KeyError:
                pass

    def delall(self):
        with self.lock:
            for name in self.pages.keys():
                self.delpage(name)

    def clear(self):
        return self.delall()

    def select(self, name):
        i = self.getIndexByName(name)
        self.nb.set_index(i)

    def getNames(self):
        with self.lock:
            return list(self.pages.keys())

    def getPage(self, name):
        with self.lock:
            return self.pages[name]

    def getCurrentPage(self):
        with self.lock:
            i = self.nb.get_index()
            if i < 0:
                return None
            child = self.nb.index_to_widget(i)
            return getattr(child, 'ig_page', None)

    def getIndexByName(self, name):
        with self.lock:
            page = self.getPage(name)
            return self.nb.index_of(page.frame)

    def showTransient(self, name):
        with self.lock:
            # Get currently selected page
            currentPage = self.getCurrentPage()

            # Add new page into a list of "transients" and
            # switch to it
            self.transients.insert(0, name)
            # "Remember" old current page if it was not in the list of
            # transients
            if (currentPage is not None) and (currentPage.name not in self.transients):
                self.lastPage = currentPage

            # Go to the new page
            self.select(name)

    def hideTransient(self, name):
        # A dialog is finished.  Pop the page off the list of "transients"
        # and go to the
        with self.lock:
            try:
                self.transients.remove(name)
            except BaseException:
                pass

            print("Transients: %s" % str(self.transients))
            if len(self.transients) == 0:
                if self.lastPage is not None:
                    print("Moving back to page: %s" % self.lastPage.name)
                    self.select(self.lastPage.name)

    def getPages(self):
        with self.lock:
            return list(self.pages.values())

    def close(self):
        def _close(res):
            if res == 'yes':
                return super().close()

        if len(self.pages) > 0:
            common.view.popup_confirm("Close Workspace",
                                      "Workspace '%s' has pages.  Really close?" % (
                                          self.name), _close)

    def move_page(self, page, workspace):
        self.logger.info("moving page '%s' to workspace '%s'" % (
            page.name, workspace.name))
        self.delpage(page.name)
        workspace._addpage(page.name, page.title, page.frame, page)

    def _page_switched(self, nb, child):
        with self.lock:
            page_num = nb.index_of(child)
            for page in self.getPages():
                if self.nb.index_of(page.frame) == page_num:
                    if page.name not in self.transients:
                        self.lastPage = page
                    break

    # DRAG AND DROP TABS

    def _page_added(self, nb, src_nb, child):
        page_num = self.nb.index_of(child)
        self.logger.debug("page added %d" % page_num)
        with self.lock:
            if child not in self.pages_w:
                pageobj = child.ig_page
                self.pages[pageobj.name] = pageobj
                self.pages_w[child] = pageobj
                pageobj.parent = self
                #self.nb.set_tab_label_text(child, pageobj.title)

            return True

    def _page_removed(self, nb, child):
        self.logger.debug("page removed %s" % str(child))
        with self.lock:
            try:
                pageobj = child.ig_page
                if self.lastPage == pageobj:
                    self.lastPage = None
                while pageobj.name in self.transients:
                    self.transients.remove(pageobj.name)
                del self.pages[pageobj.name]
                del self.pages_w[child]
            except Exception as e:
                self.logger.error('Error removing page: %s' % str(e))
            return True

    # def _detach_page(self, source, widget, x, y):
    #     # Detach page to new top-level workspace
    #     page = self.widgetToPage(widget)
    #     if not page:
    #         return None
    #     while page.name in self.transients:
    #         self.transients.remove(page.name)
    #     if self.lastPage == page:
    #         self.lastPage = None

    #     self.logger.info("detaching page %s" % (page.name))
    #     ws = self.parent.add_detached_noname(x=x, y=y)
    #     return ws.widget
