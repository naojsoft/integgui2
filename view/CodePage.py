# 
#[ Eric Jeschke (eric@naoj.org) --
#  Last edit: Wed Feb 23 11:02:28 HST 2011
#]
import os.path
import string

import common
import Page

import gtk
import gtksourceview2

class CodePage(Page.ButtonPage, Page.TextPage):

    def __init__(self, frame, name, title):

        super(CodePage, self).__init__(frame, name, title)

        # Path of the file loaded into this buffer
        self.filepath = ''
        
        # Used to strip out bogus characters from buffers
        acceptchars = set(string.printable)
        self.deletechars = ''.join(set(string.maketrans('', '')) -
                                   acceptchars)
        self.transtbl = string.maketrans('\r', '\n')

        self.border = gtk.Frame("")
        self.border.set_shadow_type(gtk.SHADOW_ETCHED_OUT)
        self.border.set_label_align(0.1, 0.5)

        # Create the widgets for the OPE file text
        scrolled_window = gtk.ScrolledWindow()
        scrolled_window.set_border_width(2)

        scrolled_window.set_policy(gtk.POLICY_AUTOMATIC,
                                   gtk.POLICY_AUTOMATIC)

        # create buffer
        lm = gtksourceview2.LanguageManager()
        self.buf = gtksourceview2.Buffer()
        self.buf.set_data('languages-manager', lm)

        tw = gtksourceview2.View(self.buf)
        scrolled_window.add(tw)
        tw.show()
        scrolled_window.show()

        tw.set_editable(True)
        tw.set_wrap_mode(gtk.WRAP_NONE)
        tw.set_left_margin(4)
        tw.set_right_margin(4)

        self.tw = tw

        self.border.add(scrolled_window)
        self.border.show()

        frame.pack_start(self.border, fill=True, expand=True)

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

        item = gtk.MenuItem(label="Save as ...")
        menu.append(item)
        item.connect_object ("activate", lambda w: self.save_as(),
                             "menu.Save_As")
        item.show()

        item = gtk.MenuItem(label="Save selection as ...")
        menu.append(item)
        item.connect_object ("activate", lambda w: self.save_selection_as(),
                             "menu.Save_As")
        item.show()

        #self.add_close()
        item = gtk.MenuItem(label="Close")
        menu.append(item)
        item.connect_object ("activate", lambda w: self.close(),
                             "menu.Close")
        item.show()


    def loadbuf(self, buftxt):

        # "cleanse" text--change CR to NL, delete unprintable chars
        # TODO: what about unicode?
        buftxt = buftxt.translate(self.transtbl, self.deletechars)
        # translate tabs
        buftxt = buftxt.replace('\t', '        ')

        self.buf.begin_not_undoable_action()

        # insert text
        #tags = ['code']
        tags = []
        try:
            start, end = self.buf.get_bounds()
            self.buf.remove_source_marks(start, end)
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
        self.buf.set_modified(False)

        self.buf.end_not_undoable_action()


    def load(self, filepath, buf):
        self.loadbuf(buf)
        self.filepath = filepath
        #lw = self.txt.component('label')
        #lw.config(text=filepath)
        self.border.set_label(filepath)

        manager = self.buf.get_data('languages-manager')
        language = manager.guess_language(filepath)
        if language:
            self.buf.set_highlight_syntax(True)
            self.buf.set_language(language)
        else:
            self.logger.info('No language found for file "%s"' % filepath)
            self.buf.set_highlight_syntax(False)

        #self.buf.set_modified(False)

        
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
        def _save(res):
            if res != 'yes':
                return

            # TODO: make backup?

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

        dirname, filename = os.path.split(self.filepath)
        common.view.popup_confirm("Save file", 
                                  'Really save "%s"?' % filename,
                                  _save)

        
    def close(self):
        def _close(res):
            if res != 'yes':
                return

            super(CodePage, self).close()
            
        if self.buf.get_modified():
            common.view.popup_confirm("Close file", 
                                      "File is modified. Really close?",
                                      _close)
        else:
            _close('yes')

    def get_filepath(self):
        return self.filepath

#END
