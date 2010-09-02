# 
#[ Eric Jeschke (eric@naoj.org) --
#  Last edit: Tue Aug 31 15:28:56 HST 2010
#]

# remove once we're certified on python 2.6
from __future__ import with_statement

import os, re
import gtk

import Bunch

import common
import Page
import CommandObject


class QueuePage(Page.CommandPage):

    def __init__(self, frame, name, title):

        super(QueuePage, self).__init__(frame, name, title)

        self.paused = False

        self.queue = []
        self.queueName = ''
        self.cmdDict = {}

        # Create the widgets for the text
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
        tw.set_left_margin(4)
        tw.set_right_margin(4)

        self.tw = tw
        self.buf = tw.get_buffer()

        self.buf.create_tag('cmdref', foreground="black")

        frame.pack_start(scrolled_window, fill=True, expand=True)

        self.add_menu()
        self.add_close()

        #self.tw.connect("button-press-event", self.jump_tag)

        # hack to get auto-scrolling to work
        self.mark = self.buf.create_mark('end', self.buf.get_end_iter(),
                                         False)

        # this is for variable definition popups
        #self.tw.set_property("has-tooltip", True)
        #self.tw.connect("query-tooltip", self.query_command)
        # self.tw.drag_source_set(gtk.gdk.BUTTON1_MASK,
        #                       [('text/cmdtag', 0, 555)], gtk.gdk.ACTION_MOVE)
        # self.tw.drag_dest_set(gtk.DEST_DEFAULT_ALL,
        #                       [('text/cmdtag', 0, 555)], gtk.gdk.ACTION_MOVE)
        self.tw.connect("drag-data-get", self.grabdata)
        self.tw.connect("drag-drop", self.rearrange)

        # keyboard shortcuts
        #self.tw.connect("key-press-event", self.keypress)

        # add some bottom buttons
        self.btn_exec = gtk.Button("Exec")
        self.btn_exec.connect("clicked", lambda w: common.view.execute(self))
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

        self.btn_refresh = gtk.Button("Refresh")
        self.btn_refresh.connect("clicked", lambda w: self.redraw())
        self.btn_refresh.show()
        self.leftbtns.pack_end(self.btn_refresh)

        item = gtk.MenuItem(label="Clear Schedule")
        self.menu.append(item)
        item.connect_object ("activate", lambda w: common.controller.clearQueue(self.queueName),
                             "menu.Clear_Scheduled")
        item.show()

    def set_queue(self, queueName, queueObj):
        self.queueName = queueName
        self.queueObj = queueObj
        # Hmmm...asking for GC troubles?
        queueObj.add_view(self)
        
        # change our tab title to match the queue
        self.setLabel(queueObj.name)

    def redraw(self):
        # clear text
        common.clear_tv(self.tw)
        with self.lock:
            for cmdObj in self.queueObj.peekAll():
                text = cmdObj.get_preview()
                # Insert text icon at end of the 
                loc = self.buf.get_end_iter()
                self.buf.insert_with_tags_by_name(loc, text, 'cmdref')
                loc = self.buf.get_end_iter()
                self.buf.insert(loc, '\n')

    def get_cmddef(self, cmdtag):
        try:
            #return self.cmdDict[cmdtag]
            return cmdtag
        except KeyError:
            raise Exception("No definition found for '%s'" % cmdtag)
        
    def reset(self):
        #common.clear_tags(self.buf, ('executing',))
        self.reset_pause()

    def query_command(self, tw, x, y, kbmode, ttw):
        # parameters are text widget, x and y coords, boolean for keyboard
        # mode (?) and the tooltip widget.  Return True if a tooltip should
        # be displayed
        #print "tooltip: args are %s" % (str(args))
        buf_x1, buf_y1 = tw.window_to_buffer_coords(gtk.TEXT_WINDOW_TEXT,
                                                    x, y)
        txtiter = tw.get_iter_at_location(buf_x1, buf_y1)

        buf = tw.get_buffer()
        tagtbl = buf.get_tag_table()
        cmdref = tagtbl.lookup('cmdref')
        if not cmdref:
            return False
        
        # Check if we are in the middle of a cmdref
        result = txtiter.has_tag(cmdref)
        if not result:
            #print "tooltip: not in word!"
            return False

        # Get boundaries of the tag.
        # TODO: there must be a more efficient way to do this!
        startiter = txtiter.copy()
        while not startiter.begins_tag(cmdref):
            startiter.backward_char()

        enditer = txtiter.copy()
        while not enditer.ends_tag(cmdref):
            enditer.forward_char()

        # Get the text of the cmdref
        cmdtag = buf.get_text(startiter, enditer)
        #cmdtag = cmdtag[1:]
        try:
            res = self.get_cmddef(cmdtag)
            ttw.set_text(res)
        except Exception, e:
            ttw.set_text(str(e))
            
        return True

    def keypress(self, w, event):
        keyname = gtk.gdk.keyval_name(event.keyval)
        print "key pressed --> %s" % keyname

        return False
    
    def grabdata(self, tw, context, selection, info, tstamp):
        print "grabbing!"
        return True
    
    def rearrange(self, tw, context, x, y, tstamp):
        print "rearrange!"
        buf_x1, buf_y1 = tw.window_to_buffer_coords(gtk.TEXT_WINDOW_TEXT,
                                                    x, y)
        txtiter = tw.get_iter_at_location(buf_x1, buf_y1)

        print "Drop!"
        print '\n'.join([str(t) for t in context.targets])
        context.finish(True, False, tstamp)
        return True
    
