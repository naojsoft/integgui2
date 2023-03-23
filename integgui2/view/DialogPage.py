#
# DialogPage.py -- implements an Integgui2 dialog
#
# E. Jeschke
#

from gi.repository import Gtk

from . import common
from . import Page

from ginga.misc import Bunch

class DialogError(Exception):
    pass

class DialogPage(Page.Page):

    def __init__(self, frame, name, title):

        super(DialogPage, self).__init__(frame, name, title)

        scrolled_window = Gtk.ScrolledWindow()
        scrolled_window.set_border_width(2)

        scrolled_window.set_policy(Gtk.PolicyType.AUTOMATIC,
                                   Gtk.PolicyType.AUTOMATIC)

        vbox = Gtk.VBox()
        scrolled_window.add(vbox)
        vbox.show()
        scrolled_window.show()

        frame.pack_start(scrolled_window, True, True, 0)

        self.cvbox = Gtk.VBox()
        vbox.pack_start(self.cvbox, False, True, 0)
        self.cvbox.show()

        separator = Gtk.HSeparator()
        separator.show()
        vbox.pack_start(separator, False, True, 0)

        # bottom buttons
        btns = Gtk.HButtonBox()
        btns.set_layout(Gtk.ButtonBoxStyle.START)
        btns.set_spacing(5)
        self.leftbtns = btns

        vbox.pack_start(self.leftbtns, False, True, 4)
        btns.show()

    def get_content_area(self):
        return self.cvbox

    def add_button(self, name, rsp, callback):
        def _callback(w):
            return callback(self, rsp)
        btn = Gtk.Button(name)
        btn.connect("clicked", _callback)
        btn.show()
        self.leftbtns.pack_start(btn, False, False, 0)

    def add_buttons(self, buttonlist, callback):
        for name, rsp in buttonlist:
            self.add_button(name, rsp, callback)

    def destroy(self):
        # this method is here to make it similar to a widget based class
        return self.close()

    def show(self):
        pass

#END
