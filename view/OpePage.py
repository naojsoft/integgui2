# 
#[ Eric Jeschke (eric@naoj.org) --
#  Last edit: Mon Jul 26 14:12:44 HST 2010
#]

import os, re
import gtk

import common
import Page, CodePage

import SOSS.parse.ope as ope

# regex for matching variable references
regex_varref = re.compile(r'^(.*?)(\$[\w_]+)(.*)$')


class OpePage(CodePage.CodePage, Page.CommandPage):

    def __init__(self, frame, name, title):

        super(OpePage, self).__init__(frame, name, title)

        self.queueName = 'executer'
        self.paused = False

        self.varDict = {}

        # Create the widgets for the tag buffer text
        scrolled_window = gtk.ScrolledWindow()
        scrolled_window.set_border_width(2)

        scrolled_window.set_policy(gtk.POLICY_AUTOMATIC,
                                   gtk.POLICY_AUTOMATIC)

        tw = gtk.TextView()
        scrolled_window.add(tw)
        tw.show()
        scrolled_window.show()

        tw.set_editable(False)
        tw.set_wrap_mode(gtk.WRAP_NONE)
        tw.set_left_margin(2)
        tw.set_right_margin(2)
        tw.connect("button-press-event", self.jump_tag)

        self.tagtw = tw
        self.tagbuf = tw.get_buffer()
        self.tagidx = {}
        # hack to get auto-scrolling to work
        self.mark = self.buf.create_mark('end', self.buf.get_end_iter(),
                                         False)

        self.hbox.pack1(scrolled_window, resize=False, shrink=True)
        self.hbox.set_position(0)

        # this is for variable definition popups
        self.tw.set_property("has-tooltip", True)
        self.tw.connect("query-tooltip", self.query_vardef)

        # keyboard shortcuts
        self.tw.connect("key-press-event", self.keypress)

        # add some bottom buttons
        self.btn_exec = gtk.Button("Exec")
        self.btn_exec.connect("clicked", lambda w: common.view.execute(self))
        self.btn_exec.modify_bg(gtk.STATE_NORMAL,
                                common.launcher_colors['execbtn'])
        self.btn_exec.show()
        self.leftbtns.pack_end(self.btn_exec)

        self.btn_sched = gtk.Button("Schedule")
        self.btn_sched.connect("clicked", lambda w: common.view.schedule(self))
        self.btn_sched.show()
        self.leftbtns.pack_end(self.btn_sched)

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

        self.btn_tags = gtk.ToggleButton("Tags")
        self.btn_tags.connect("toggled", self.toggle_tags)
        self.btn_tags.show()
        self.leftbtns.pack_end(self.btn_tags)

        # Add items to the menu
        item = gtk.MenuItem(label="Recolor")
        self.menu.append(item)
        item.connect_object ("activate", lambda w: self.color(),
                             "menu.Recolor")
        item.show()

        item = gtk.MenuItem(label="Current")
        self.menu.append(item)
        item.connect_object ("activate", lambda w: self.current(),
                             "menu.Current")
        item.show()

        item = gtk.MenuItem(label="Clear Schedule")
        self.menu.append(item)
        item.connect_object ("activate", lambda w: common.view.clear_queued_tags(self, ['scheduled']),
                             "menu.Clear_Scheduled")
        item.show()

    def load(self, filepath, buf):
        super(OpePage, self).load(filepath, buf)
        self.cond_color()

    def reload(self):
        super(OpePage, self).reload()
        self.cond_color()

    def cond_color(self):
        name, ext = os.path.splitext(self.filepath)
        ext = ext.lower()

        if ext in ('.ope', '.cd'):
            self.color()

    def showtags(self):
        self.btn_tags.set_active(True)
        
    def hidetags(self):
        self.btn_tags.set_active(False)
        
    def toggle_tags(self, w):
        print "Toggled!"
        #common.view.playSound(common.sound.tags_toggle)
        if w.get_active():
            self.hbox.set_position(250)
        else:
            self.hbox.set_position(0)

    def get_vardef(self, varname):
        try:
            return self.varDict[varname]
        except KeyError:
            raise Exception("No definition found for '%s'" % varname)
        
    def color(self):

        self.tags = common.decorative_tags + common.execution_tags

        # Remove everything from the tag buffer
        start, end = self.tagbuf.get_bounds()
        self.tagbuf.delete(start, end)

        # Get the text from the code buffer
        start, end = self.buf.get_bounds()
        buf = self.buf.get_text(start, end)

        # compute the variable dictionary
        self.varDict = ope.get_vars_ope(buf)

        badrefs = set([])
        badtags = []
        self.tagidx = {}

        # remove decorative tags
        for tag, bnch in common.decorative_tags:
            try:
                self.buf.remove_tag_by_name(tag, start, end)
            except:
                # tag may not exist--that's ok
                pass

        # add tags back in
        for tag, bnch in self.tags:
            properties = {}
            properties.update(bnch)
            try:
                self.buf.create_tag(tag, **properties)
            except:
                # tag may already exist--that's ok
                pass
            try:
                self.tagbuf.create_tag(tag, **properties)
            except:
                # tag may already exist--that's ok
                pass

        def addbadtag(lineno, line, tags):
            # Add this line and a tag to the tags buffer
            tend = self.tagbuf.get_end_iter()
            taglineno = tend.get_line()