class altQueuePage(Page.CommandPage):

    def __init__(self, frame, name, title):

        super(QueuePage, self).__init__(frame, name, title)

        self.paused = False

        self.queue = None
        self.cmdDict = {}

        # Create the widgets for the text
        scrolled_window = gtk.ScrolledWindow()
        scrolled_window.set_border_width(2)

        scrolled_window.set_policy(gtk.POLICY_AUTOMATIC,
                                   gtk.POLICY_AUTOMATIC)

        self.ls = gtk.ListStore(str)
        tvw = gtk.TreeView(self.ls)
        scrolled_window.add(tvw)
        scrolled_window.show()
        self.tvw = tvw

        targets = [ ('my_tree_model_row', gtk.TARGET_SAME_WIDGET, 0),
                    ('text/plain', 0, 1),
                    ('TEXT', 0, 2),
                    ('STRING', 0, 3)]
        self.cell = gtk.CellRendererText()
        self.tvc = gtk.TreeViewColumn('Commands', self.cell, text=0)
        #self.tvc.set_reorderable(True)
        self.tvw.append_column(self.tvc)
        #self.tvc.pack_start(self.cell, True)
        #self.tvc.add_attribute(self.cell, 'text', 0)
        self.tvw.set_search_column(0)
        self.tvw.set_reorderable(True)
        tvw.show()

        self.tvw.enable_model_drag_source(gtk.gdk.BUTTON1_MASK,
                                          targets,
                                          gtk.gdk.ACTION_DEFAULT|
                                          gtk.gdk.ACTION_MOVE)
        self.tvw.enable_model_drag_dest(targets,
                                        gtk.gdk.ACTION_DEFAULT)
        self.tvw.connect('drag_data_get', self.drag_data_get_data)
        self.tvw.connect('drag_data_received', self.drag_data_received_data)
        
        frame.pack_start(scrolled_window, fill=True, expand=True)
        #frame.show_all()

        self.add_menu()
        self.add_close()

        # this is for command definition popups
        self.tvw.set_property("has-tooltip", True)
        self.tvw.connect("query-tooltip", self.query_command)

        # add some bottom buttons
        self.btn_exec = gtk.Button("Exec")
        self.btn_exec.connect("clicked", lambda w: common.view.execute(self))
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

        item = gtk.MenuItem(label="Clear Schedule")
        self.menu.append(item)
        item.connect_object ("activate", lambda w: common.controller.clearQueue(self.queueName),
                             "menu.Clear_Scheduled")
        item.show()

    def set_queue(self, queueObj):
        self.queueObj = queueObj
        # change our tab title to match the queue
        self.setLabel(queueObj.name)

    def redraw(self, queueObj):
        # clear text
        common.clear_tv(self.tw)
        with self.lock:
            for bnch in queueObj.peekAll():
                text = bnch.tag
                # Insert text icon at end of the 
                loc = self.buf.get_end_iter()
                self.buf.insert_with_tags_by_name(loc, text, 'cmdref')
                loc = self.buf.get_end_iter()
                self.buf.insert(loc, '\n')

    def get_cmddef(self, cmdtag):
        try:
            #return self.cmdDict[cmdtag]
            return cmdtag
        except KeyError:
            raise Exception("No definition found for '%s'" % cmdtag)
        
    def reset(self):
        common.clear_tags(self.buf, ('executing',))
        self.reset_pause()

    def query_command(self, tvw, x, y, kbmode, ttw):
        # parameters are text widget, x and y coords, boolean for keyboard
        # mode (?) and the tooltip widget.  Return True if a tooltip should
        # be displayed
        #print "tooltip: args are %s" % (str(args))
        model = tvw.get_model()
        info = tvw.get_path_at_pos(x, y)
        if not info:
            return
        
        path = info[0]
        iter = model.get_iter(path)

        # Get the text of the cmdref
        cmdtag = model.get_value(iter, 0)
        #cmdtag = cmdtag[1:]
        try:
            res = self.get_cmddef(cmdtag)
            ttw.set_text(res)
        except Exception, e:
            ttw.set_text(str(e))
            
        return True

    def keypress(self, w, event):
        keyname = gtk.gdk.keyval_name(event.keyval)
        print "key pressed --> %s" % keyname

        return False
    
    def drag_data_get_data(self, treeview, context, selection, target_id,
                              etime):
        print "drag data get!"
        treeselection = treeview.get_selection()
        model, iter = treeselection.get_selected()
        data = model.get_value(iter, 0)
        selection.set(selection.target, 8, data)
        
    def drag_data_received_data(self, treeview, context, x, y, selection,
                                info, etime):
        print "drag data received!"
        model = treeview.get_model()
        data = selection.data
        drop_info = treeview.get_dest_row_at_pos(x, y)
        if drop_info:
            path, position = drop_info
            iter = model.get_iter(path)
            if (position == gtk.TREE_VIEW_DROP_BEFORE
                or position == gtk.TREE_VIEW_DROP_INTO_OR_BEFORE):
                model.insert_before(iter, [data])
            else:
                model.insert_after(iter, [data])
        else:
            model.append([data])
        if context.action == gtk.gdk.ACTION_MOVE:
            context.finish(True, True, etime)
        return


class BreakCommandObject(CommandObject.CommandObject):

    def __init__(self, format, queueName, page):
        self.page = page
        
        super(BreakCommandObject, self).__init__(format, queueName)

    def get_preview(self):
        return self.get_cmdstr()
    
    def get_cmdstr(self):
        return '== BREAK =='

    def mark_status(self, txttag):
        pass

#END
