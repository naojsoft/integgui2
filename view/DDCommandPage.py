# 
#[ Eric Jeschke (eric@naoj.org) --
#  Last edit: Wed Sep  1 21:03:27 HST 2010
#]

import gtk

import common
import Page
import CommandObject

class DDCommandPage(Page.CommandPage):

    def __init__(self, frame, name, title):

        super(DDCommandPage, self).__init__(frame, name, title)

        self.queueName = 'executer'
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


    def execute(self):
        """Callback when the EXEC button is pressed.
        """
        # Check whether we are busy executing a command here
        if common.controller.executingP.isSet():
            # Yep--popup an error message
            common.view.popup_error("There is already a %s task running!" % (
                self.queueName))
            return

        # tag the text so we can manipulate it later
        cmdObj = DDCommandObject('dd%d', self.queueName,
                                 self.logger, self)

        # Clear the selection
        itr = self.buf.get_end_iter()
        self.buf.move_mark_by_name("insert", itr)         
        self.buf.move_mark_by_name("selection_bound", itr)

        common.controller.prependQueue(self.queueName, cmdObj)
        common.controller.resumeQueue(self.queueName)


class DDCommandObject(CommandObject.CommandObject):

    def __init__(self, format, queueName, logger, page):
        self.page = page

        super(DDCommandObject, self).__init__(format, queueName, logger)
        
    def get_preview(self):
        return self.get_cmdstr()
    
    def get_cmdstr(self):
        # Get the entire buffer from the page's text widget
        buf = self.page.buf
        start, end = buf.get_bounds()
        txtbuf = buf.get_text(start, end).strip()

        # remove trailing semicolon, if present
        cmdstr = txtbuf
        if cmdstr.endswith(';'):
            cmdstr = cmdstr[:-1]

        self.cmdstr = cmdstr
        return cmdstr

    def mark_status(self, txttag):
        pass

    def execute(self):
        # Get the command string associated with this kind of page.
        cmdstr = self.get_cmdstr()
        
        try:
            # Try to execute the command in the TaskManager
            self.logger.debug("Invoking to task manager (%s): '%s'" % (
                self.queueName, cmdstr))

            common.controller.executingP.set()

            res = common.controller.tm.execTask(self.queueName,
                                                cmdstr, '')
            common.controller.executingP.clear()

            if res == 0:
                self.feedback_ok(res)
            else:
                self.feedback_error('Command terminated with res=%d' % res)

        except Exception, e:
            common.controller.executingP.clear()
            self.feedback_error(str(e))


    def feedback_ok(self, res):
        """This method is indirectly invoked via the controller when
        there is feedback that a command has completed successfully.
        """
        self.logger.info("Ok [%s] %s" % (
            self.queueName, self.cmdstr))

        soundfile = common.sound.success_executer
        common.controller.playSound(soundfile)

           
    def feedback_error(self, e):
        """This method is indirectly invoked via the controller when
        there is feedback that a command has completed with failure.
        """
        self.logger.error("Error [%s] %s\n:%s" % (
            self.queueName, self.cmdstr, str(e)))
        
        soundfile = common.sound.failure_executer
        #common.view.gui_do(common.view.popup_error, str(e))
        #common.view.statusMsg(str(e))
        common.controller.playSound(soundfile)

        
#END
