# 
#[ Eric Jeschke (eric@naoj.org) --
#  Last edit: Tue May  9 16:52:44 HST 2017
#]

from __future__ import absolute_import
import gtk

from . import common
from . import Page
from . import CommandObject

class DDCommandPage(Page.CommandPage):

    def __init__(self, frame, name, title):

        super(DDCommandPage, self).__init__(frame, name, title)

        self.queueName = 'default'
        self.tm_queueName = 'executer'

        scrolled_window = Gtk.ScrolledWindow()
        scrolled_window.set_border_width(2)

        scrolled_window.set_policy(Gtk.PolicyType.AUTOMATIC,
                                   Gtk.PolicyType.AUTOMATIC)

        tw = Gtk.TextView()
        tw.set_editable(True)
        tw.set_wrap_mode(Gtk.WrapMode.WORD)
        tw.set_left_margin(4)
        tw.set_right_margin(4)
        scrolled_window.add(tw)
        tw.show()
        scrolled_window.show()

        frame.pack_start(scrolled_window, True, True, 0)

        self.tw = tw
        self.buf = tw.get_buffer()

        ## self.add_menu()
        ## self.add_close()
        
        self.btn_exec = Gtk.Button("Exec")
        self.btn_exec.connect("clicked", lambda w: self.execute())
        self.btn_exec.modify_bg(Gtk.StateType.NORMAL,
                                common.launcher_colors['execbtn'])
        self.btn_exec.show()
        self.leftbtns.pack_end(self.btn_exec, False, False, 0)

        self.btn_append = Gtk.Button("Append")
        self.btn_append.connect("clicked", lambda w: self.insert())
        self.btn_append.show()
        self.leftbtns.pack_end(self.btn_append, False, False, 0)

        self.btn_prepend = Gtk.Button("Prepend")
        self.btn_prepend.connect("clicked", lambda w: self.insert(loc=0))
        self.btn_prepend.show()
        self.leftbtns.pack_end(self.btn_prepend, False, False, 0)

        self.btn_cancel = Gtk.Button("Cancel")
        self.btn_cancel.connect("clicked", lambda w: self.cancel())
        self.btn_cancel.modify_bg(Gtk.StateType.NORMAL,
                                common.launcher_colors['cancelbtn'])
        self.btn_cancel.show()
        self.leftbtns.pack_end(self.btn_cancel, False, False, 0)

        self.btn_pause = Gtk.Button("Pause")
        self.btn_pause.connect("clicked", self.toggle_pause)
        self.btn_pause.show()
        self.leftbtns.pack_end(self.btn_pause, False, False, 0)

        # Add items to the menu
        menu = self.add_pulldownmenu("Page")

        item = Gtk.MenuItem(label="Clear text")
        menu.append(item)
        item.connect_object ("activate", lambda w: self.clear_text(),
                             "menu.Clear")
        item.show()

        item = Gtk.MenuItem(label="Close")
        menu.append(item)
        item.connect_object ("activate", lambda w: self.close(),
                             "menu.Close")
        item.show()

        menu = self.add_pulldownmenu("Command")

        item = Gtk.MenuItem(label="Exec as launcher")
        menu.append(item)
        item.connect_object ("activate", lambda w: self.execute_as_launcher(),
                             "menu.Execute_as_launcher")
        item.show()

        menu = self.add_pulldownmenu("Queue")

        item = Gtk.MenuItem(label="Clear All")
        menu.append(item)
        item.connect_object ("activate", lambda w: common.controller.clearQueue(self.queueName),
                             "menu.Clear_All")
        item.show()

        item = Gtk.MenuItem(label="Attach to ...")
        menu.append(item)
        item.connect_object ("activate", lambda w: self.attach_queue(),
                             "menu.Attach_to")
        item.show()

    def clear_text(self):
        start, end = self.buf.get_bounds()
        self.buf.delete(start, end)
        
    def set_text(self, text):
        self.clear_text()
        itr = self.buf.get_end_iter()
        self.buf.insert(itr, text)
        itr = self.buf.get_end_iter()
        self.buf.place_cursor(itr)         

    # TODO: this is code share with OpePage.  Should be shared.
    def attach_queue(self):
        dialog = Gtk.MessageDialog(flags=Gtk.DIALOG_DESTROY_WITH_PARENT,
                                   type=Gtk.MESSAGE_QUESTION,
                                   buttons=Gtk.BUTTONS_OK_CANCEL,
                                   message_format="Pick the destination queue:")
        dialog.set_title("Connect Queue")
        # Add a combo box to the content area containing the names of the
        # current queues
        vbox = dialog.get_content_area()
        cbox = Gtk.ComboBoxText()
        index = 0
        names = []
        for name in common.controller.queue.keys():
            cbox.insert_text(index, name.capitalize())
            names.append(name)
            index += 1
        cbox.set_active(0)
        vbox.add(cbox)
        cbox.show()
        dialog.connect("response", self.attach_queue_res, cbox, names)
        dialog.show()

    def attach_queue_res(self, w, rsp, cbox, names):
        queueName = names[cbox.get_active()].strip().lower()
        w.destroy()
        if rsp == Gtk.RESPONSE_OK:
            if queueName not in common.view.queue:
                common.view.popup_error("No queue with that name exists!")
                return True
            self.queueName = queueName
        return True
        
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

        if len(cmdstr) == 0:
            raise Exception("No text in command buffer!")
            
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

            common.controller.execOne(cmdObj, self.tm_queueName)
        except Exception as e:
            common.view.popup_error(str(e))

    def execute_as_launcher(self):
        """Callback when the 'Exec as launcher' menu item is invoked.
        """
        try:
            cmdObj = self.get_dd_command()
            common.controller.execOne(cmdObj, 'launcher')

        except Exception as e:
            common.view.popup_error(str(e))

    def insert(self, loc=None, queueName='default'):
        """Callback when the Append button is pressed.
        """
        try:
            cmdObj = self.get_dd_command()

            queue = common.controller.queue[self.queueName]
            if loc == None:
                queue.append(cmdObj)
            else:
                queue.insert(loc, [cmdObj])

        except Exception as e:
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
