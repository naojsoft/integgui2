# 
#[ Eric Jeschke (eric@naoj.org) --
#  Last edit: Tue May 18 16:36:44 HST 2010
#]

import gtk

import common
import Page


class DDCommandPage(Page.ButtonPage):

    def __init__(self, frame, name, title):

        super(DDCommandPage, self).__init__(frame, name, title)

        self.queueName = 'executer'
        self.block = False

        scrolled_window = gtk.ScrolledWindow()
        scrolled_window.set_border_width(2)

        scrolled_window.set_policy(gtk.POLICY_AUTOMATIC,
                                   gtk.POLICY_AUTOMATIC)

        tw = gtk.TextView()
        tw.set_editable(True)
        tw.set_wrap_mode(gtk.WRAP_NONE)
        tw.set_left_margin(4)
        tw.set_right_margin(4)
        scrolled_window.add(tw)
        tw.show()
        scrolled_window.show()

        frame.pack_start(scrolled_window, expand=True, fill=True)

        self.tw = tw
        self.buf = tw.get_buffer()

        self.add_close()
        
        self.btn_exec = gtk.Button("Exec")
        self.btn_exec.connect("clicked", lambda w: common.view.execute_dd(self))
        self.btn_exec.modify_bg(gtk.STATE_NORMAL,
                                common.launcher_colors['execbtn'])
        self.btn_exec.show()
        self.leftbtns.pack_end(self.btn_exec)

        self.btn_cancel = gtk.Button("Cancel")
        self.btn_cancel.connect("clicked", lambda w: self.cancel())
        self.btn_cancel.modify_bg(gtk.STATE_NORMAL,
                                common.launcher_colors['cancelbtn'])
        self.btn_cancel.show()
        self.leftbtns.pack_end(self.btn_cancel)

        self.btn_kill = gtk.Button("Kill")
        self.btn_kill.connect("clicked", lambda w: self.kill())
        self.btn_kill.modify_bg(gtk.STATE_NORMAL,
                                common.launcher_colors['killbtn'])
        self.btn_kill.show()
        self.leftbtns.pack_end(self.btn_kill)

        self.btn_pause = gtk.ToggleButton("Pause")
        self.btn_pause.connect("toggled", self.toggle_pause)
        self.btn_pause.show()
        self.leftbtns.pack_end(self.btn_pause)

    def kill(self):
        #controller = self.parent.get_controller()
        controller = common.controller
        controller.tm_restart()
        self.block = True
        self.btn_pause.set_active(False)
        self.block = False

    def cancel(self):
        #controller = self.parent.get_controller()
        controller = common.controller
        controller.tm_cancel(self.queueName)
        self.block = True
        self.btn_pause.set_active(False)
        self.block = False

    def pause(self):
        if self.block:
            return
        #controller = self.parent.get_controller()
        controller = common.controller
        controller.tm_pause(self.queueName)

    def resume(self):
        if self.block:
            return
        #controller = self.parent.get_controller()
        controller = common.controller
        controller.tm_resume(self.queueName)

    def toggle_pause(self, w):
        if w.get_active():
            self.pause()
            self.btn_pause.set_label("Resume")
        else:
            self.resume()
            self.btn_pause.set_label("Pause")

        return True


#END
