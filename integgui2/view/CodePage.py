#
# E. Jeschke
#
import os.path
import string

from ginga.gw import Widgets

from . import common
from . import Page
from . import dialogs
from .TextSource import TextSource

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
        tw = TextSource(wrap=False, editable=True)
        # TODO
        #tw.set_left_margin(4)
        #tw.set_right_margin(4)

        tw.set_font('DejaVu Sans Mono', 10)
        self.tw = tw

        self.sr = dialogs.SearchReplace("Find and/or Replace")
        # Offset in the buffer from which the next find continues.  Replaces
        # the old GTK "searchmark".
        self._search_offset = 0

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

    def build_dialog(self, title, text, buttons, callback):
        """Build a standard warning MessageDialog with the given
        ``(name, value)`` buttons.  ``callback(dialog, value)`` is invoked on
        a button press (or window close); the dialog is dismissed first.
        """
        dialog = Widgets.MessageDialog(title=title, modal=False,
                                       parent=common.view.w.root,
                                       buttons=buttons, autoclose=False)
        dialog.set_message('warning', text)

        def _dismiss(w):
            common.view.remove_window(w)
            w.delete()

        def _activated(w, val):
            _dismiss(w)
            return callback(w, val)

        dialog.add_callback('activated', _activated)
        dialog.add_callback('close', _dismiss)
        common.view.add_window(dialog)
        return dialog

    def close(self):
        if self.tw.get_modified():
            self.build_dialog("Close file", warning_close,
                              [("Cancel", 1), ("Close", 2),
                               ("Save and Close", 3)],
                              self._close_check_res).show()
            return False

        super(CodePage, self).close()
        return True

    def _close_check_res(self, w, rsp):
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
            if not self.tw.has_selection():
                # No selection.
                dialog.set_message("NO SELECTION")
                return True

            bounds = self.tw.get_selection_bounds()
            if bounds is None:
                dialog.set_message("ERROR SELECTION?")
                return True
            start, end = bounds

            # TODO: how to force increments of undoable actions?
            self.tw.delete_range(start, end)
            self.tw.insert_text(start, dialog.get_replace_text())

            # Clear the selection
            common.clear_selection(self.tw)

            return True

        # response == 'find'
        query = dialog.get_search_text()
        if not query:
            dialog.set_message("PLEASE ENTER SEARCH TEXT")
            return True

        reverse = dialog.is_reverse_search()
        # The "Case sensitive" checkbox drives case sensitivity directly.
        case_insensitive = not dialog.is_case_sensitive()

        # Collect all matches once; direction and wrap-around are chosen
        # relative to the running search offset.  (The unified text widget
        # has no native reverse search, so we drive it from find_all.)
        matches = self.tw.find_all(query, case_insensitive=case_insensitive)
        if not matches:
            dialog.set_message("NO INSTANCES FOUND")
            return True

        pos = self._search_offset
        spans = [(s.get_offset(), e.get_offset(), s, e) for (s, e) in matches]

        if reverse:
            # last match ending at or before the current position, else wrap
            candidates = [t for t in spans if t[1] <= pos]
            chosen = candidates[-1] if candidates else spans[-1]
        else:
            # first match starting at or after the current position, else wrap
            candidates = [t for t in spans if t[0] >= pos]
            chosen = candidates[0] if candidates else spans[0]

        start_off, end_off, start_ref, end_ref = chosen
        self.tw.set_selection_range(start_ref, end_ref)
        self.scroll_to_lineno(start_ref.get_line())
        # Advance the search position so the next find moves on.
        self._search_offset = start_off if reverse else end_off
        dialog.set_message("Found in line %d" % (start_ref.get_line() + 1))
        return True

    def find(self):
        self._search_offset = self.tw.get_cursor().get_offset()
        self.sr.popup(self._find)
