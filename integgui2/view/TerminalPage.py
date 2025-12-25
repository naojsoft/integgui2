#
# E. Jeschke
#

import os

from ginga.gw import Widgets

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
        self.content.add_widget(Widgets.wrap(tw), stretch=1)

        #self.add_close()
        # Add items to the menu
        menu = self.add_pulldownmenu("Page")

        item = menu.add_name("Close")
        item.add_callback("activated", lambda w: self.close())
