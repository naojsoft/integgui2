#
# Eric Jeschke (eric@naoj.org)
#

#from gi.repository import Gtk

from . import Workspace
from . import Page


class WorkspacePage(Workspace.Workspace, Page.Page):

    def __init__(self, frame, name, title):
        Page.Page.__init__(self, frame, name, title)
        Workspace.Workspace.__init__(self, frame, name, title)

        #self.nb.set_tab_pos(Gtk.PositionType.LEFT)

class ButtonWorkspacePage(Workspace.Workspace, Page.ButtonPage):

    def __init__(self, frame, name, title):
        Page.ButtonPage.__init__(self, frame, name, title)
        Workspace.Workspace.__init__(self, frame, name, title)

#END
