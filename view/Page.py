#
#[ Eric Jeschke (eric@naoj.org) --
#  Last edit: Tue May 18 17:15:12 HST 2010
#]
#
import threading

import gtk

import common

# constants
LEFT  = 'left'
RIGHT = 'right'


class Page(object):

    def __init__(self, frame, name, title):

        self.frame = frame
        self.name = name
        self.title = title

        self.closed = False

        # every page has a lock
        self.lock = threading.RLock()

    def close(self):
        # parent attribute is added by parent workspace
        self.parent.delpage(self.name)

        self.closed = True


class ButtonPage(Page):

    def __init__(self, frame, name, title):
        super(ButtonPage, self).__init__(frame, name, title)

        # bottom buttons
        self.btnframe = gtk.HBox()
        
        btns = gtk.HButtonBox()
        btns.set_layout(gtk.BUTTONBOX_START)
        btns.set_spacing(5)
        self.leftbtns = btns

        self.btnframe.pack_start(self.leftbtns, fill=False, expand=False)
        btns.show()

        btns = gtk.HButtonBox()
        btns.set_layout(gtk.BUTTONBOX_START)
        btns.set_spacing(5)
        self.rightbtns = btns
        
        self.btnframe.pack_end(self.rightbtns, fill=False, expand=False)
        btns.show()

        frame.pack_end(self.btnframe, fill=True, expand=False, padding=2)
        self.btnframe.show()

    def _get_side(self, side):
        if side == LEFT:
            return self.leftbtns
        elif side == RIGHT:
            return self.rightbtns
        return None
    
    def add_close(self, side=RIGHT):
        self.btn_close = gtk.Button("Close")
        self.btn_close.connect("clicked", lambda w: self.close())
        self.btn_close.show()
        w = self._get_side(side)
        w.pack_end(self.btn_close, padding=4)

    def add_menu(self, side=RIGHT):
        self.btn_menu = gtk.Button("Menu")
        self.menu = gtk.Menu()
        self.btn_menu.connect_object("event", self.popup_menu, self.menu)
        self.btn_menu.show()
        w = self._get_side(side)
        w.pack_end(self.btn_menu, padding=4)

    def popup_menu(self, w, event):
        if event.type == gtk.gdk.BUTTON_PRESS:
            self.menu.popup(None, None, None, event.button, event.time)
            return True
        return False
        

class CommandPage(ButtonPage):

    def kill(self):
        #controller = self.parent.get_controller()
        controller = common.controller
        controller.tm_restart()
        self.reset_pause()

    def cancel(self):
        #controller = self.parent.get_controller()
        controller = common.controller
        controller.tm_cancel(self.queueName)
        self.reset_pause()

    def pause(self):
        self.btn_pause.set_label("Resume")
        self.paused = True
        #controller = self.parent.get_controller()
        controller = common.controller
        controller.tm_pause(self.queueName)

    def resume(self):
        self.reset_pause()
        #controller = self.parent.get_controller()
        controller = common.controller
        controller.tm_resume(self.queueName)

    def toggle_pause(self, w):
        common.view.playSound(common.sound.pause_toggle)
        if self.paused:
            self.resume()
        else:
            self.pause()

        return True

    def reset_pause(self):
        self.btn_pause.set_label("Pause")
        self.paused = False

    def reset(self):
        self.reset_pause()


#END
