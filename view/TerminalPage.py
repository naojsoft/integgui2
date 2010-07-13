# 
#[ Eric Jeschke (eric@naoj.org) --
#  Last edit: Tue May 18 16:36:44 HST 2010
#]

import gtk
import vte

import common
import Page


class TerminalPage(Page.CommandPage):

    def __init__(self, frame, name, title):

        super(TerminalPage, self).__init__(frame, name, title)

        tw = vte.Terminal()
        tw.connect("child-exited", lambda w: self.close())
        tw.fork_command()
        self.tw = tw

        tw.show()
        frame.pack_start(tw, expand=True, fill=True)

        self.add_close()

        

#END