##             self.tagbuf.insert_with_tags_by_name(tend, line+'\n',
##                                                  *(tags + [tag]))
            self.tagbuf.insert_with_tags_by_name(tend, line+'\n', *tags)
            # make an entry in the tags index
            self.tagidx[taglineno] = lineno

        def addtags(lineno, line, tags):
            # apply desired tags to entire line in main text buffer
            start.set_line(lineno)
            end.set_line(lineno)
            end.forward_to_line_end()

            for tag in tags:
                self.buf.apply_tag_by_name(tag, start, end)

            addbadtag(lineno, line, tags)

        def addvarrefs(lineno, line):
            # apply desired tags to varrefs in this line in main text buffer

            offset = 0
            match = regex_varref.match(line)
            while match:
                pfx, varref, sfx = match.groups()
                varref = varref.upper()
                start.set_line(lineno)
                offset += len(pfx)
                start.forward_chars(offset)
                end.set_line(lineno)
                offset += len(varref)
                end.forward_chars(offset)

                self.buf.apply_tag_by_name('varref', start, end)
                try:
                    res = self.get_vardef(varref[1:])
                except Exception, e:
                    self.buf.apply_tag_by_name('badref', start, end)
                    badrefs.add(varref)
                    badtags.append((varref, lineno))

                match = regex_varref.match(sfx)
                
        lineno = 0
        for line in buf.split('\n'):
            line = line.strip()
            if line.startswith('###'):
                addtags(lineno, line, ['comment3'])
        
            elif line.startswith('##'):
                addtags(lineno, line, ['comment2'])
        
            elif line.startswith('#'):
                addtags(lineno, line, ['comment1'])

            else:
                addvarrefs(lineno, line)

            lineno += 1

        if len(badrefs) > 0:
            addbadtag(1, "UNDEFINED VARIABLE REFS", ['badref'])
            for varref, lineno in badtags:
                addbadtag(lineno, "%s: line %d" % (varref, lineno), ['badref'])
            
            common.view.popup_error("Undefined variable references: " +
                                    ' '.join(badrefs) + ". See bottom of tags for details.")
            


    def jump_tag(self, w, evt):
        widget = self.tagtw
        win = gtk.TEXT_WINDOW_TEXT
        buf_x1, buf_y1 = widget.window_to_buffer_coords(win, evt.x, evt.y)
        (startiter, coord) = widget.get_line_at_y(buf_y1)
        taglineno = startiter.get_line()
        try:
            lineno = self.tagidx[taglineno]
        except KeyError:
            return

        loc = self.buf.get_start_iter()
        loc.set_line(lineno)
        self.buf.move_mark(self.mark, loc)
        #res = self.tw.scroll_to_iter(loc, 0.5)
        res = self.tw.scroll_to_mark(self.mark, 0.2)
        if not res:
            res = self.tw.scroll_mark_onscreen(self.mark)
        #print "line->%d res=%s" % (lineno, res)
            

    def current(self):
        """Scroll to the current position in the buffer.  The current
        poistion is determined by the first tag found, otherwise it
        just scrolls to the mark position.
        """
        # TODO: might be lots of tags of 'error' and 'done' in the buffer
        # It might be better to scroll to the mark than these tags
        for tag in ('executing', 'scheduled', 'error', 'done'):
            try:
                start, end = common.get_region(self.buf, tag)
                
                self.buf.move_mark(self.mark, start)
                res = self.tw.scroll_to_mark(self.mark, 0.2)
                if not res:
                    res = self.tw.scroll_mark_onscreen(self.mark)

                return

            except common.TagError:
                continue

        #common.view.popup_error("Sorry, cannot find any region of interest.")
        # Scroll to mark, if any
        res = self.tw.scroll_mark_onscreen(self.mark)


    def reset(self):
        common.clear_tags(self.buf, ('executing',))
        self.reset_pause()

    def query_vardef(self, tw, x, y, kbmode, ttw):
        # parameters are text widget, x and y coords, boolean for keyboard
        # mode (?) and the tooltip widget.  Return True if a tooltip should
        # be displayed
        #print "tooltip: args are %s" % (str(args))
        buf_x1, buf_y1 = tw.window_to_buffer_coords(gtk.TEXT_WINDOW_TEXT,
                                                    x, y)
        txtiter = tw.get_iter_at_location(buf_x1, buf_y1)

        buf = tw.get_buffer()
        tagtbl = buf.get_tag_table()
        varref = tagtbl.lookup('varref')
        
        # Check if we are in the middle of a varref
        result = txtiter.has_tag(varref)
        if not result:
            #print "tooltip: not in word!"
            return False

        # Get boundaries of the tag.
        # TODO: there must be a more efficient way to do this!
        startiter = txtiter.copy()
        while not startiter.begins_tag(varref):
            startiter.backward_char()

        enditer = txtiter.copy()
        while not enditer.ends_tag(varref):
            enditer.forward_char()

        # Get the text of the varref
        varname = buf.get_text(startiter, enditer)
        varname = varname[1:]
        try:
            res = self.get_vardef(varname)
            ttw.set_text(res)
        except Exception, e:
            ttw.set_text(str(e))
            
        return True

    def keypress(self, w, event):
        keyname = gtk.gdk.keyval_name(event.keyval)
        #print "key pressed --> %s" % keyname

        if event.state & gtk.gdk.CONTROL_MASK:
            if keyname == 't':
                self.btn_tags.set_active(not self.btn_tags.get_active())
                return True
        
            elif keyname == 'r':
                self.color()
                return True
        
        return False
    
#END
