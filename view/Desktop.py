import gtk

import Workspace


class Desktop(object):
    
    def __init__(self, frame, name, title):
        self.frame = frame
        self.name = name
        self.title = title

        # TODO: should generalize to number of rows and columns

        paned = gtk.HPaned()
        self.hframe = paned
        paned.show()

        frame.pack_start(paned, fill=True, expand=True)

        lframe = gtk.VPaned()
        rframe = gtk.VPaned()

        paned.add1(lframe)
        paned.add2(rframe)

        ul = gtk.VBox()
        lframe.add1(ul)
        ll = gtk.VBox()
        lframe.add2(ll)

        ur = gtk.VBox()
        rframe.add1(ur)
        lr = gtk.VBox()
        rframe.add2(lr)

        self.ws_fr = {
            'll': ll,
            'ul': ul,
            'lr': lr,
            'ur': ur,
            }

        self.ws = {}

        paned.show_all()


    def get_wsframe(self, name):
        return self.ws_fr[name]

    def addws(self, loc, name, title):

        frame = self.get_wsframe(loc)

        ws = Workspace.Workspace(frame, name, title)
        # Some attributes we force on our children
        ws.logger = self.logger

        frame.show_all()
        
        self.ws[name] = ws
        return ws

    def getws(self, name):
        return self.ws[name]


#END
