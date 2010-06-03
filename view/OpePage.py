# 
#[ Eric Jeschke (eric@naoj.org) --
#  Last edit: Tue May 18 16:59:14 HST 2010
#]

import os
import gtk

import common
import CodePage


class OpePage(CodePage.CodePage):

    def __init__(self, frame, name, title):

        super(OpePage, self).__init__(frame, name, title)

        self.queueName = 'executer'
        self.block = False

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

        # add some bottom buttons
        self.btn_exec = gtk.Button("Exec")
        self.btn_exec.connect("clicked", lambda w: common.view.execute(self))
        self.btn_exec.show()
        self.leftbtns.pack_end(self.btn_exec)

        self.btn_cancel = gtk.Button("Cancel")
        self.btn_cancel.connect("clicked", lambda w: self.cancel())
        self.btn_cancel.show()
        self.leftbtns.pack_end(self.btn_cancel)

        self.btn_kill = gtk.Button("Kill")
        self.btn_kill.connect("clicked", lambda w: self.kill())
        self.btn_kill.show()
        self.leftbtns.pack_end(self.btn_kill)

        self.btn_pause = gtk.ToggleButton("Pause")
        self.btn_pause.connect("toggled", self.toggle_pause)
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
        if w.get_active():
            self.hbox.set_position(250)
        else:
            self.hbox.set_position(0)
        
    def color(self):

        self.tags = common.decorative_tags + common.execution_tags

        # Remove everything from the tag buffer
        start, end = self.tagbuf.get_bounds()
        self.tagbuf.delete(start, end)

        # Get the text from the code buffer
        start, end = self.buf.get_bounds()
        buf = self.buf.get_text(start, end)

        self.tagidx = {}

        def addtags(lineno, line, tags):
            start.set_line(lineno)
            end.set_line(lineno)
            end.forward_to_line_end()

            for tag in tags:
                self.buf.apply_tag_by_name(tag, start, end)

            # Add this line and a tag to the tags buffer
            tend = self.tagbuf.get_end_iter()
            taglineno = tend.get_line()
            self.tagbuf.insert_with_tags_by_name(tend, line+'\n',
                                                 *(tags + [tag]))
            # make an entry in the tags index
            self.tagidx[taglineno] = lineno

        try:
            for tag, bnch in self.tags:
                properties = {}
                properties.update(bnch)
                self.buf.create_tag(tag, **properties)
                self.tagbuf.create_tag(tag, **properties)

        except:
            # in case they've been created already
            pass

        lineno = 0
        for line in buf.split('\n'):
            line = line.strip()
            if line.startswith('###'):
                addtags(lineno, line, ['comment3'])
        
            elif line.startswith('##'):
                addtags(lineno, line, ['comment2'])
        
            elif line.startswith('#'):
                addtags(lineno, line, ['comment1'])

            lineno += 1


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
        print "line->%d res=%s" % (lineno, res)
            

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
