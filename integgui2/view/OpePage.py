#
# E. Jeschke
#
import sys, traceback

import os, re

from ginga.gw import Widgets

import oscript.parse.ope as ope

from . import common
from . import Page, CodePage
from . import CommandObject

thisDir = os.path.split(sys.modules[__name__].__file__)[0]
icondir = os.path.abspath(os.path.join(thisDir, "..", "icons"))

warning_close = """
WARNING:
You are attempting to delete text in this buffer that is needed
by queued commands.

Please choose one of the following options:

1) Don't close page.
2) Unlink queued commands from this page and close page.
3) Remove the commands from the queue and close page.

"""

warning_reload = """
WARNING:
You are attempting to replace text in this buffer that is needed
by queued commands.

Please choose one of the following options:

1) Don't reload page.
2) Unlink queued commands from this page and reload page.
3) Remove the commands from the queue and reload page.
4) Open the OPE file again in a new page.

"""

warning_queued = """
WARNING:
There are queued commands.

Please choose one of the following options:

1) Prepend these commands to the queue along with a breakpoint and execute.
2) Prepend these commands to the queue, but don't execute.
3) Append these commands to the queue, but don't execute.
4) Replace queued commands with these commands and execute.
5) Cancel this execute request.

"""


class OpePage(CodePage.CodePage, Page.CommandPage):

    def __init__(self, frame, name, title):
        super().__init__(frame, name, title)

        self.queueName = 'default'
        self.tm_queueName = 'executer'

        self.varDict = {}

        settings = common.view.get_settings()
        wrap_lines = settings.get('wrap_lines', False)
        if wrap_lines:
            self.line_wrapping('full')

        number_lines = settings.get('show_line_numbers', False)
        self.line_numbering(number_lines)

        # this is for variable definition popups
        self.tw.enable_tooltips(True)
        self.tw.add_callback('tooltip', self.query_vardef)
        # keyboard shortcuts (Ctrl-modified)
        self.tw.add_callback('key-press', self.keypress)
        # TODO?
        #self.tw.connect("focus-in-event", self.focus_in)

        self.tw.enable_line_icons(True)
        # TODO
        #self.tw.set_insert_spaces_instead_of_tabs(True)

        # add some bottom buttons
        self.btn_exec = Widgets.Button("Exec")
        self.btn_exec.add_callback("activated", lambda w: self.execute())
        self.btn_exec.set_color(bg=common.launcher_colors['execbtn'])
        self.leftbtns.add_widget(self.btn_exec)

        self.btn_append = Widgets.Button("Append")
        self.btn_append.add_callback("activated", lambda w: self.insert())
        self.leftbtns.add_widget(self.btn_append)

        self.btn_prepend = Widgets.Button("Prepend")
        self.btn_prepend.add_callback("activated", lambda w: self.insert(loc=0))
        self.leftbtns.add_widget(self.btn_prepend)

        self.btn_cancel = Widgets.Button("Cancel")
        self.btn_cancel.add_callback("activated", lambda w: self.cancel())
        self.btn_cancel.set_color(bg=common.launcher_colors['cancelbtn'])
        self.leftbtns.add_widget(self.btn_cancel)

        self.btn_pause = Widgets.Button("Pause")
        self.btn_pause.add_callback("activated", self.toggle_pause)
        self.leftbtns.add_widget(self.btn_pause)

        # Exec/Append/Prepend act on the current selection, so disable them
        # whenever there is no selection.  Selection changes arrive via the
        # text widget's 'cursor_moved' callback.
        self.tw.add_callback('cursor_moved',
                             lambda w: self._update_button_states())
        self._update_button_states()

        # Add items to the menu
        menu = self.add_pulldownmenu("Buffer")

        item = menu.add_name("Recolor")
        item.add_callback("activated", lambda w: self.color())

        item = menu.add_name("Uncolor")
        item.add_callback("activated", lambda w: self.color(eraseall=True))

        item = menu.add_name("Current")
        item.add_callback("activated", lambda w: self.current())

        menu = self.add_pulldownmenu("Queue")

        item = menu.add_name("Clear all")
        item.add_callback("activated", lambda w: common.controller.clearQueue(self.queueName))

        item = menu.add_name("Clear my")
        item.add_callback("activated", lambda w: self.unqueue_my_commands())

        item = menu.add_name("Unlink my")
        item.add_callback("activated", lambda w: self.unlink_my_commands())

        item = menu.add_name("Attach to ...")
        item.add_callback("activated", lambda w: self.attach_queue())

        menu = self.add_pulldownmenu("Options")

        item = menu.add_name("Don't link commands to page", checkable=True)
        item.set_state(False)
        item.add_callback("activated", lambda w, tf: self.toggle_var(tf, 'add_frozen'))

        # option variables
        self.add_frozen = False


    def toggle_var(self, tf, key):
        self.__dict__[key] = tf

    def _update_button_states(self):
        """Enable Exec/Append/Prepend only when there is a selection."""
        tf = self.tw.has_selection()
        self.btn_exec.set_enabled(tf)
        self.btn_append.set_enabled(tf)
        self.btn_prepend.set_enabled(tf)

    def load(self, filepath, buf):
        super().load(filepath, buf)
        self.cond_color()

    def _reload(self):
        super().reload()
        self.cond_color()
        common.remove_all_marks(self.tw)

    def reload(self):
        if not self.reload_check():
            return
        self._reload()

    def reload_check(self):
        num = len(self.my_queued_commands())
        if num == 0:
            return True
        #common.view.popup_error("%d commands are still queued!" % num)
        self.build_dialog("%d commands are queued" % num, warning_reload,
                          [("Cancel", 1), ("Unlink", 2), ("Remove", 3),
                           ("New Page", 4)],
                          self.reload_check_res).show()
        return False

    def reload_check_res(self, w, rsp):
        if rsp == 2:
            self.unlink_my_commands()
            self._reload()

        elif rsp == 3:
            self.unqueue_my_commands()
            self._reload()

        elif rsp == 4:
            common.view.load_generic(self.filepath, OpePage)

        return True

    def queued_check(self, fn_res):
        num = len(self.my_queued_commands())
        if num == 0:
            return True
        self.build_dialog("%d commands are queued" % num, warning_queued,
                          [("Prepend w/Break and Exec", 1), ("Prepend", 2),
                           ("Append", 3), ("Replace and Exec", 4),
                           ("Cancel", 5)],
                          fn_res).show()
        return False

    def close_check(self):
        num = len(self.my_queued_commands())
        if num == 0:
            return True
        #common.view.popup_error("%d commands are still queued!" % num)
        self.build_dialog("%d commands are queued" % num, warning_close,
                          [("Cancel", 1), ("Unlink", 2), ("Remove", 3)],
                          self.close_check_res).show()
        return False

    def close_check_res(self, w, rsp):
        if rsp == 2:
            self.unlink_my_commands()
            self._close()

        elif rsp == 3:
            self.unqueue_my_commands()
            self._close()

        return True

    def _close(self):
        super().close()

    def close(self):
        if not self.close_check():
            return
        self._close()

    def unqueue_my_commands(self):
        tags = self.my_queued_commands()
        common.controller.remove_by_tags(tags)

    def unlink_my_commands(self):
        tags = self.my_queued_commands()
        self._convert_linked_commands(tags)
        return True

    def my_queued_commands(self):
        """Return the list of tags from our text buffer that are referenced
        from active queues."""
        tags = common.controller.get_all_queued_tags()
        return self.sift_tags(tags)

    def remove_commands(self, tags):
        """Remove from any queues commands corresponding to this
        list of tags."""
        common.controller.remove_by_tag(tags)

    def sift_tags(self, taglist):
        """From a list of tags (taglist), return the subset that are
        defined in our buffer."""
        # TODO: can we improve the efficiency of this?
        res = []
        num = 0
        for tagname in taglist:
            if self.tw.has_tag(tagname):
                res.append(tagname)
        return res

    def cond_color(self):
        name, ext = os.path.splitext(self.filepath)
        ext = ext.lower()

        if ext in ('.ope', '.cd'):
            self.color()

    def get_vardef(self, varname):
        try:
            return self.varDict[varname]
        except KeyError:
            raise Exception("No definition found for '%s'" % varname)

    def get_target_info(self):
        #common.view.assert_gui_thread()

        # Get the entire buffer from the page's text widget
        buf = self.tw.get_text().strip()

        include_dirs = common.view.include_dirs

        # extract the target info
        return ope.get_targets(buf, include_dirs, ope_filename=self.filepath)

    def color(self, reporterror=True, eraseall=False):
        try:
            # Get the text from the code buffer
            buf = self.tw.get_text()

            # compute the variable dictionary
            include_dirs = common.view.include_dirs

            # check the file
            self.logger.debug("Parsing OPE file.")
            res = ope.check_ope(buf, include_dirs=include_dirs)

            if len(res.prm_errmsg_list) > 0:
                errmsg = '\n'.join(res.prm_errmsg_list)
                common.view.statusMsg(errmsg)
                if reporterror:
                    common.view.popup_error(errmsg)
                for errmsg in res.prm_errmsg_list:
                    self.logger.error(errmsg)

            # store away our variable dictionary for future reference
            self.varDict = res.vardict

            tags = common.decorative_tags + common.execution_tags

            if eraseall:
                removetags = tags
            else:
                removetags = common.decorative_tags

            # Get "Tags" page
            tagpage = common.view.tagpage
            # TODO: what if user closed Tags page?

            # Remove everything from the tag buffer
            self.logger.debug("Preparing tags.")
            tagpage.initialize(self)

            # remove decorative tags
            for tag, bnch in removetags:
                try:
                    if self.tw.has_tag(tag):
                        self.tw.remove_tag_def(tag)
                except Exception:
                    # tag may not exist--that's ok
                    pass

            # add tags back in
            for tag, bnch in tags:
                properties = {}
                properties.update(bnch)
                try:
                    self.tw.create_tag(tag, **properties)
                except Exception:
                    # tag may already exist--that's ok
                    pass

                try:
                    tagpage.addtag(tag, **properties)
                except Exception:
                    # tag may already exist--that's ok
                    pass

            # Update the tag coloring and the tag list.  Syntax highlighting
            # is done entirely through the tag table (the same mechanism used
            # for execution marking), driven by the OPE parser results.
            self.logger.debug("Coloring tags.")
            start, end = self.tw.get_ref_bounds()

            # Line-level tags (comment1/comment2/comment3) applied to the
            # whole line.
            for bnch in res.taglist:
                lineno = bnch.lineno - 1
                # apply desired tags to entire line in main text buffer
                start.set_line(lineno)
                end.set_line(lineno)
                end.to_line_end()

                for tag in bnch.tags:
                    self.tw.apply_tag(tag, start, end)

                tagpage.add_mapping(lineno, bnch.text, bnch.tags)

            # Character-level tags for variable references: 'varref' for every
            # $VAR, plus 'badref' overlaid where the reference is undefined.
            # bnch.start/bnch.end are column offsets within the line.
            self.logger.debug("Coloring refs.")
            for bnch in res.reflist:
                lineno = bnch.lineno - 1
                start.set_line(lineno)
                base = start.get_offset()
                start.set_offset(base + bnch.start)
                end.set_offset(base + bnch.end)

                self.tw.apply_tag('varref', start, end)
                if bnch.varref in res.badset:
                    self.tw.apply_tag('badref', start, end)

            self.logger.debug("Summarizing.")
            common.view.statusMsg('')
            errlst = []
            if len(res.badset) > 0:
                # Add all undefined refs to the tag table
                errline = tagpage.get_end_lineno()
                tagpage.add_mapping(1, "UNDEFINED VARIABLE REFS", ['badref'])
                for bnch in res.badlist:
                    tagpage.add_mapping(bnch.lineno, "%s: line %d" % (
                        bnch.varref, bnch.lineno), ['badref'])

                errmsg = "Undefined variable references: " + \
                         ' '.join(res.badset)
                errlst.append(errmsg)

                # scroll tag table to errors
                tagpage.scroll_to_lineno(errline)

            if len(res.badcoords) > 0:
                # Add all bad coords to the tag table
                errline = tagpage.get_end_lineno()
                tagpage.add_mapping(1, "POSSIBLE BAD COORDINATES", ['badref'])
                for bnch in res.badcoords:
                    tagpage.add_mapping(bnch.lineno, "line %d: %s" % (
                        bnch.lineno, bnch.errstr), ['badref'])

                errmsg = "Possible bad RA/DEC coordinates."
                errlst.append(errmsg)

                # scroll tag table to errors
                tagpage.scroll_to_lineno(errline)

            if len(errlst) > 0:
                errlst.append("See bottom of tags for details.")
                errmsg = '; '.join(errlst)
                if reporterror:
                    common.view.raise_page('tags')
                    common.view.popup_error(errmsg)
                else:
                    common.view.statusMsg(errmsg)

                # TODO: turn tab background to orange on Tags page
                #tagpage.tablbl.set_markup('<span background="orange">Tags</span>')

            else:
                # TODO: turn tab background to clear on Tags page
                #tagpage.tablbl.set_markup('<span>Tags</span>')
                pass


        except Exception as e:
            errmsg = "Error coloring buffer: %s" % (str(e))
            self.logger.error(errmsg)
            common.view.statusMsg(errmsg)
            if reporterror:
                common.view.popup_error(errmsg)


    def focus_in(self, w, evt):
        self.logger.debug("got focus!")
        self.color(reporterror=False)
        return False

    def current(self):
        """Scroll to the current position in the buffer.  The current
        position is determined by the execution mark (if any), otherwise
        by the first execution-related tag found.
        """

        # Try to find the execution mark ('executing' or 'error') and
        # scroll to it.  These are anchored by named refs (see
        # OpeCommandObject._set_exec_mark).
        for name in ('executing', 'error'):
            ref = self.tw.get_named_ref(name)
            if ref is not None and ref.is_valid():
                self.scroll_to_lineno(ref.get_line())
                return

        # If we can't find a mark then look for tags
        for tag in ('executing', 'queued', 'error', 'done'):
            try:
                start, end = common.get_region(self.tw, tag)
                self.scroll_to_lineno(start.get_line())
                return

            except common.TagError:
                continue

        #common.view.popup_error("Sorry, cannot find any region of interest.")


    def reset(self):
        common.clear_tags(self.tw, ('executing',))
        self._clear_exec_marks()
        # this will reset Pause button, etc.
        super().reset()

    def _mark_icon(self, name):
        """Lazily load and cache the gutter icon image for an execution
        mark name ('executing' or 'error').  Returns a QImage or None."""
        if not hasattr(self, '_mark_icons'):
            self._mark_icons = {}
        if name not in self._mark_icons:
            from qtpy.QtGui import QImage
            fname = {'executing': 'apple-green.png',
                     'error': 'apple-red.png'}.get(name)
            img = None
            if fname is not None:
                img = QImage(os.path.join(icondir, fname))
                img = None if img.isNull() else img.scaledToHeight(16)
            self._mark_icons[name] = img
        return self._mark_icons[name]

    def _set_exec_mark(self, name, ref):
        """Show the single execution gutter mark ('executing' or 'error')
        on the line containing ``ref``, replacing any previous mark.  The
        mark is anchored by a named ref so it follows edits and can be
        located by current()."""
        self._clear_exec_marks()
        marker = self.tw.create_named_ref(name, ref.get_offset())
        img = self._mark_icon(name)
        if img is not None:
            self.tw.set_icon(marker, img)

    def _clear_exec_marks(self):
        """Remove any execution gutter marks and their anchoring refs."""
        self.tw.clear_icons()
        for name in ('executing', 'error'):
            self.tw.remove_named_ref(name)

    def query_vardef(self, widget, res, line_no, pos_in_line, text):
        # parameters are text widget, x and y coords, boolean for keyboard
        # mode (?) and the tooltip widget.  If a tooltip should be
        # displayed, then append a string to `res`
        #print(line_no, pos_in_line, text)
        if len(text) == 0:
            return

        # Get the text of the varref
        i = pos_in_line
        if i >= len(text):
            return
        while i >= 0:
            if text[i] == '$':
                break
            i -= 1
        i = max(0, i)

        if text[i] != '$':
            return

        j = pos_in_line
        while j < len(text):
            cur_word = text[i:j]
            if re.match(r"^\$[\w\d_]+$", cur_word):
                j += 1
                continue
            j -= 1
            break

        varname = text[i:j]
        self.logger.debug(f"{varname=}")
        if not re.match(r"^\$[\w\d_]+$", varname):
            return
        # strip off leading $
        varname = varname[1:]

        try:
            text = self.get_vardef(varname)
            res.append(text)
        except Exception as e:
            pass

        return True

    def copy(self):
        # A hack to get around accidentally copying rich text tags along
        # with the text

        # Get the selection.  If there is none, we're done.
        bounds = self.tw.get_selection_bounds()
        if bounds is None:
            return

        # Set the clipboard to the plain ASCII text
        start, end = bounds
        text = self.tw.get_text_range(start, end)
        common.view.clipboard.set_text(text, -1)


    def keypress(self, w, event):
        keyname = event.key

        if 'ctrl' in event.modifiers:
            if keyname == 't':
                common.view.raise_page('tags')
                return True

            elif keyname == 'r':
                self.color()
                return True

            ## elif keyname == 'e':
            ##     self.color(eraseall=True)
            ##     return True

            elif keyname == 'l':
                self.current()
                return True

            elif keyname == 'q':
                common.view.raise_page('queues')
                return True

            elif keyname == 'h':
                common.view.raise_page('handset')
                return True

            elif keyname == 'c':
                self.copy()
                return True

            elif keyname == 'f':
                self.find()
                return True

        return False


    def process_cmdstr(self, txtbuf, cmdstr):
        cmdstr = cmdstr.strip()

        # remove trailing semicolon, if present
        if cmdstr.endswith(';'):
            cmdstr = cmdstr[:-1]

        # Resolve all variables/macros
        try:
            self.logger.debug("Unprocessed command is: %s" % cmdstr)
            include_dirs = common.view.include_dirs
            p_cmdstr = ope.getCmd(txtbuf, cmdstr, include_dirs)
            self.logger.debug("Processed command is: %s" % p_cmdstr)

            return p_cmdstr

        except Exception as e:
            errstr = "Error parsing command: %s" % (str(e))
            raise Exception(errstr)


    def _convert_linked_commands(self, tags):
        """Takes a set of command tags, as may be found in our text buffer,
        and converts any queued instance of it to a new SimpleCommandObject
        (which contains the expanded command string) and that is not linked
        to this page.
        """

        # Get current value of text buffer
        txtbuf = self.tw.get_text()

        # Get all the commands strings referenced by _tags_ and put
        # them in dict _cmds_
        cmds = {}
        for tag in tags:
            # Now get the command from the text widget
            start, end = common.get_region_lines(self.tw, tag)
            cmds[tag] = self.tw.get_text_range(start, end)

        # Define a mapping
        # NOTE: enclosed function captures values of tags, cmds and
        #   txtbuf
        def f(cmdObj):
            tag = str(cmdObj)
            if not (tag in tags):
                return cmdObj

            cmdstr = self.process_cmdstr(txtbuf, cmds[tag])
            return CommandObject.SimpleCommandObject('cp%d', self.queueName,
                                                     self.logger,
                                                     cmdstr)

        # This function just iterates over all current queues, applying
        # the mapping function
        def g():
            for queueObj in common.controller.queue.values():
                queueObj.mapFilter(f)

        # Execute this as a thread in the controller
        common.controller.ctl_do(g)


    def _get_commands_from_selection(self, copytext=None):

        if copytext == None:
            copytext = self.add_frozen

        if copytext:
            # If copytext==True then we are not storing a reference
            # to the command in the page, but the command string
            # already pre-expanded
            txtbuf = self.tw.get_text()

        # Get the range of text selected
        bounds = self.tw.get_selection_bounds()
        if bounds is None:
            raise common.SelectionError("Error getting selection--no selection?")
        first, last = bounds

        frow = first.get_line()
        lrow = last.get_line()
        if last.get_line_column()[1] == 0:
            # Hack to fix problem where selection covers the newline
            # but not the first character of the next line
            lrow -= 1
        #print("selection: %d-%d" % (frow, lrow))

        # Clear the selection (programmatic clears don't fire cursor_moved)
        common.clear_selection(self.tw)
        self._update_button_states()

        # Break selection into individual lines
        cmds = []

        for i in range(int(lrow)+1-frow):

            row = frow+i
            #print("row: %d" % (row))

            first.set_line(row)
            last.set_line(row)
            last.to_line_end()
            cmd = self.tw.get_text_range(first, last).strip()
            self.logger.debug("cmd=%s" % (cmd))
            if (len(cmd) == 0) or cmd.startswith('#'):
                # TODO: linked comments
                cmdobj = CommandObject.CommentCommandObject('cm%d',
                                                            self.queueName,
                                                            self.logger, cmd)

            elif copytext:
                cmdstr = self.process_cmdstr(txtbuf, cmd)
                cmdobj = CommandObject.SimpleCommandObject('cp%d',
                                                           self.queueName,
                                                           self.logger, cmdstr)
            else:
                # tag the text so we can manipulate it later
                cmdobj = OpeCommandObject('ope%d', self.queueName,
                                          self.logger, self)
                tag = cmdobj.guitag
                self.tw.create_tag(tag)
                self.tw.apply_tag(tag, first, last)

            cmds.append(cmdobj)

        return cmds


    def execute(self, copytext=None):
        """Callback when the EXEC button is pressed.
        """
        # Check whether we are busy executing a command here
        if common.controller.executingP.isSet():
            # Yep--popup an error message
            common.view.popup_error("There is already a %s task running!" % (
                self.tm_queueName))
            return

        # Get length of queued items, if any
        queue = common.controller.queue[self.queueName]
        num_queued = len(queue)

        settings = common.view.get_settings()
        suppress_confirm_exec = settings.get('suppress_confirm_exec', True)

        if not self.tw.has_selection():
            # No selection.  See if there are previously queued commands
            if num_queued == 0:
                common.view.popup_error("No mouse selection and no %s queued commands!" % (
                    self.queueName))
            else:
                #------------------
                def _execute_1(res):
                    if res != 'yes':
                        return
                    common.controller.execQueue(self.queueName,
                                                tm_queueName=self.tm_queueName)
                #------------------

                if suppress_confirm_exec:
                    _execute_1('yes')
                else:
                    common.view.popup_confirm("Confirm execute",
                                              "No selection--resume execution of %s queued commands?" % (
                        self.queueName),
                                              _execute_1)

            return

        #------------------
        # Code to do if we have a selection
        def _execute_2(w, rsp):
            try:
                cmds = self._get_commands_from_selection(copytext=copytext)

                if rsp == 1:
                    cmdobj = CommandObject.BreakCommandObject('brk%d',
                                                              self.queueName,
                                                              self.logger, self)
                    queue.prepend(cmdobj)
                    queue.insert(0, cmds)
                    common.controller.execQueue(self.queueName,
                                                tm_queueName=self.tm_queueName)
                elif rsp == 2:
                    queue.insert(0, cmds)
                elif rsp == 3:
                    queue.extend(cmds)
                elif rsp == 4:
                    queue.replace(cmds)
                    common.controller.execQueue(self.queueName,
                                                tm_queueName=self.tm_queueName)

            except Exception as e:
                common.view.popup_error(str(e))
            return True

        #------------------

        # <== There is a selection
        if num_queued > 0:
            if suppress_confirm_exec:
                #_execute_2(None, 1)
                _execute_2(None, 4)
            else:
                self.queued_check(_execute_2)

        else:
            _execute_2(None, 4)


    def insert(self, loc=None, copytext=None):
        """Callback when the APPEND button is pressed.
        """
        if not self.tw.has_selection():
            # No selection.
            common.view.popup_error("No mouse selection!")
            return

        try:
            cmds = self._get_commands_from_selection(copytext=copytext)
            #print(len(cmds), "selected!")

            queue = common.controller.queue[self.queueName]
            if loc == None:
                queue.extend(cmds)
            else:
                queue.insert(loc, cmds)
        except Exception as e:
            common.view.popup_error(str(e))

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
        common.view.add_window(dialog)
        dialog.show()

    def attach_queue_res(self, w, rsp, cbox, names):
        queueName = names[cbox.get_index()].strip().lower()
        common.view.remove_window(w)
        w.delete()
        if rsp == 1:
            if queueName not in common.view.queue:
                common.view.popup_error("No queue with that name exists!")
                return True
            self.queueName = queueName
        return True


