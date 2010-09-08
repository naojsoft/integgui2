# 
#[ Eric Jeschke (eric@naoj.org) --
#  Last edit: Tue Sep  7 17:13:20 HST 2010
#]

import gtk

import common
import Page
import CommandObject

class DDCommandPage(Page.CommandPage):

    def __init__(self, frame, name, title):

        super(DDCommandPage, self).__init__(frame, name, title)

        self.queueName = 'command'
        self.tm_queueName = 'executer'
        self.paused = False

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

        self.add_menu()
        self.add_close()
        
        self.btn_exec = gtk.Button("Exec")
        self.btn_exec.connect("clicked", lambda w: self.execute())
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

        self.btn_pause = gtk.Button("Pause")
        self.btn_pause.connect("clicked", self.toggle_pause)
        self.btn_pause.show()
        self.leftbtns.pack_end(self.btn_pause)

        # Add items to the menu
        item = gtk.MenuItem(label="Schedule")
        self.menu.append(item)
        item.connect_object ("activate", lambda w: self.schedule(),
                             "menu.Schedule")
        item.show()

        item = gtk.MenuItem(label="Exec as launcher")
        self.menu.append(item)
        item.connect_object ("activate", lambda w: self.execute_as_launcher(),
                             "menu.Execute_As_Launcher")
        item.show()


    def get_dd_command(self):
        # Clear the selection
        itr = self.buf.get_end_iter()
        self.buf.place_cursor(itr)         

        # Get the entire buffer from the page's text widget
        start, end = self.buf.get_bounds()
        txtbuf = self.buf.get_text(start, end).strip()

        # remove trailing semicolon, if present
        cmdstr = txtbuf
        if cmdstr.endswith(';'):
            cmdstr = cmdstr[:-1]

        # tag the text so we can manipulate it later
        cmdObj = DDCommandObject('dd%d', self.queueName,
                                 self.logger, self, cmdstr)
        return cmdObj

    def execute(self):
        """Callback when the 'Exec' button is pressed.
        """
        # Check whether we are busy executing a command here
        if common.controller.executingP.isSet():
            # Yep--popup an error message
            common.view.popup_error("There is already a %s task running!" % (
                self.tm_queueName))
            return

        try:
            cmdObj = self.get_dd_command()

            common.controller.replaceQueueAndExecute(self.queueName, [cmdObj],
                                                     tm_queueName=self.tm_queueName)
        except Exception, e:
            common.view.popup_error(str(e))

    def execute_as_launcher(self):
        """Callback when the 'Exec as launcher' menu item is invoked.
        """
        try:
            cmdObj = self.get_dd_command()
            common.controller.execOne(cmdObj, 'launcher')

        except Exception, e:
            common.view.popup_error(str(e))

    def schedule(self, queueName='default'):
        """Callback when the Schedule button is pressed.
        """
        try:
            cmdObj = self.get_dd_command()
            common.controller.appendQueue(queueName, [cmdObj])

        except Exception, e:
            common.view.popup_error(str(e))


class DDCommandObject(CommandObject.CommandObject):

    def __init__(self, format, queueName, logger, page, cmdstr):
        self.page = page
        self.cmdstr = cmdstr

        super(DDCommandObject, self).__init__(format, queueName, logger)
        
    def get_preview(self):
        return self.get_cmdstr()
    
    def get_cmdstr(self):
        return self.cmdstr

    def mark_status(self, txttag):
        pass

#END
