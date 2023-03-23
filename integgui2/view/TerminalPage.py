#
# E. Jeschke
#

import os

import gi
from gi.repository import Gtk
from gi.repository import GLib
gi.require_version('Vte', '2.91')
from gi.repository import Vte

from . import common
from . import Page


class TerminalPage(Page.ButtonPage):

    def __init__(self, frame, name, title):

        super(TerminalPage, self).__init__(frame, name, title)

        tw = Vte.Terminal()
        #tw.set_color_foreground(common.terminal_colors.fg)
        #tw.set_color_background(common.terminal_colors.bg)

        tw.connect("child-exited", lambda w: self.close())
        if hasattr(tw, 'spawn_sync'):
            # python 3, but not python 2
            tw.spawn_sync(Vte.PtyFlags.DEFAULT,
                          os.environ['HOME'],
                          ["/bin/bash"],
                          [],
                          GLib.SpawnFlags.DO_NOT_REAP_CHILD,
                          None,
                          None)
        self.tw = tw

        tw.show()
        frame.pack_start(tw, True, True, 0)

        #self.add_close()
        # Add items to the menu
        menu = self.add_pulldownmenu("Page")

        item = Gtk.MenuItem(label="Close")
        menu.append(item)
        item.connect_object ("activate", lambda w: self.close(),
                             "menu.Close")
        item.show()



#END
