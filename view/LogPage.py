# 
#[ Eric Jeschke (eric@naoj.org) --
#  Last edit: Tue May 18 16:36:46 HST 2010
#]

import gtk
import gobject
import os.path

import Page


class LogPage(Page.ButtonPage):

    def __init__(self, frame, name, title):

        super(LogPage, self).__init__(frame, name, title)

        self.logsize = 5000

        scrolled_window = gtk.ScrolledWindow()
        scrolled_window.set_border_width(2)

        scrolled_window.set_policy(gtk.POLICY_AUTOMATIC,
                                   gtk.POLICY_AUTOMATIC)

        tw = gtk.TextView()
        scrolled_window.add(tw)
        tw.show()
        scrolled_window.show()

        frame.pack_start(scrolled_window, expand=True, fill=True)

        tw.set_editable(False)
        tw.set_wrap_mode(gtk.WRAP_NONE)
        tw.set_left_margin(4)
        tw.set_right_margin(4)

        self.tw = tw
        self.buf = tw.get_buffer()
        # hack to get auto-scrolling to work
        self.mark = self.buf.create_mark('end', self.buf.get_end_iter(),
                                         False)

        self.add_close()


    def load(self, filepath):
        self.filepath = filepath
        self.file = open(self.filepath, 'r')
        # Go to the end of the file
        try:
            self.file.seek(- self.logsize, 2)
        except:
            pass
        self.size = self.file.tell()
        self.poll()


    def close(self):
        try:
            self.file.close()
        except:
            pass

        super(LogPage, self).close()


    def poll(self):
        if self.closed:
            return

        #self.tw.scroll_mark_onscreen(self.mark)

        if os.path.getsize(self.filepath) > self.size:
            data = self.file.read()
            self.size = self.size + len(data)
            # TODO: mark error and warning lines

            loc = self.buf.get_end_iter()
            self.buf.insert(loc, data)

            # Remove some old log lines if necessary
            excess_lines = loc.get_line() - self.logsize
            if excess_lines > 0:
                bitr1 = self.buf.get_start_iter()
                bitr2 = bitr1.copy()
                bitr2.set_line(excess_lines)
                self.buf.delete(bitr1, bitr2)
                    
            loc = self.buf.get_end_iter()
            self.buf.move_mark(self.mark, loc)
            #self.tw.scroll_to_iter(loc, 0.0)
            #self.tw.scroll_mark_onscreen(self.mark)
            self.tw.scroll_to_mark(self.mark, 0.0)

        gobject.timeout_add(100, self.poll)


#END
