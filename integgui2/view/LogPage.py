#
# E. Jeschke
#
import time
import threading

from ginga.gw import Widgets

import os.path

from . import common
from . import Page
from . import Widgets as IGWidgets


class NotePage(Page.ButtonPage, Page.TextPage):

    def __init__(self, frame, name, title):
        super(NotePage, self).__init__(frame, name, title)

        # How many lines should we keep in this buffer beyond which
        # we cull from the top.  A value of 0 disables auto-culling.
        self.logsize = 0

        # Whether to automatically scroll the text widget when data
        # is appended to the bottom of the buffer programatically.
        self.autoscroll = True

        self.lock = threading.RLock()

        tw = IGWidgets.TextSource()
        self.tw = tw

        self.content.add_widget(tw, stretch=1)

        tw.set_editable(False)
        tw.set_wrap(False)
        # TODO: set margins
        #tw.set_border_width(4)

        menu = self.add_pulldownmenu("Page")

        item = menu.add_name("Save as ...")
        item.add_callback("activated", lambda w: self.save_log_as())

        item = menu.add_name("Save selection as ...")
        item.add_callback("activated", lambda w: self.save_log_selection_as())

        item = menu.add_name("Close")
        item.add_callback("activated", lambda w: self.close())
        self.menu_close = item


    def set_editable(self, value):
        self.tw.set_editable(value)

    def set_logsize(self, size):
        """(size) should be an integer value indicating number of
        lines.  Setting to 0 will disable any culling of old lines.
        """
        self.logsize = size

    def set_autoscroll(self, onoff):
        self.autoscroll = onoff

    def addtag(self, name, **properties):
        try:
            self.tw.create_tag(name, **properties)
        except:
            # tag may already exist--that's ok
            pass

    def clear(self):
        start, end = self.tw.get_ref_bounds()
        self.tw.delete_range(start, end)

    def _cull(self):
        if self.logsize:
            end = self.tw.get_ref_end()
            excess_lines = end.get_line() - self.logsize
            if excess_lines > 0:
                bitr1 = self.tw.get_ref_start()
                bitr2 = bitr1.copy()
                bitr2.set_line(excess_lines)
                self.tw.delete_range(bitr1, bitr2)

    def append(self, data, tags):
        end = self.tw.get_ref_end()
        if not tags:
            tags = ['normal']

        try:
            self.tw.insert_text(end, data, tags=tags)

        except Exception as e:
            tags = ['error']
            data = "--DATA COULD NOT BE INSERTED--: %s" % (str(e))
            self.tw.insert_text(end, data, tags=tags)

        # Remove some old log lines if necessary
        self._cull()

        # Auto scroll to end of buffer
        if self.autoscroll:
            end = self.tw.get_ref_end()
            self.tw.scroll_to_ref(end)

    def save_log_as(self):
        homedir = os.path.join(os.environ['HOME'], 'Procedure')
        filename = time.strftime("%Y%m%d-%H:%M:%S") + (
            '-%s.txt' % self.name)

        common.view.popup_save("Save buffer", self._savefile,
                               homedir, filename=filename)

    def save_log_selection_as(self):
        homedir = os.path.join(os.environ['HOME'], 'Procedure')
        filename = time.strftime("%Y%m%d-%H:%M:%S") + (
            '-%s.txt' % self.name)
        return self.save_selection_as(homedir, filename)


class LogPage(NotePage):

    def __init__(self, frame, name, title):
        super(LogPage, self).__init__(frame, name, title)

        # interval between checking for log file updates (ms)
        self.poll_interval = 500

        self.set_logsize(5000)

        # add standard decorative tags
        for tag, bnch in common.log_tags:
            properties = {}
            properties.update(bnch)
            self.addtag(tag, **properties)

        # This is a table of regex, tag tuples used to do
        # auto coloring of log entries
        self.regexes = []


    def clear_regexes(self):
        self.regexes = []

    def add_regex(self, regex, tags):
        self.regexes.append((regex, tags))

    def add_regexes(self, tuples):
        for tup in tuples:
            self.add_regex(*tup)

    def load(self, filepath):
        self.filepath = filepath
        self.file = open(self.filepath, 'r')
        # Go to the end of the file
        if self.logsize:
            try:
                self.file.seek(- self.logsize, 2)
            except:
                pass
            self.size = self.file.tell()
        else:
            self.size = 0
        self.poll()

    def close(self):
        try:
            self.file.close()
        except:
            pass

        super(LogPage, self).close()

    def push(self, msgstr):
        line = msgstr + '\n'

        # set tags according to content of message
        for (regex, tags) in self.regexes:
            if regex.match(msgstr):
                self.append(line, tags)
                return

        self.append(line, [])


    def poll(self):
        if self.closed:
            return

        #self.tw.scroll_mark_onscreen(self.mark)

        #if os.path.getsize(self.filepath) > self.size:
        try:
            data = self.file.read()
            self.size = self.size + len(data)

            if len(data) > 0:
                with self.lock:
                    for line in data.split('\n'):
                        self.push(line)

        except IOError as e:
            pass

        #GObject.timeout_add(self.poll_interval, self.poll)


class MonLogPage(LogPage):

    def add2log(self, logdict):
        #self.tw.scroll_mark_onscreen(self.mark)

        data = logdict['msgstr']

        if len(data) > 0:
            with self.lock:
                for line in data.split('\n'):
                    if len(line) > 0:
                        self.push(line)
