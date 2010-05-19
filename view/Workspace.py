# 
#[ Eric Jeschke (eric@naoj.org) --
#  Last edit: Tue May 18 15:42:42 HST 2010
#]

# remove once we're certified on python 2.6
from __future__ import with_statement

import sys
import threading
import traceback

import gtk

class Workspace(object):
    
    def __init__(self, frame, name, title):
        self.frame = frame
        self.name = name
        self.title = title

        self.widget = gtk.Notebook()
        self.widget.set_tab_pos(gtk.POS_TOP)
        self.widget.set_scrollable(True)
        self.widget.set_show_tabs(True)
        self.widget.set_show_border(True)
        self.widget.set_size_request(900, 500)
        self.widget.show()

        frame.pack_start(self.widget, expand=True, fill=True,
                         padding=2)

        # Holds my pages
        self.pages = {}
        self.pagelist = []
        self.lock = threading.RLock()


    def addpage(self, name, title, klass):
        with self.lock:
            try:
                pageobj = self.pages[name]
                raise Exception("A page with name '%s' already exists!" % name)

            except KeyError:
                pass

            # Make a frame for the notebook tab content
            pagefr = gtk.VBox()

            # Create the new object in the frame
            try:
                pageobj = klass(pagefr, name, title)

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

            pagefr.show()

            # Create a label for the notebook tab
            label = gtk.Label(title)
            label.show()

##             hb = gtk.HandleBox()
##             hb.set_shadow_type(gtk.SHADOW_ETCHED_IN)
##             hb.set_handle_position(gtk.POS_TOP)
##             hb.set_snap_edge(gtk.POS_TOP)
            
##             hb.add(pagefr)
##             hb.show()
            hb = pagefr
            
            # Add the page to the notebook
            self.widget.append_page(hb, label)
            
            # Some attributes we force on our children
            pageobj.logger = self.logger
            # ?? cyclical reference causes problems for gc?
            pageobj.parent = self

            # store away our handles to the page
            self.pages[name] = pageobj
            self.pagelist.append(name)

            # select the new page
            self.select(name)

            return pageobj

        
    def delpage(self, name):
        with self.lock:
            i = self.pagelist.index(name)
            self.widget.remove_page(i)

            del self.pages[name]
            self.pagelist.remove(name)
            

    def delall(self):
        with self.lock:
            for name in self.pages.keys():
                self.delpage(name)
            
    def select(self, name):
        i = self.pagelist.index(name)
        self.widget.set_current_page(i)

    def getNames(self):
        with self.lock:
            return self.pages.keys()

    def getPage(self, name):
        with self.lock:
            return self.pages[name]


#END
