import gtk
import gobject
import os.path

import Page


class LogPage(Page.Page):

    def __init__(self, frame, name, title):

        super(LogPage, self).__init__(frame, name, title)

        self.logsize = 5000

        scrolled_window = gtk.ScrolledWindow()
        scrolled_window.set_border_width(2)

        scrolled_window.set_policy(gtk.POLICY_AUTOMATIC,
                                   gtk.POLICY_AUTOMATIC)

        tw = gtk.TextView()
        scrolled_window.add_with_viewport(tw)
        tw.show()
        scrolled_window.show()

        frame.pack_start(scrolled_window, expand=True, fill=True)

        tw.set_editable(False)
        tw.set_wrap_mode(gtk.WRAP_NONE)
        tw.set_left_margin(4)
        tw.set_right_margin(4)

        self.tw = tw
        self.buf = tw.get_buffer()

        # bottom buttons
        btns = gtk.HButtonBox()
        btns.set_layout(gtk.BUTTONBOX_START)
        btns.set_spacing(5)
        self.btns = btns

        self.btn_close = gtk.Button("Close")
        self.btn_close.connect("clicked", lambda w: self.close())
        self.btn_close.show()
        btns.pack_end(self.btn_close, padding=4)

        frame.pack_end(btns, fill=False, expand=False, padding=2)


    def load(self, filepath):
        self.filepath = filepath
        self.file = open(self.filepath, 'r')
        # Go to the end of the file
        self.file.seek(0, 2)
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
                    
            self.tw.scroll_to_iter(loc, 0.1)

        gobject.timeout_add(100, self.poll)


#END
