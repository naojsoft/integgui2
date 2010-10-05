# 
#[ Eric Jeschke (eric@naoj.org) --
#  Last edit: Sat Oct  2 15:02:12 HST 2010
#]

import gtk

import Workspace
import Page


class WorkspacePage(Workspace.Workspace, Page.Page):
    pass

    ## def __init__(self, frame, name, title):
    ##     super(WorkspacePage, self).__init__(frame, name, title)

    ##     self.nb.set_tab_pos(gtk.POS_LEFT)

class ButtonWorkspacePage(Workspace.Workspace, Page.ButtonPage):
    pass

#END
