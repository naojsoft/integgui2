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

        super(DialogPage, self).__init__(frame, name, title)

        scrolled_window = Widgets.ScrollArea()

        vbox = Widgets.VBox()
        scrolled_window.set_widget(vbox)

        frame.add_widget(scrolled_window, stretch=1)

        # for the content
        self.cvbox = Widgets.VBox()
        vbox.add_widget(self.cvbox, stretch=1)

        #separator = Gtk.HSeparator()
        #vbox.pack_start(separator, False, True, 0)

        # bottom buttons
        btns = Widgets.ButtonBox()
        btns.set_spacing(5)
        self.leftbtns = btns

        vbox.add_callback(self.leftbtns, stretch=0)

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

    def show(self):
        pass
