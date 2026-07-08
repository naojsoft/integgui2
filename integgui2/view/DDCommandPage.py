#
# E. Jeschke
#

from ginga.gw import Widgets

from . import common
from . import Page
from . import CommandObject
from .TextSource import TextSource


class DDCommandPage(Page.CommandPage):

    def __init__(self, frame, name, title):

        super(DDCommandPage, self).__init__(frame, name, title)

        self.queueName = 'default'
        self.tm_queueName = 'executer'

        tw = TextSource(editable=True, wrap=True)
        # TODO
        #tw.set_left_margin(4)
        #tw.set_right_margin(4)

        self.content.add_widget(tw, stretch=1)

        self.tw = tw

        ## self.add_menu()
        ## self.add_close()

        self.btn_exec = Widgets.Button("Exec")
        self.btn_exec.add_callback("activated", lambda w: self.execute())
        common.modify_bg(self.btn_exec,
                         common.launcher_colors['execbtn'])
        self.leftbtns.add_widget(self.btn_exec)

        self.btn_append = Widgets.Button("Append")
        self.btn_append.add_callback("activated", lambda w: self.insert())
        self.leftbtns.add_widget(self.btn_append)

        self.btn_prepend = Widgets.Button("Prepend")
        self.btn_prepend.add_callback("clicked", lambda w: self.insert(loc=0))
        self.leftbtns.add_widget(self.btn_prepend)

        self.btn_cancel = Widgets.Button("Cancel")
        self.btn_cancel.add_callback("clicked", lambda w: self.cancel())
        common.modify_bg(self.btn_cancel,
                         common.launcher_colors['cancelbtn'])
        self.leftbtns.add_widget(self.btn_cancel)

        self.btn_pause = Widgets.Button("Pause")
        self.btn_pause.add_callback("clicked", self.toggle_pause)
        self.leftbtns.add_widget(self.btn_pause)

        # Add items to the menu
        menu = self.add_pulldownmenu("Page")

        item = menu.add_name("Clear text")
        item.add_callback("activated", lambda w: self.clear_text())

        item = menu.add_name("Close")
        item.add_callback("activated", lambda w: self.close())

        menu = self.add_pulldownmenu("Command")

        item = menu.add_name("Exec as launcher")
        item.add_callback("activated", lambda w: self.execute_as_launcher())

        menu = self.add_pulldownmenu("Queue")

        item = menu.add_name("Clear All")
        item.add_callback("activated", lambda w: common.controller.clearQueue(self.queueName))

        item = menu.add_name("Attach to ...")
        item.add_callback("activated", lambda w: self.attach_queue())

    def clear_text(self):
        self.tw.clear()

    def set_text(self, text):
        self.tw.set_text(text)
        # place cursor at end
        self.tw.set_cursor(self.tw.get_ref_end())

    # TODO: this is code share with OpePage.  Should be shared.
    def attach_queue(self):
        dialog = Widgets.MessageDialog(title="Connect Queue",
                                       buttons=[("Ok", 1), ("Cancel", 0)])
        dialog.set_message('question', "Pick the destination queue:")
        # Add a combo box to the content area containing the names of the
        # current queues
        vbox = dialog.get_content_area()
        cbox = Widgets.ComboBox()
        names = []
        for name in common.controller.queue.keys():
            cbox.append_text(name.capitalize())
            names.append(name)
        cbox.set_index(0)
        vbox.add_widget(cbox, stretch=0)
        dialog.add_callback('activated', self.attach_queue_res, cbox, names)
        dialog.show()

    def attach_queue_res(self, w, rsp, cbox, names):
        queueName = names[cbox.get_index()].strip().lower()
        w.destroy()
        if rsp == 1:
            if queueName not in common.view.queue:
                common.view.popup_error("No queue with that name exists!")
                return True
            self.queueName = queueName
        return True

    def get_dd_command(self):
        # Clear the selection: place cursor at end
        self.tw.set_cursor(self.tw.get_ref_end())

        # Get the entire buffer from the page's text widget
        txtbuf = self.tw.get_text().strip()

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
