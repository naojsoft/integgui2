#
# E. Jeschke
#


from . import LogPage

class TagPage(LogPage.NotePage):

    def __init__(self, frame, name, title):
        super().__init__(frame, name, title)

        # clicking a line in the tag list jumps to the corresponding line
        # in the source OPE page
        self.tw.add_callback('line-clicked', self.jump_tag)
        # currently disable close button
        self.menu_close.set_enabled(False)

        self.tagidx = {}
        self.opepage = None

    def initialize(self, opepage):
        super().clear()

        self.tagidx = {}
        self.opepage = opepage

    def add_mapping(self, lineno, line, tags):
        # Append this line (with tags) to the tags buffer.  The line it
        # lands on is the current end line.
        taglineno = self.tw.get_end_lineno()
        self.tw.append_text(line + '\n', tags=tags, autoscroll=False)
        # make an entry in the tags index
        self.tagidx[taglineno] = lineno

    ## def scroll_to_lineno(self, lineno):
    ##     # Scroll tag table to errors
    ##     loc = self.buf.get_end_iter()
    ##     loc.set_line(lineno)
    ##     # HACK: I have to defer the scroll operation until the widget
    ##     # is rendered or it does not scroll
    ##     # UPDATE: this causes a crash
    ##     ## common.view.gui_do(self.tw.scroll_to_iter,
    ##     ##                     loc, 0, True)

    def jump_tag(self, w, taglineno):
        # Called on the widget's 'line-clicked' callback with the 0-based
        # line number that was clicked in the tag list.
        try:
            lineno = self.tagidx[taglineno]
        except KeyError:
            return False

        if not self.opepage:
            return True

        # TODO: raise self.opepage

        self.opepage.scroll_to_lineno(lineno)
        return True
