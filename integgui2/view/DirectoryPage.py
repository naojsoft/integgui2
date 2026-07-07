#
# E. Jeschke
#
import sys
import glob
import os, re

from . import common
from . import LogPage


class DirectoryPage(LogPage.NotePage):

    def __init__(self, frame, name, title):
        super(DirectoryPage, self).__init__(frame, name, title)

        self.listing = []
        self.pattern = '*'
        self.clickfn = None

        self.cursor = 0
        self.moving_cursor = False

        self.tw.set_editable(False)

        # cursor-line tracking and keyboard shortcuts
        self.tw.add_callback('cursor_moved', self.show_cursor)
        self.tw.add_callback('key-press', self.keypress)

        # add standard decorative tags
        for tag, bnch in common.directory_tags:
            properties = {}
            properties.update(bnch)
            self.addtag(tag, **properties)

    def regist_clickfn(fn):
        """Register a function to be called on the files when you click them."""
        self.clickfn = fn

    def process_listing(self, listing):
        self.clear()
        for path in listing:
            dirname, filename = os.path.split(path)
            tags = ['normal']
            if os.path.isdir(path):
                filename += '/'
                tags = ['directory']
            elif os.path.islink(path):
                filename += '@'
                tags = ['link']
            else:
                #stat = os.stat(path)
                pass
            self.append(filename + '\n', tags)

    def listdir(self, dirpath, pattern):
        listing = glob.glob(os.path.join(dirpath, pattern))
        listing.append(os.path.join(dirpath, '..'))
        listing.sort()
        self.listing = listing
        self.process_listing(listing)

    def load(self, dirpath, pattern):
        self.listdir(dirpath, pattern)
        self.dirpath = dirpath
        self.pattern = pattern
        self._redraw()

    def reload(self):
        self.listdir(self.dirpath, self.pattern)
        self._redraw()


    def _redraw(self):
        # restore cursor and highlight its line
        self.cursor = min(self.cursor, self.tw.get_end_lineno())
        loc = self.tw.get_ref_line_start(self.cursor)
        self.moving_cursor = True
        try:
            self.tw.set_cursor(loc)
            self.tw.scroll_to_ref(loc)
            self._highlight_cursor_line(self.cursor)
        finally:
            self.moving_cursor = False

    def redraw(self):
        common.gui_do(self._redraw)

    def _highlight_cursor_line(self, line):
        """Move the 'cursor' highlight tag to the given line."""
        common.clear_tags(self.tw, ('cursor',))
        start = self.tw.get_ref_line_start(line)
        end = self.tw.get_ref_line_end(line)
        self.tw.apply_tag('cursor', start, end)

    def show_cursor(self, w):
        # Called on the widget's 'cursor_moved' callback; highlight the line
        # the cursor is on and remember it.
        if self.moving_cursor:
            return False

        self.moving_cursor = True
        try:
            line = self.tw.get_cursor().get_line()
            self.cursor = line
            self._highlight_cursor_line(line)
        finally:
            self.moving_cursor = False
        return True

    def process_entry(self, text, keyname):
        """Subclass should override this to do something interesting when
        a folder link is clicked."""
        self.logger.debug("text is %s, key is '%s'" % (text, keyname))
        path = os.path.abspath(text)

        if keyname == 'e':
            common.view.gui_do(common.view.load_file, path)
            return True

        if keyname == 'i':
            common.view.gui_do(common.view.load_inf, path)
            return True

        if keyname == 'f':
            common.view.gui_do(common.view.load_ephem, path)
            return True

        if keyname == 't':
            common.view.gui_do(common.view.load_tscTrack, path)
            return True

        if keyname == 'return':
            if os.path.isdir(path):
                self.load(path, self.pattern)
            else:
                common.view.gui_do(common.view.load_file, path)

        ## if (keyname == 'Return') and (self.clickfn):
        ##     common.controller.ctl_do(self.clickfn, text)

        return False


    def keypress(self, w, event):
        keyname = event.key
        if keyname in ('up', 'down', 'shift_l', 'shift_r',
                       'alt_l', 'alt_r', 'control_l', 'control_r'):
            # navigation and modifiers: let the widget handle them
            return False
        if keyname in ('left', 'right'):
            # ignore these
            return True
        #print("key pressed --> %s" % keyname)

        if 'ctrl' in event.modifiers:
            if keyname == 'r':
                self.reload()
                return True

            elif keyname == 'q':
                common.view.raise_queue()
                return True

            elif keyname == 'h':
                common.view.raise_handset()
                return True

        else:
            try:
                text = self.listing[self.cursor]
            except IndexError:
                return False

            return self.process_entry(text, keyname)

        return False


#END
