#
# E. Jeschke
#
import os.path
import string

from ginga.gw import Widgets

from . import common
from . import Page
from . import dialogs
from . import Widgets as IGWidgets

warning_close = """
WARNING: Buffer is modified

Please choose one of the following options:

1) Don't close page.
2) Close without saving.
3) Save buffer and close page.

"""

class CodePage(Page.ButtonPage, Page.TextPage):

    def __init__(self, frame, name, title):

        super().__init__(frame, name, title)

        # Path of the file loaded into this buffer
        self.filepath = ''

        # Used to strip out bogus characters from buffers
        acceptchars = set(string.printable.encode('iso-8859-1'))
        self.deletechars = (''.join([chr(c)
                                     for c in set(bytes.maketrans(b'', b'')) -
                                     acceptchars])).encode('iso-8859-1')
        self.transtbl = bytes.maketrans(b'\r', b' ')

        self.border = Widgets.Frame(title='')
        w = self.border.get_widget()
        # TODO
        #w.set_shadow_type(Gtk.ShadowType.ETCHED_OUT)
        #w.set_label_align(0.1, 0.5)

        # Create the widgets for the code file text
        tw = IGWidgets.NumberedTextArea(wrap=False, editable=True)
        # TODO
        #tw.set_left_margin(4)
        #tw.set_right_margin(4)

        tw.set_font('DejaVuSans', 10)
        self.tw = tw

        self.sr = dialogs.SearchReplace("Find and/or Replace")
        #self.buf.connect('mark-set', self.place_cursor_cb)

        self.border.set_widget(tw)

        self.content.add_widget(self.border, stretch=1)

        menu = self.add_pulldownmenu("Page")

        item = menu.add_name("Reload")
        item.add_callback("activated", lambda w: self.reload())

        item = menu.add_name("Save")
        item.add_callback("activated", lambda w: self.save())

        item = menu.add_name("Save as ...")
        item.add_callback("activated", lambda w: self.save_as())

        item = menu.add_name("Save selection as ...")
        item.add_callback("activated", lambda w: self.save_selection_as())

        #self.add_close()
        item = menu.add_name("Close")
        item.add_callback("activated", lambda w: self.close())

        menu = self.add_pulldownmenu("Buffer")

        item = menu.add_name("Find/Replace ...")
        item.add_callback("activated", lambda w: self.find())

        item = menu.add_name("Wrap lines", checkable=True)
        wrap_lines = False
        item.set_state(wrap_lines)
        item.add_callback("activated", self.toggle_line_wrapping)

        item = menu.add_name("Show line numbers", checkable=True)
        number_lines = False
        item.set_state(number_lines)
        item.add_callback("activated", self.toggle_line_numbering)

        # item = menu.add_name("Print ...")
        # item.add_callback("activated", lambda w: self.print_cb())


    def loadbuf(self, buftxt):

        # "cleanse" text--delete invisible chars that are sometimes
        # mistakenly inserted by users
        res = []
        lines = buftxt.split('\n')
        for line in lines:
            # Lines beginning with a comment character (#) are left as is
            if line.strip().startswith('#'):
                res.append(line)
                continue

            # Other lines are considered "code": we remove all characters
            # except ASCII printable ones
            btxt = line.encode('utf-8')
            btxt = btxt.translate(self.transtbl, self.deletechars)
            # translate tabs to 8 spaces
            btxt = btxt.replace(b'\t', b' ' * 8)
            line = btxt.decode()

            res.append(line)

        buftxt = '\n'.join(res)
        res = []

        # insert text
        self.tw.set_text(buftxt)
        self.tw.set_scroll_pos(0)

    def load(self, filepath, buf):
        self.loadbuf(buf)
        self.filepath = filepath
        self.border.set_text(filepath)

        # TODO: set syntax highlighter based on file extension?

    def reload(self):
        try:
            with open(self.filepath, 'r', newline=None) as in_f:
                buf = in_f.read()
        except IOError as e:
            # ? raise exception instead ?
            return common.view.popup_error("Cannot read '%s': %s" % (
                    self.filepath, str(e)))

        self.loadbuf(buf)

    def _do_save(self):
            # TODO: make backup?

            # get text to save
            buf = self.tw.get_text()

            try:
                with open(self.filepath, 'w') as out_f:
                    out_f.write(buf)
                #self.statusMsg("%s saved." % self.filepath)
            except IOError as e:
                return common.view.popup_error("Cannot write '%s': %s" % (
                        self.filepath, str(e)))

    def save(self):
        def _save(res):
            if res != 'yes':
                return
            self._do_save()

        dirname, filename = os.path.split(self.filepath)
        common.view.popup_confirm("Save file",
                                  'Really save "%s"?' % filename,
                                  _save)

    def build_dialog(self, title, text, buttons=[("Dismiss", 0)]):
        dialog = Widgets.Dialog(title=title,
                                buttons=buttons)
        vbox = warn.get_content_area()
        vbox.set_margins(4, 4, 4, 4)
        lbl = Widgets.Label(text)
        vbox.add_widget(lbl, stretch=1)
        return dialog

    def close(self):
        if self.tw.get_modified():
            w = self.build_dialog("Close file", warning_close,
                                  buttons=[("Cancel", 1), ("Close", 2),
                                           ("Save and Close", 3)])
            w.add_callback('activated', _close_check_res)
            w.add_callback('close', _close_check_res, 1)
            self.add_window(w)
            w.show()
            return False

        super(CodePage, self).close()
        return True

    def _close_check_res(self, w, rsp):
        self.remove_window(w)
        w.destroy()
        if rsp == 2:
            super(CodePage, self).close()

        elif rsp == 3:
            self._do_save()
            super(CodePage, self).close()

        return True

    def get_filepath(self):
        return self.filepath

    def line_numbering(self, onoff):
        self.tw.show_line_numbers(onoff)

    def toggle_line_numbering(self, widget, tf):
        self.line_numbering(tf)
        return True

    def toggle_line_wrapping(self, widget, tf):
        self.tw.set_wrap(tf)
        return True

    ##### Find and Replace callbacks

    def _find(self, response):
        dialog = self.sr

        if response == 'close':
            common.clear_selection(self.tw)
            return True

        if response == 'replace':
            if not self.buf.get_has_selection():
                # No selection.
                dialog.set_message("NO SELECTION")
                return True

            try:
                start, end = self.buf.get_selection_bounds()
            except ValueError:
                dialog.set_message("ERROR SELECTION?")
                return True

            # TODO: how to force increments of undoable actions?
            self.buf.delete(start, end)
            self.buf.insert(start, dialog.get_replace_text())

            # Clear the selection
            common.clear_selection(self.tw)

            return True

        reverse = dialog.is_reverse_search()
        if dialog.is_case_sensitive():
            search_flags = Gtk.TextSearchFlags.CASE_INSENSITIVE
        else:
            search_flags = 0

        i = self.buf.get_iter_at_mark(self.searchmark)
        if i == None:
            dialog.set_message("PLEASE PLACE CURSOR")
            return
        dialog.set_message("Search begins in line %d" % (
            i.get_line()))

        if reverse:
            searched = i.backward_search(dialog.get_search_text(),
                                        search_flags, None)
        else:
            searched = i.forward_search(dialog.get_search_text(),
                                        search_flags, None)
        if searched:
            dialog.set_message("Found string")
            start, end = searched
            self.buf.select_range(start, end)
            self.scroll_to_lineno(start.get_line())
            if reverse:
                self.buf.move_mark(self.searchmark, start)
            else:
                self.buf.move_mark(self.searchmark, end)

        else:
            end = i
            if reverse:
                i = self.buf.get_end_iter()
                searched = i.backward_search(dialog.get_search_text(),
                                            search_flags, end)
            else:
                i = self.buf.get_start_iter()
                searched = i.forward_search(dialog.get_search_text(),
                                            search_flags, end)
            if searched:
                dialog.set_message("Found string")
                start, end = searched
                self.buf.select_range(start, end)
                self.scroll_to_lineno(start.get_line())
                if reverse:
                    self.buf.move_mark(self.searchmark, start)
                else:
                    self.buf.move_mark(self.searchmark, end)

            else:
                dialog.set_message("NO MORE INSTANCES FOUND")

    def find(self):
        loc = self.buf.get_iter_at_mark(self.buf.get_insert())
        if not loc:
            loc = self.buf.get_start_iter()
        self.buf.move_mark(self.searchmark, loc)

        self.sr.popup(self._find)

    def place_cursor_cb(self, buf, loc, mark):
        if mark == buf.get_insert():
            self.buf.move_mark(self.searchmark, loc)
        return False
