# 
#[ Eric Jeschke (eric@naoj.org) --
#  Last edit: Fri Oct  1 17:10:39 HST 2010
#]

import gtk

import Workspace
import Page


class WorkspacePage(Workspace.Workspace, Page.Page):

    def __init__(self, frame, name, title):
        super(WorkspacePage, self).__init__(frame, name, title)

        self.nb.set_tab_pos(gtk.POS_LEFT)

class ButtonWorkspacePage(Workspace.Workspace, Page.ButtonPage):
    pass

#END
