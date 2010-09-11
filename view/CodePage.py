# 
#[ Eric Jeschke (eric@naoj.org) --
#  Last edit: Fri Sep 10 15:28:34 HST 2010
#]
import os.path

import common
import Page

import gtk

class CodePage(Page.ButtonPage):

    def __init__(self, frame, name, title):

        super(CodePage, self).__init__(frame, name, title)

        self.hbox = gtk.HPaned()
        
        self.border = gtk.Frame("")
        self.border.set_shadow_type(gtk.SHADOW_ETCHED_OUT)
        self.border.set_label_align(0.1, 0.5)

        # Create the widgets for the OPE file text
        scrolled_window = gtk.ScrolledWindow()
        scrolled_window.set_border_width(2)

        scrolled_window.set_policy(gtk.POLICY_AUTOMATIC,
                                   gtk.POLICY_AUTOMATIC)

        tw = gtk.TextView()
        scrolled_window.add(tw)
        tw.show()
        scrolled_window.show()

        tw.set_editable(True)
        tw.set_wrap_mode(gtk.WRAP_NONE)
        tw.set_left_margin(4)
        tw.set_right_margin(4)

        self.tw = tw
        self.buf = tw.get_buffer()

        self.border.add(scrolled_window)
        self.border.show()

        self.hbox.pack2(self.border, resize=False, shrink=True)
        self.hbox.show()
        frame.pack_start(self.hbox, fill=True, expand=True)

        menu = self.add_pulldownmenu("Page")

        item = gtk.MenuItem(label="Reload")
        menu.append(item)
        item.connect_object ("activate", lambda w: self.reload(),
                             "menu.Reload")
        item.show()

        item = gtk.MenuItem(label="Save")
        menu.append(item)
        item.connect_object ("activate", lambda w: self.save(),
                             "menu.Save")
        item.show()

        #self.add_close()
        item = gtk.MenuItem(label="Close")
        menu.append(item)
        item.connect_object ("activate", lambda w: self.close(),
                             "menu.Close")
        item.show()


    def loadbuf(self, buftxt):

        # insert text
        tags = ['code']
        try:
            start, end = self.buf.get_bounds()
            self.buf.delete(start, end)
        except:
            pass

        # Create default 'code' tag
        try:
            self.buf.create_tag('code', foreground="black")
        except:
            # tag may be already created
            pass

        self.buf.insert_with_tags_by_name(start, buftxt, *tags)


    def load(self, filepath, buf):
        self.loadbuf(buf)
        self.filepath = filepath
        #lw = self.txt.component('label')
        #lw.config(text=filepath)
        self.border.set_label(filepath)

        self.buf.set_modified(False)

        
    def reload(self):
        try:
            in_f = open(self.filepath, 'r')
            buf = in_f.read()
            in_f.close()
        except IOError, e:
            # ? raise exception instead ?
            return common.view.popup_error("Cannot read '%s': %s" % (
                    self.filepath, str(e)))

        self.loadbuf(buf)


    def save(self):
        # TODO: make backup?

        dirname, filename = os.path.split(self.filepath)

        res = common.view.popup_yesno("Save file", 
                               'Really save "%s"?' % filename)
        if not res:
            return

        # get text to save
        start, end = self.buf.get_bounds()
        buf = self.buf.get_text(start, end)

        try:
            out_f = open(self.filepath, 'w')
            out_f.write(buf)
            out_f.close()
            #self.statusMsg("%s saved." % self.filepath)
        except IOError, e:
            return common.view.popup_error("Cannot write '%s': %s" % (
                    self.filepath, str(e)))

        self.buf.set_modified(False)

        
    def close(self):
        if self.buf.get_modified():
            res = common.view.popup_yesno("Close file", 
                                   "File is modified. Really close?")
            if not res:
                return

        super(CodePage, self).close()


#END
