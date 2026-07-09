#
# DialogPage.py -- implements an Integgui2 dialog
#
# E. Jeschke
#

from . import common
from . import Page

from ginga.gw import Widgets
from ginga.misc import Bunch

class DialogError(Exception):
    pass

class DialogPage(Page.Page):

    def __init__(self, frame, name, title):

        super().__init__(frame, name, title)

        scrolled_window = Widgets.ScrollArea()

        vbox = Widgets.VBox()
        scrolled_window.set_widget(vbox)

        frame.add_widget(scrolled_window, stretch=1)

        # for the content (natural size, anchored at the top)
        self.cvbox = Widgets.VBox()
        vbox.add_widget(self.cvbox, stretch=0)

        #separator = Gtk.HSeparator()
        #vbox.pack_start(separator, False, True, 0)

        # buttons (a ButtonBox), sitting just below the content and ABOVE
        # the spacer
        btns = Widgets.ButtonBox()
        btns.set_spacing(5)
        self.leftbtns = btns
        vbox.add_widget(self.leftbtns, stretch=0)

        # A stretching spacer at the bottom so the content + buttons sit at
        # the top of the tab rather than filling it vertically.  This is
        # only added for the embedded (tab) dialog -- popup dialogs size to
        # their content and don't need it.
        vbox.add_widget(Widgets.Label(''), stretch=1)

    def get_content_area(self):
        return self.cvbox

    def add_button(self, name, rsp, callback):
        def _callback(w):
            return callback(self, rsp)
        btn = Widgets.Button(name)
        btn.add_callback("activated", _callback)
        self.leftbtns.add_widget(btn)

    def add_buttons(self, buttonlist, callback):
        for name, rsp in buttonlist:
            self.add_button(name, rsp, callback)

    def destroy(self):
        # this method is here to make it similar to a widget based class
        return self.close()

    def delete(self):
        # the dialog code closes via widget.delete(); for an embedded page
        # that means removing the tab (a fresh page is built each time)
        return self.close()

    def show(self):
        pass
