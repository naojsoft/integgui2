import common

import Page

import gtk

class CodePage(Page.Page):

    def __init__(self, frame, name, title):

        super(CodePage, self).__init__(frame, name, title)

        self.border = gtk.Frame("")
        self.border.set_shadow_type(gtk.SHADOW_ETCHED_OUT)
        self.border.set_label_align(0.1, 0.5)
        
        scrolled_window = gtk.ScrolledWindow()
        scrolled_window.set_border_width(2)

        scrolled_window.set_policy(gtk.POLICY_AUTOMATIC,
                                   gtk.POLICY_AUTOMATIC)

        tw = gtk.TextView()
        scrolled_window.add_with_viewport(tw)
        tw.show()
        scrolled_window.show()

        tw.set_editable(True)
        tw.set_wrap_mode(gtk.WRAP_NONE)
        tw.set_left_margin(4)
        tw.set_right_margin(4)

        self.border.add(scrolled_window)
        frame.pack_start(self.border, expand=True, fill=True)
        self.border.show()

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

        self.btn_reload = gtk.Button("Reload")
        self.btn_reload.connect("clicked", lambda w: self.reload())
        self.btn_reload.show()
        btns.pack_end(self.btn_reload, padding=4)

        self.btn_save = gtk.Button("Save")
        self.btn_save.connect("clicked", lambda w: self.save())
        self.btn_save.show()
        btns.pack_end(self.btn_save, padding=4)

        btns.show()

        frame.pack_end(btns, fill=False, expand=False, padding=2)


    def loadbuf(self, buf):

        # insert text
        tags = ['code']
        try:
            start, end = self.buf.get_bounds()
            tw.delete(start, end)
        except:
            pass

        # Create default 'code' tag
        try:
            self.buf.create_tag('code', foreground="black")
        except:
            # tag may be already created
            pass

        self.buf.insert_with_tags_by_name(start, buf, *tags)


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
            return common.view.popup_error("Cannot write '%s': %s" % (
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