class OpeCommandObject(CommandObject.CommandObject):

    def __init__(self, format, queueName, logger, opepage):
        self.page = opepage

        super().__init__(format, queueName, logger)


    def get_preview(self):
        """This is called to get a preview of the command string that
        should be executed.
        """
        common.view.assert_gui_thread()

        # Get the command from the page's text widget
        tw = self.page.tw
        start, end = common.get_region_lines(tw, self.guitag)
        cmdstr = tw.get_text_range(start, end).strip()

        # remove trailing semicolon, if present
        if cmdstr.endswith(';'):
            cmdstr = cmdstr[:-1]

        self.logger.debug("preview is '%s'" % (cmdstr))
        return '>>' + cmdstr

    def _get_cmdstr(self):
        """This is called to get the command string that should be executed.
        """
        common.view.assert_gui_thread()

        # Get the entire buffer from the page's text widget
        tw = self.page.tw
        txtbuf = tw.get_text()

        # Now get the command from the text widget
        start, end = common.get_region_lines(tw, self.guitag)
        cmdstr = tw.get_text_range(start, end)

        return (txtbuf, cmdstr)

    def get_cmdstr(self):
        common.view.assert_nongui_thread()

        # Get the command string associated with this kind of page.
        # We are executing in another thread, so use gui_do_res()
        # to get the text
        f_res = common.gui_do_res(self._get_cmdstr)
        txtbuf, cmdstr = f_res.get_value(timeout=10.0)

        cmdstr = self.page.process_cmdstr(txtbuf, cmdstr)
        return cmdstr


    def _mark_status(self, txttag):
        """This is called when our command changes status.  _txttag_ should
        be one of unqueued, queued, normal, executing, done, error
        """
        common.view.assert_gui_thread()

        # Get the region of the OPE buffer for this command
        tw = self.page.tw
        start, end = common.get_region_lines(tw, self.guitag)

        if txttag == 'unqueued':
            common.clear_tags_region(tw, ('queued',),
                                     start, end)
            return

        if txttag == 'normal':
            common.clear_tags_region(tw, ('done', 'error', 'executing'),
                                     start, end)
            return

        if txttag == 'executing':
            common.clear_tags_region(tw, ('done', 'error'),
                                     start, end)
            # annotate line with executing gutter mark
            self.page._set_exec_mark('executing', start)

        elif txttag in ('done',):
            common.clear_tags_region(tw, ('executing',),
                                     start, end)
        elif txttag in ('error',):
            common.clear_tags_region(tw, ('executing',),
                                     start, end)
            # annotate line with error gutter mark
            self.page._set_exec_mark('error', start)

        tw.apply_tag(txttag, start, end)

    def mark_status(self, txttag):
        # This MAY be called from a non-gui thread
        common.gui_do(self._mark_status, txttag)


class OpeCommentCommandObject(CommandObject.CommandObject):

    def __init__(self, format, queueName, logger, opepage):
        self.page = opepage

        super().__init__(format,
                                                      queueName, logger)


    def get_preview(self):
        """This is called to get a preview of the command string that
        should be executed.
        """
        common.view.assert_gui_thread()

        # Get the comment from the page's text widget
        tw = self.page.tw
        start, end = common.get_region_lines(tw, self.guitag)
        comment = tw.get_text_range(start, end).strip()

        self.logger.debug("preview is '%s'" % (comment))
        return '>>' + comment

    def _get_cmdstr(self):
        return '== NOP =='

    def get_cmdstr(self):
        return '== NOP =='

    def mark_status(self, txttag):
        pass
