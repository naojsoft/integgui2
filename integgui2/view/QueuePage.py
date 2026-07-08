#
# E. Jeschke
#
import os, re

from ginga.gw import Widgets
from ginga.misc import Bunch

from . import common
from . import Page
from . import CommandObject
from .TextSource import TextSource


class QueuePage(Page.ButtonPage, Page.TextPage):

    def __init__(self, frame, name, title):

        super(QueuePage, self).__init__(frame, name, title)

        self.paused = False

        self.queueName = ''
        self.queueObj = None
        self.tm_queueName = 'executer'

        # Create the widgets for the text
        tw = TextSource(editable=False, wrap=False)
        # TODO
        #tw.set_left_margin(4)
        #tw.set_right_margin(4)

        self.tw = tw

        # Stores saved selection
        self.sel_i = None
        self.sel_j = None
        # Stores cut
        self.clip = []

        self.cursor = 0
        self.moving_cursor = False

        # keyboard shortcuts and cursor-line tracking
        self.tw.add_callback('key-press', self.keypress)
        self.tw.add_callback('cursor_moved', self.show_cursor)

        # define the tags used to color queue lines (includes 'selected'
        # and 'cursor')
        for tag, bnch in common.queue_tags:
            properties = {}
            properties.update(bnch)
            try:
                self.tw.create_tag(tag, **properties)
            except Exception:
                # tag may already exist--that's ok
                pass

        self.content.add_widget(self.tw, stretch=1)

        ## self.add_menu()
        ## self.add_close()

        # add some bottom buttons
        self.btn_exec = Widgets.Button("Resume")
        self.btn_exec.add_callback("activated", lambda w: self.resume())
        common.modify_bg(self.btn_exec,
                         common.launcher_colors['execbtn'])
        self.leftbtns.add_widget(self.btn_exec)

        self.btn_step = Widgets.Button("Step")
        self.btn_step.add_callback("activated", lambda w: self.step())
        common.modify_bg(self.btn_step,
                         common.launcher_colors['execbtn'])
        self.leftbtns.add_widget(self.btn_step)

        self.btn_break = Widgets.Button("Break")
        self.btn_break.add_callback("activated", lambda w: self.insbreak(line=0))
        self.leftbtns.add_widget(self.btn_break)

        self.btn_refresh = Widgets.Button("Refresh")
        self.btn_refresh.add_callback("activated", lambda w: self.redraw())
        self.leftbtns.add_widget(self.btn_refresh)

        menu = self.add_pulldownmenu("Page")

        item = menu.add_name("Close")
        # currently disabled
        item.set_enabled(False)
        item.add_callback("activated", lambda w: self.close())

        menu = self.add_pulldownmenu("Queue")

        item = menu.add_name("Clear All")
        item.add_callback("activated", lambda w: common.controller.clearQueue(self.queueName))

        item = menu.add_name("Pop and edit command")
        item.add_callback("activated", lambda w: self.editCommand())


    def set_queue(self, queueName, queueObj):
        self.queueName = queueName
        self.queueObj = queueObj
        # Hmmm...asking for GC troubles?
        queueObj.add_view(self)

        # change our tab title to match the queue
        tabName = queueObj.name.capitalize()
        self.setLabel(tabName)

    def close(self):
        self.queueObj.del_view(self)
        super(QueuePage, self).close()

    def editCommand(self):
        try:
            cmdObj = self.queueObj.peek()
            self.queueObj.remove(cmdObj)

        except Exception as e:
            # TODO: popup error here?
            common.view.gui_do(common.view.popup_error, str(e))

        common.controller.editOne(cmdObj)

    def _redraw(self):
        common.view.assert_gui_thread()

        with self.lock:
            # suppress cursor-line tracking while we rebuild the buffer
            self.moving_cursor = True
            try:
                self.tw.clear()

                numlines = 0
                for cmdObj in self.queueObj.peekAll():
                    tag = 'normal'
                    try:
                        text = cmdObj.get_preview()
                        if text.startswith('###'):
                            tag = 'comment3'
                        elif text.startswith('##'):
                            tag = 'comment2'
                        elif text.startswith('#'):
                            tag = 'comment1'
                    except Exception as e:
                        text = "++ THIS COMMAND HAS BEEN DELETED IN THE SOURCE PAGE ++"
                        tag = 'badref'

                    # Append the colored command line
                    self.tw.append_text(text, tags=[tag], autoscroll=False)
                    self.tw.append_text('\n', autoscroll=False)
                    numlines += 1

                # Restore the selection highlight, if any
                # TODO: make selection a part of the CommandQueue?
                if self.has_selection():
                    self.sel_i = min(self.sel_i, numlines)
                    self.sel_j = min(self.sel_j, numlines)
                    first = self.tw.get_ref_line_start(self.sel_i)
                    last = self.tw.get_ref_line_end(self.sel_j)
                    self.tw.apply_tag('selected', first, last)

                # restore cursor and highlight its line
                self.cursor = min(self.cursor, numlines)
                loc = self.tw.get_ref_line_start(self.cursor)
                self.tw.set_cursor(loc)
                self.tw.scroll_to_ref(loc)
                self._highlight_cursor_line(self.cursor)
            finally:
                self.moving_cursor = False

    def _highlight_cursor_line(self, line):
        """Move the 'cursor' highlight tag to the given line."""
        common.clear_tags(self.tw, ('cursor',))
        start = self.tw.get_ref_line_start(line)
        end = self.tw.get_ref_line_end(line)
        self.tw.apply_tag('cursor', start, end)


    def redraw(self):
        common.gui_do(self._redraw)

    def set_selection(self):
        # Clear previous selection highlight, if any
        common.clear_tags(self.tw, ('selected',))

        # Get the range of text selected
        bounds = self.tw.get_selection_bounds()
        if bounds is not None:
            first, last = bounds
            # Clear the text selection
            common.clear_selection(self.tw)
        else:
            # If there is no selection, then use the cursor line
            cur = self.tw.get_cursor()
            first = cur.copy()
            last = cur.copy()

        lrow = last.get_line()

        # Adjust to beginning and end of lines
        first.to_line_start()
        if last.get_line_column()[1] == 0:
            # Hack to fix problem where selection covers the newline
            # but not the first character of the next line
            lrow -= 1
            last.set_line(lrow)
        last.to_line_end()

        # Apply color to rows and save selection indexes
        self.tw.apply_tag('selected', first, last)
        self.sel_i = first.get_line()
        self.sel_j = last.get_line()

    def clear_selection(self):
        common.clear_tags(self.tw, ('selected',))

        common.clear_selection(self.tw)

        self.sel_i = None
        self.sel_j = None

    def has_selection(self):
        return self.sel_i != None

    def cut(self):
        if not self.has_selection():
            # Try to set a selection if none provided
            self.set_selection()

        if self.has_selection():
            (i, j) = (self.sel_i, self.sel_j)
            #print("i=%d j=%d" % (i, j))
            self.clear_selection()

            self.clip = self.queueObj.delete(i, j+1)
        else:
            common.view.popup_error("Please make a selection first!")

    def copy(self):
        if not self.has_selection():
            # Try to set a selection if none provided
            self.set_selection()

        if self.has_selection():
            (i, j) = (self.sel_i, self.sel_j)
            #print("i=%d j=%d" % (i, j))
            self.clear_selection()

            self.clip = self.queueObj.getslice(i, j+1)
        else:
            common.view.popup_error("Please make a selection first!")

    def set_clip(self, clip):
        # clip must contain CommandObjects!
        self.clip = clip

    def paste(self, clip=None):
        if clip == None:
            clip = self.clip
        if len(clip) == 0:
            common.view.popup_error("Please cut/copy the selection first.")
            return

        k = self.tw.get_cursor().get_line()

        self.queueObj.insert(k, clip)
        #self.clip = []

    def move(self):
        if not self.has_selection():
            common.view.popup_error("Please make a selection with 's' first.")
            return

        (i, j) = (self.sel_i, self.sel_j)
        #print("i=%d j=%d" % (i, j))
        self.clear_selection()

        deleted = self.queueObj.delete(i, j+1)

        k = self.tw.get_cursor().get_line()

        self.queueObj.insert(k, deleted)


    def insbreak(self, line=None):
        if line == None:
            line = self.tw.get_cursor().get_line()

        try:
            cmdobj = CommandObject.BreakCommandObject('brk%d', self.queueName,
                                                     self.logger, self)
            self.queueObj.insert(line, [cmdobj])
        except Exception as e:
            common.view.popup_error(str(e))

    def _skip_comment(self, line):
        # TODO: need lock?
        while line < len(self.queueObj):
            cmdObj = self.queueObj[line]
            if isinstance(cmdObj, CommandObject.CommentCommandObject):
                line += 1
                continue
            break
        return line

    def _resume(self, w_break=False):
        """Callback when the Resume button is pressed.
        """
        # Check whether we are busy executing a command here
        if common.controller.executingP.isSet():
            # Yep--popup an error message
            common.view.popup_error("There is already a %s task running!" % (
                self.tm_queueName))
            return

        # Get length of queued items, if any
        num_queued = len(self.queueObj)

        if num_queued == 0:
            common.view.popup_error("No %s queued commands!" % (
                self.queueName))
            return

        if w_break:
            try:
                # Take a peek at the top item on the queue.  If it is not
                # a break, then insert a break right after the top command
                cmdobj = self.queueObj.peek()
                if not isinstance(cmdobj, CommandObject.BreakCommandObject):
                    cmdobj = CommandObject.BreakCommandObject('brk%d',
                                                              self.queueName,
                                                              self.logger, self)
                    i = self._skip_comment(0)
                    if i < num_queued:
                        i += 1
                    self.queueObj.insert(i, [cmdobj])
            except Exception as e:
                common.view.popup_error(str(e))
                return

        try:
            common.controller.execQueue(self.queueName,
                                        tm_queueName=self.tm_queueName)
        except Exception as e:
            common.view.popup_error(str(e))


    def resume(self):
        return self._resume()

    def step(self):
        return self._resume(w_break=True)

    def keypress(self, w, event):
        keyname = event.key
        if keyname in ('up', 'down', 'shift_l', 'shift_r',
                       'alt_l', 'alt_r', 'control_l', 'control_r'):
            # navigation and modifiers: let the widget handle them
            return False
        if keyname in ('left', 'right'):
            # ignore these
            return True
        #print("key pressed --> %s" % keyname)

        if keyname == 'r':
            self._redraw()
            return True
        elif keyname == 's':
            self.set_selection()
            return True
        elif keyname == 'a':
            self.clear_selection()
            return True
        elif keyname == 'c':
            self.copy()
            return True
        elif keyname == 'x':
            self.cut()
            return True
        elif keyname == 'v':
            self.paste()
            return True
        elif keyname == 'm':
            self.move()
            return True
        elif keyname == 'b':
            self.insbreak()
            return True

        common.view.statusMsg("I don't understand that key: %s" % keyname)
        return True

    def show_cursor(self, w):
        # Called on the widget's 'cursor_moved' callback; highlight the line
        # the cursor is on.
        if self.moving_cursor:
            return False

        self.moving_cursor = True
        try:
            line = self.tw.get_cursor().get_line()
            self.cursor = line
            self._highlight_cursor_line(line)
        finally:
            self.moving_cursor = False
        return True

    # TODO: drag-and-drop reordering (was GTK-based; not yet reimplemented
    # for the Qt/ginga backend).
