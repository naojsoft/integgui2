# 
#[ Eric Jeschke (eric@naoj.org) --
#  Last edit: Thu May 13 22:41:48 HST 2010
#]

# remove once we're certified on python 2.6
from __future__ import with_statement

# Standard library imports
import sys, os, glob
import re, time
import threading, Queue
import logging

# Special library imports
import pygtk
pygtk.require('2.0')
import gtk, gobject

# SSD/Gen2 imports
import remoteObjects as ro
import Bunch
import ssdlog
import cfg.g2soss
#from cfg.INS import INSdata

# Local integgui2 imports
import fits, ope
import controller as igctrl

color_blue = '#cae1ff'     # pale blue
color_green = '#c1ffc1'     # pale green
color_yellow = '#fafad2'     # cream
#color_white = 'whitesmoke'
color_white = 'white'

color_bg = 'light grey'

# Define sounds used in IntegGUI
sound = Bunch.Bunch(success='doorbell.au',
                    failure='splat.au')


# Yuk...module-level variables
view = None
controller = None

def set_view(pview):
    global view
    view = pview

def set_controller(pcontroller):
    global controller
    controller = pcontroller


def update_line(buf, row, text, tags=None):
    """Update a line of the text widget _tw_, defined by _row_,
    with the value _val_.
    """
    start = buf.get_start_iter()
    start.set_line(row)
    end = start.copy()
    end.forward_to_line_end()
    
    buf.delete(start, end)
    if not tags:
        buf.insert(start, text)
    else:
        buf.insert_with_tags_by_name(start, text, *tags)

def change_text(page, tagname, **kwdargs):
    tag = page.tagtbl.lookup(tagname)
    if not tag:
        raise TagError("Tag not found: '%s'" % tagname)

    for key, val in kwdargs.items():
        tag.set_property(key,val)

    # Scroll the view to this area
    start, end = get_region(page.buf, tagname)
    page.tw.scroll_to_iter(start, 0.1)


def get_region(txtbuf, tagname):
    """Returns a (start, end) pair of Gtk text buffer iterators
    associated with this tag.
    """
    # Painfully inefficient and error-prone way to locate a tagged
    # region.  Seems gtk text buffers have tags, but no good way to
    # manipulate text associated with them efficiently.

    # Get the tag table associated with this text buffer
    tagtbl = txtbuf.get_tag_table()
    # Look up the tag
    tag = tagtbl.lookup(tagname)

    # Get text iters at beginning and end of buffer
    start, end = txtbuf.get_bounds()

    # Now search forward from beginning for first location of this
    # tag, and backwards from the end
    result = start.forward_to_tag_toggle(tag)
    if not result:
        raise TagError("Tag not found: '%s'" % tagname)
    result = end.backward_to_tag_toggle(tag)
    if not result:
        raise TagError("Tag not found: '%s'" % tagname)

    return (start, end)


def replace_text(page, tagname, textstr):
    txtbuf = page.buf
    start, end = get_region(txtbuf, tagname)
    txtbuf.delete(start, end)
    txtbuf.insert_with_tags_by_name(start, textstr, tagname)

    # Scroll the view to this area
    page.tw.scroll_to_iter(start, 0.1)


class FileSelection(object):
    
    # Get the selected filename and print it to the console
    def file_ok_sel(self, w):
        filepath = self.filew.get_filename()
        self.close(w)
        self.callfn(filepath)

    def __init__(self):
        # Create a new file selection widget
        self.filew = gtk.FileSelection("Select a file")
        self.filew.connect("destroy", self.close)
        
        # Connect the ok_button to file_ok_sel method
        self.filew.ok_button.connect("clicked", self.file_ok_sel)
    
        # Connect the cancel_button to destroy the widget
        self.filew.cancel_button.connect("clicked", self.close)
    
    def popup(self, title, callfn, initialdir=None,
              filename=None):
        self.callfn = callfn
        self.filew.set_title(title)

        if filename:
            self.filew.set_filename(filename)

        self.filew.show()

    def close(self, widget):
        self.filew.hide()


class TagError(Exception):
    pass


class Page(object):

    def __init__(self, frame, name, title):

        self.frame = frame
        self.name = name
        self.title = title

        self.closed = False

        # every page has a lock
        self.lock = threading.RLock()

    def close(self):
        # parent attribute is added by parent workspace
        self.parent.delpage(self.name)

        self.closed = True


class CodePage(Page):

    def __init__(self, frame, name, title):

        super(CodePage, self).__init__(frame, name, title)

        # bottom buttons
        btns = gtk.HBox()
        self.btns = btns

        self.btn_close = gtk.Button("Close")
        self.btn_close.connect("clicked", lambda w: self.close())
        self.btn_close.show()
        btns.pack_end(self.btn_close, padding=4)

        self.btn_reload = gtk.Button("Reload")
        self.btn_reload.connect("clicked", lambda w: self.reload())
        self.btn_reload.show()
        btns.pack_end(self.btn_reload, padding=4)

        self.btn_save = gtk.Button("Save")
        self.btn_save.connect("clicked", lambda w: self.save())
        self.btn_save.show()
        btns.pack_end(self.btn_save, padding=4)

        btns.show()

        frame.pack_end(btns, fill=False, expand=False, padding=2)

        self.modified = True


    def loadbuf(self, buf):

        # insert text
        tags = ['code']
        try:
            start, end = self.buf.get_bounds()
            tw.delete(start, end)
        except:
            pass

        # Create default 'code' tag
        try:
            self.buf.create_tag('code', foreground="black")
        except:
            # tag may be already created
            pass

        self.buf.insert_with_tags_by_name(start, buf, *tags)


    def load(self, filepath, buf):
        self.loadbuf(buf)
        self.filepath = filepath
        #lw = self.txt.component('label')
        #lw.config(text=filepath)

        
    def reload(self):
        try:
            in_f = open(self.filepath, 'r')
            buf = in_f.read()
            in_f.close()
        except IOError, e:
            # ? raise exception instead ?
            return view.popup_error("Cannot write '%s': %s" % (
                    self.filepath, str(e)))

        self.loadbuf(buf)


    def save(self):
        # TODO: make backup?

        dirname, filename = os.path.split(self.filepath)

        res = view.popup_yesno("Save file", 
                               'Really save "%s"?' % filename)
        if not res:
            return

        # get text to save
        start, end = self.buf.get_bounds()
        buf = self.buf.get_text(start, end)

        try:
            out_f = open(self.filepath, 'w')
            out_f.write(buf)
            out_f.close()
            #self.statusMsg("%s saved." % self.filepath)
        except IOError, e:
            return view.popup_error("Cannot write '%s': %s" % (
                    self.filepath, str(e)))

        self.buf.set_modified(False)

        
    def close(self):
        if self.buf.get_modified():
            res = view.popup_yesno("Close file", 
                                   "File is modified. Really close?")
            if not res:
                return

        super(CodePage, self).close()


class OpePage(CodePage):

    def __init__(self, frame, name, title):

        super(OpePage, self).__init__(frame, name, title)

        self.queueName = 'executer'

        scrolled_window = gtk.ScrolledWindow()
        scrolled_window.set_border_width(2)

        scrolled_window.set_policy(gtk.POLICY_AUTOMATIC,
                                   gtk.POLICY_AUTOMATIC)

        tw = gtk.TextView()
        scrolled_window.add_with_viewport(tw)
        tw.show()
        scrolled_window.show()

        tw.set_editable(True)
        tw.set_wrap_mode(gtk.WRAP_NONE)
        tw.set_left_margin(4)
        tw.set_right_margin(4)

        frame.pack_start(scrolled_window, expand=True, fill=True)

        self.tw = tw
        self.buf = tw.get_buffer()

        # add some bottom buttons
        self.btn_exec = gtk.Button("Exec")
        self.btn_exec.connect("clicked", lambda w: view.execute(self))
        self.btn_exec.show()
        self.btns.pack_end(self.btn_exec)

        self.btn_pause = gtk.Button("Pause")
        self.btn_pause.connect("clicked", lambda w: self.pause())
        self.btn_pause.show()
        self.btns.pack_end(self.btn_pause)

        self.btn_cancel = gtk.Button("Cancel")
        self.btn_cancel.connect("clicked", lambda w: self.cancel())
        self.btn_cancel.show()
        self.btns.pack_end(self.btn_cancel)

        self.btn_kill = gtk.Button("Kill")
        self.btn_kill.connect("clicked", lambda w: self.kill())
        self.btn_kill.show()
        self.btns.pack_end(self.btn_kill)


    def loadbuf(self, buf):

        super(OpePage, self).loadbuf(buf)

        lines = buf.split('\n')
        header = '\n' * len(lines)
##         hw = self.txt.component('rowheader')
##         hw.delete('1.0', 'end')
##         hw.insert('end', header)


    def load(self, filepath, buf):

        super(OpePage, self).load(filepath, buf)

        name, ext = os.path.splitext(self.filepath)
        ext = ext.lower()

        if ext in ('.ope', '.cd'):
            self.color()


    def color(self):

        start, end = self.buf.get_bounds()
        buf = self.buf.get_text(start, end)

        def addtags(lineno, tags):
            start.set_line(lineno)
            end.set_line(lineno)
            end.forward_to_line_end()

            for tag in tags:
                self.buf.apply_tag_by_name(tag, start, end)

        try:
            self.buf.create_tag('comment3', foreground="indian red")
            self.buf.create_tag('comment2', foreground="saddle brown")
            self.buf.create_tag('comment1', foreground="dark green")
        except:
            # in case they've been created already
            pass

        lineno = 0
        for line in buf.split('\n'):
            line = line.strip()
            if line.startswith('###'):
                addtags(lineno, ['comment3'])
        
            elif line.startswith('##'):
                addtags(lineno, ['comment2'])
        
            elif line.startswith('#'):
                addtags(lineno, ['comment1'])

            lineno += 1



    def kill(self):
        #controller = self.parent.get_controller()
        controller.tm_restart()

    def cancel(self):
        #controller = self.parent.get_controller()
        controller.tm_cancel(self.queueName)

    def pause(self):
        #controller = self.parent.get_controller()
        controller.tm_pause(self.queueName)


class SkPage(CodePage):

    def __init__(self, frame, name, title):
        super(SkPage, self).__init__(frame, name, title)

        scrolled_window = gtk.ScrolledWindow()
        scrolled_window.set_border_width(2)

        scrolled_window.set_policy(gtk.POLICY_AUTOMATIC,
                                   gtk.POLICY_AUTOMATIC)

        tw = gtk.TextView()
        scrolled_window.add_with_viewport(tw)
        tw.show()
        scrolled_window.show()

        tw.set_editable(True)
        tw.set_wrap_mode(gtk.WRAP_NONE)
        tw.set_left_margin(4)
        tw.set_right_margin(4)

        frame.pack_start(scrolled_window, expand=True, fill=True)

        self.tw = tw
        self.buf = tw.get_buffer()


class TaskPage(CodePage):

    def __init__(self, frame, name, title):
        super(TaskPage, self).__init__(frame, name, title)

        scrolled_window = gtk.ScrolledWindow()
        scrolled_window.set_border_width(2)

        scrolled_window.set_policy(gtk.POLICY_AUTOMATIC,
                                   gtk.POLICY_AUTOMATIC)

        tw = gtk.TextView()
        scrolled_window.add_with_viewport(tw)
        tw.show()
        scrolled_window.show()

        tw.set_editable(True)
        tw.set_wrap_mode(gtk.WRAP_NONE)
        tw.set_left_margin(4)
        tw.set_right_margin(4)

        frame.pack_start(scrolled_window, expand=True, fill=True)

        self.tw = tw
        self.buf = tw.get_buffer()

                               
class DDCommandPage(Page):

    def __init__(self, frame, name, title):

        super(DDCommandPage, self).__init__(frame, name, title)

        self.queueName = 'executer'

        scrolled_window = gtk.ScrolledWindow()
        scrolled_window.set_border_width(2)

        scrolled_window.set_policy(gtk.POLICY_AUTOMATIC,
                                   gtk.POLICY_AUTOMATIC)

        tw = gtk.TextView()
        scrolled_window.add_with_viewport(tw)
        tw.show()
        scrolled_window.show()

        frame.pack_start(scrolled_window, expand=True, fill=True)

        self.tw = tw
        self.buf = tw.get_buffer()

        # bottom buttons
        btns = gtk.HBox(spacing=4)
        self.btns = btns

##         self.btn_close = gtk.Button("Close")
##         self.btn_close.connect("clicked", lambda w: self.close())
##         self.btn_close.show()
##         btns.pack_end(self.btn_close)

        self.btn_exec = gtk.Button("Exec")
        self.btn_exec.connect("clicked", lambda w: view.execute_dd(self))
        self.btn_exec.show()
        btns.pack_end(self.btn_exec)

        self.btn_pause = gtk.Button("Pause")
        self.btn_pause.connect("clicked", lambda w: self.pause())
        self.btn_pause.show()
        btns.pack_end(self.btn_pause)

        self.btn_cancel = gtk.Button("Cancel")
        self.btn_cancel.connect("clicked", lambda w: self.cancel())
        self.btn_cancel.show()
        btns.pack_end(self.btn_cancel)

        self.btn_kill = gtk.Button("Kill")
        self.btn_kill.connect("clicked", lambda w: self.kill())
        self.btn_kill.show()
        btns.pack_end(self.btn_kill)

        frame.pack_end(btns, fill=False, expand=False, padding=2)


    def kill(self):
        #controller = self.parent.get_controller()
        controller.tm_restart()

    def cancel(self):
        #controller = self.parent.get_controller()
        controller.tm_cancel(self.queueName)

    def pause(self):
        #controller = self.parent.get_controller()
        controller.tm_pause(self.queueName)


class ObsInfoPage(Page):

    def __init__(self, frame, name, title):

        super(ObsInfoPage, self).__init__(frame, name, title)

        scrolled_window = gtk.ScrolledWindow()
        scrolled_window.set_border_width(2)

        scrolled_window.set_policy(gtk.POLICY_AUTOMATIC,
                                   gtk.POLICY_AUTOMATIC)

        tw = gtk.TextView()
        scrolled_window.add_with_viewport(tw)
        tw.show()
        scrolled_window.show()

        tw.set_editable(False)
        tw.set_wrap_mode(gtk.WRAP_NONE)
        tw.set_left_margin(4)
        tw.set_right_margin(4)

        frame.pack_start(scrolled_window, expand=True, fill=True)

        self.tw = tw
        self.buf = tw.get_buffer()

        start = self.buf.get_start_iter()
        self.buf.insert(start, '\n' * 10)

        frame.pack_start(scrolled_window, fill=True, expand=True)


    def update_obsinfo(self, obsdict):

        self.logger.debug("obsinfo update: %s" % str(obsdict))

        if obsdict.has_key('PROP-ID'):
            update_line(self.buf, 1, 'Prop-Id: %s' % obsdict['PROP-ID'])
        if obsdict.has_key('TIMER_SEC'):
            self.set_timer(obsdict['TIMER_SEC'])
        
        offset = 2
        for i in xrange(1, 6):
            try:
                val = str(obsdict['OBSINFO%d' % i])
                update_line(self.buf, i+offset, val)
            except KeyError:
                continue


    def set_timer(self, val):
        self.logger.debug("val = %s" % str(val))
        val = int(val)
        self.logger.debug("val = %d" % val)
        if val <= 0:
            return
        self.timer_val = val + 1
        self.logger.debug("timer_val = %d" % self.timer_val)
        # READ GLOBAL VAR
        self.timer_interval(view.w.root)


    def timer_interval(self):
        self.logger.debug("timer: %d sec" % self.timer_val)
        self.timer_val -= 1
        update_line(self.buf, 2, 'Timer: %s' % str(self.timer_val))
        if self.timer_val > 0:
            gobject.timeout_add(1000, self.timer_interval)
        else:
            # Do something when timer expires?
            pass
        

class LogPage(Page):

    def __init__(self, frame, name, title):

        super(LogPage, self).__init__(frame, name, title)

        self.logsize = 5000

        scrolled_window = gtk.ScrolledWindow()
        scrolled_window.set_border_width(2)

        scrolled_window.set_policy(gtk.POLICY_AUTOMATIC,
                                   gtk.POLICY_AUTOMATIC)

        tw = gtk.TextView()
        scrolled_window.add_with_viewport(tw)
        tw.show()
        scrolled_window.show()

        frame.pack_start(scrolled_window, expand=True, fill=True)

        tw.set_editable(False)
        tw.set_wrap_mode(gtk.WRAP_NONE)
        tw.set_left_margin(4)
        tw.set_right_margin(4)

        self.tw = tw
        self.buf = tw.get_buffer()

        # bottom buttons
        btns = gtk.HBox(spacing=4)
        self.btns = btns

        self.btn_close = gtk.Button("Close")
        self.btn_close.connect("clicked", lambda w: self.close())
        self.btn_close.show()
        btns.pack_end(self.btn_close, padding=4)

        frame.pack_end(btns, fill=False, expand=False, padding=2)


    def load(self, filepath):
        self.filepath = filepath
        self.file = open(self.filepath, 'r')
        # Go to the end of the file
        self.file.seek(0, 2)
        self.size = self.file.tell()
        self.poll()


    def close(self):
        try:
            self.file.close()
        except:
            pass

        super(LogPage, self).close()


    def poll(self):
        if self.closed:
            return

        if os.path.getsize(self.filepath) > self.size:
            data = self.file.read()
            self.size = self.size + len(data)
            # TODO: mark error and warning lines

            loc = self.buf.get_end_iter()
            self.buf.insert(loc, data)

            # Remove some old log lines if necessary
            excess_lines = loc.get_line() - self.logsize
            if excess_lines > 0:
                bitr1 = self.buf.get_start_iter()
                bitr2 = bitr1.copy()
                bitr2.set_line(excess_lines)
                self.buf.delete(bitr1, bitr2)
                loc = self.buf.get_end_iter()
                    
            self.tw.scroll_to_iter(loc, 0.1)

        gobject.timeout_add(100, self.poll)


class FramesPage(Page):

    def __init__(self, frame, name, title):

        super(FramesPage, self).__init__(frame, name, title)

        scrolled_window = gtk.ScrolledWindow()
        scrolled_window.set_border_width(2)

        scrolled_window.set_policy(gtk.POLICY_AUTOMATIC,
                                   gtk.POLICY_AUTOMATIC)

        tw = gtk.TextView()
        scrolled_window.add_with_viewport(tw)
        tw.show()
        scrolled_window.show()

        frame.pack_start(scrolled_window, expand=True, fill=True)

        tw.set_editable(False)
        tw.set_wrap_mode(gtk.WRAP_NONE)
        tw.set_left_margin(4)
        tw.set_right_margin(4)

        self.tw = tw
        self.buf = tw.get_buffer()

##         # bottom buttons
##         btns = gtk.HBox(spacing=4)
##         self.btns = btns

##         self.btn_close = gtk.Button("Close")
##         self.btn_close.connect("clicked", lambda w: self.close())
##         self.btn_close.show()
##         btns.pack_end(self.btn_close, padding=4)

##         frame.pack_end(btns, fill=False, expand=False, padding=2)


    def update_frame(self, frameinfo):
        self.logger.debug("UPDATE FRAME: %s" % str(frameinfo))

        frameid = frameinfo.frameid
        with self.lock:
            text = fits.format_str % frameinfo

            if hasattr(frameinfo, 'row'):
                row = frameinfo.row
                update_line(self.buf, row, text)
                #update_line(self.buf, row, text, tags=[frameid])

            else:
                end = self.buf.get_end_iter()
                row = end.get_line()
                #self.buf.create_tag(frameid, foreground="black")
                frameinfo.row = row
                self.buf.insert(end, text)
                #self.buf.insert_with_tags_by_name(end, text, [frameid])

        
    def update_frames(self, framelist):

        # Delete frames text
        start, end = self.buf.get_bounds()
        self.buf.delete(start, end)
        
        # Create header
        self.buf.insert(start, fits.header)

        # add frames
        for frameinfo in framelist:
            self.update_frame(frameinfo)


class skMonitorPage(Page):

    def __init__(self, frame, name, title):

        super(skMonitorPage, self).__init__(frame, name, title)

        self.nb = gtk.Notebook()
        self.nb.set_tab_pos(gtk.POS_TOP)
        self.nb.set_scrollable(True)
        self.nb.set_show_tabs(True)
        self.nb.set_show_border(True)
        #self.nb.set_size_request(1000, 700)
        self.nb.show()

        frame.pack_start(self.nb, expand=True, fill=True,
                         padding=2)

        # Holds my pages
        self.pages = {}
        self.pagelist = []
        self.pagelimit = 10

        self.track = {}
        self.lock = threading.RLock()


    def insert_ast(self, tw, text):

        buf = tw.get_buffer()
        all_tags = set([])

        def insert(text, tags):

            loc = buf.get_end_iter()
            #linenum = loc.get_line()
            try:
                foo = text.index("<div ")

            except ValueError:
                buf.insert_with_tags_by_name(loc, text, *tags)
                return

            match = re.match(r'^\<div\sclass=([^\>]+)\>', text[foo:],
                             re.MULTILINE | re.DOTALL)
            if not match:
                buf.insert_with_tags_by_name(loc, 'ERROR 1: %s' % text, *tags)
                return

            num = int(match.group(1))
            regex = r'^(.*)\<div\sclass=%d\>(.+)\</div\sclass=%d\>(.*)$' % (
                num, num)
            #print regex
            match = re.match(regex, text, re.MULTILINE | re.DOTALL)
            if not match:
                buf.insert_with_tags_by_name(loc, 'ERROR 2: %s' % text, *tags)
                return

            buf.insert_with_tags_by_name(loc, match.group(1), *tags)

            serial_num = '%d' % num
            buf.create_tag(serial_num, foreground="black")
            newtags = [serial_num]
            all_tags.add(serial_num)
            newtags.extend(tags)
            insert(match.group(2), newtags)

            insert(match.group(3), tags)

        # Create tags that will be used
        buf.create_tag('code', foreground="black")
        
        insert(text, ['code'])
        #tw.tag_raise('code')
        #print "all tags=%s" % str(all_tags)

    def astIdtoTitle(self, ast_id):
        page = self.pages[ast_id]
        return page.title
        
    def delpage(self, ast_id):
        with self.lock:
            i = self.pagelist.index(ast_id)
            self.nb.remove_page(i)

            del self.pages[ast_id]
            self.pagelist.remove(ast_id)

    def addpage(self, ast_id, title, text):

        with self.lock:
            # Make room for new pages
            while len(self.pagelist) >= self.pagelimit:
                oldast_id = self.pagelist[0]
                self.delpage(oldast_id)
                
            scrolled_window = gtk.ScrolledWindow()
            scrolled_window.set_border_width(2)

            scrolled_window.set_policy(gtk.POLICY_AUTOMATIC,
                                       gtk.POLICY_AUTOMATIC)

            tw = gtk.TextView(buffer=None)
            scrolled_window.add_with_viewport(tw)
            tw.show()
            scrolled_window.show()

            tw.set_editable(True)
            tw.set_wrap_mode(gtk.WRAP_NONE)
            tw.set_left_margin(4)
            tw.set_right_margin(4)

            label = gtk.Label(title)
            label.show()

            self.nb.append_page(scrolled_window, label)

            self.insert_ast(tw, text)

            txtbuf = tw.get_buffer()
            tagtbl = txtbuf.get_tag_table()
            try:
                page = self.pages[ast_id]
                page.tw = tw
                page.buf = txtbuf
                page.tagtbl = tagtbl
                page.title = title
            except KeyError:
                self.pages[ast_id] = Bunch.Bunch(tw=tw, title=title,
                                                 buf=txtbuf, tagtbl=tagtbl)

            self.pagelist.append(ast_id)

            self.setpage(ast_id)

    def setpage(self, name):
        # Because %$%(*)&^! gtk notebook widget doesn't associate names
        # with pages
        i = self.pagelist.index(name)
        self.nb.set_current_page(i)

        
    def change_text(self, page, tagname, **kwdargs):
        tagname = str(tagname)
        tag = page.tagtbl.lookup(tagname)
        if not tag:
            raise TagError("Tag not found: '%s'" % tagname)

        for key, val in kwdargs.items():
            tag.set_property(key,val)
            
        #page.tw.tag_raise(ast_num)
        # Scroll the view to this area
        start, end = self.get_region(page.buf, tagname)
        page.tw.scroll_to_iter(start, 0.1)


    def get_region(self, txtbuf, tagname):
        """Returns a (start, end) pair of Gtk text buffer iterators
        associated with this tag.
        """
        # Painfully inefficient and error-prone way to locate a tagged
        # region.  Seems gtk text buffers have tags, but no good way to
        # manipulate text associated with them efficiently.

        tagname = str(tagname)

        # Get the tag table associated with this text buffer
        tagtbl = txtbuf.get_tag_table()
        # Look up the tag
        tag = tagtbl.lookup(tagname)
        
        # Get text iters at beginning and end of buffer
        start, end = txtbuf.get_bounds()

        # Now search forward from beginning for first location of this
        # tag, and backwards from the end
        result = start.forward_to_tag_toggle(tag)
        if not result:
            raise TagError("Tag not found: '%s'" % tagname)
        result = end.backward_to_tag_toggle(tag)
        if not result:
            raise TagError("Tag not found: '%s'" % tagname)

        return (start, end)


    def replace_text(self, page, tagname, textstr):
        tagname = str(tagname)
        txtbuf = page.buf
        start, end = self.get_region(txtbuf, tagname)
        txtbuf.delete(start, end)
        txtbuf.insert_with_tags_by_name(start, textstr, tagname)

        # Scroll the view to this area
        page.tw.scroll_to_iter(start, 0.1)


    def append_error(self, page, tagname, textstr):
        tagname = str(tagname)
        txtbuf = page.buf
        start, end = self.get_region(txtbuf, tagname)
        txtbuf.insert_with_tags_by_name(end, textstr, tagname)

        self.change_text(page, tagname,
                         foreground="red", background="lightyellow")


    def update_time(self, page, tagname, vals, time_s):

        if not view.show_times:
            return

        tagname = str(tagname)
        txtbuf = page.buf
        start, end = self.get_region(txtbuf, tagname)

        if vals.has_key('time_added'):
            length = vals['time_added']
            end = start.copy()
            end.forward_chars(length)
            txtbuf.delete(start, end)
            
        vals['time_added'] = len(time_s)
        txtbuf.insert_with_tags_by_name(start, time_s, tagname)
        

    def update_page(self, bnch):

        page = bnch.page
        vals = bnch.state
        #print "vals = %s" % str(vals)
        ast_num = vals['ast_num']

        cmd_str = None
        if vals.has_key('cmd_str'):
            cmd_str = vals['cmd_str']

            if not vals.has_key('inserted'):
                # Replace the decode string with the actual parameters
                self.replace_text(page, ast_num, cmd_str)
                vals['inserted'] = True
                try:
                    del vals['time_added']
                except KeyError:
                    pass

        if vals.has_key('task_error'):
            self.append_error(page, ast_num, '\n ==> ' + vals['task_error'])
            
            # audible warnings
            view.audible_warn(cmd_str, vals)

        elif vals.has_key('task_end'):
            if vals.has_key('task_start'):
                if view.track_elapsed and bnch.page.has_key('asttime'):
                    elapsed = vals['task_start'] - bnch.page.asttime
                else:
                    elapsed = vals['task_end'] - vals['task_start']
                self.update_time(page, ast_num, vals, '[ F %9.3f s ]: ' % (
                        elapsed))
            else:
                self.update_time(page, ast_num, vals, '[TE %s]: ' % (
                        self.time2str(vals['task_end'])))
            self.change_text(page, ast_num, foreground="blue4")
                
        elif vals.has_key('end_time'):
            self.update_time(page, ast_num, vals, '[EN %s]: ' % (
                    self.time2str(vals['end_time'])))
            self.change_text(page, ast_num, foreground="blue1")
                
        elif vals.has_key('ack_time'):
            self.update_time(page, ast_num, vals, '[AB %s]: ' % (
                    self.time2str(vals['ack_time'])))
            self.change_text(page, ast_num, foreground="green4")

        elif vals.has_key('cmd_time'):
            self.update_time(page, ast_num, vals, '[CD %s]: ' % (
                    self.time2str(vals['cmd_time'])))
            self.change_text(page, ast_num, foreground="brown")

        elif vals.has_key('task_start'):
            self.update_time(page, ast_num, vals, '[TS %s]: ' % (
                    self.time2str(vals['task_start'])))
            self.change_text(page, ast_num, foreground="gold2")

        else:
            #self.change_text(page, ast_num, foreground="gold2")
            pass

                
    def time2str(self, time_cmd):
        time_int = int(time_cmd)
        time_str = time.strftime("%H:%M:%S", time.localtime(float(time_int)))
        time_sfx = ('%.3f' % (time_cmd - time_int)).split('.')[1]
        title = time_str + ',' + time_sfx
        return title
            
    def process_ast(self, ast_id, vals):
        #print ast_id, vals

        with self.lock:
            try:
                page = self.pages[ast_id]
            except KeyError:
                # this page is not received/set up yet
                page = Bunch.Bunch(vals)
                page.nodes = {}
                self.pages[ast_id] = page

            if vals.has_key('ast_buf'):
                ast_str = ro.binary_decode(vals['ast_buf'])
                # Get the time of the command to construct the tab title
                title = self.time2str(vals['ast_time'])
                page.asttime = vals['ast_time']

                # TODO: what if this page has already been deleted?
                # GLOBAL VAR READ
                if view.save_decode_result:
                    self.addpage(ast_id + '.decode', title, ast_str)

                self.addpage(ast_id, title, ast_str)

            elif vals.has_key('ast_track'):
                path = vals['ast_track']
                
                # GLOBAL VAR READ
                curvals = controller.getvals(path)
                if isinstance(curvals, dict):
                    vals.update(curvals)
               
                # Make an entry for this ast node, if there isn't one already
                ast_num = '%d' % vals['ast_num']
                state = page.nodes.setdefault(ast_num, vals)

                bnch = Bunch.Bunch(page=page, state=state)
                self.track.setdefault(vals['ast_track'], bnch)
                
                # Replace the decode string with the actual parameters
                # ?? Has string really changed at this point??
                self.replace_text(page, ast_num, vals['ast_str'])

                self.update_page(bnch)
                

    def process_task(self, path, vals):
        #print path, vals

        with self.lock:
            try:
                bnch = self.track[path]
            except KeyError:
                # this page is not received/set up yet
                return

            #print path, vals
            bnch.state.update(vals)

            self.update_page(bnch)
            

    def process_ast_err(self, ast_id, vals):
        try:
            self.process_ast(ast_id, vals)
        except Exception, e:
            self.logger.error("MONITOR ERROR: %s" % str(e))
            
    def process_task_err(self, path, vals):
        try:
            self.process_task(path, vals)
        except Exception, e:
            self.logger.error("MONITOR ERROR: %s" % str(e))
            
        

class Launcher(object):
    
    def __init__(self, frame, name, title, execfn):
        self.frame = frame
        self.params = Bunch.Bunch()
        self.paramList = []
        self.row = 1
        self.col = 1
        self.btn_width = 20
        self.execfn = execfn

        self.btn_exec = gtk.Button(title)
        self.btn_exec.connect("clicked", self.execute)
        self.btn_exec.show()
        btns.pack_end(self.btn_exec)

        #self.btn_exec.grid(row=1, column=0, padx=1, sticky='ew')
        

    def addParam(self, name):
        self.paramList.append(name)
        # sort parameter list so longer strings are substituted first
        self.paramList.sort(lambda x,y: len(y) - len(x))

    def add_cmd(self, cmdstr):
        self.cmdstr = cmdstr

    def add_break(self):
        self.row += 2
        self.col = 1

    def add_input(self, name, width, defVal, label):
        
        lbl = Tkinter.Label(self.frame, text=label, relief='flat')
        lbl.grid(row=self.row-1, column=self.col, padx=1, sticky='ew')
        tclvar = Tkinter.StringVar(self.frame)
        tclvar.set(str(defVal))
        field = Tkinter.Entry(self.frame, textvariable=tclvar, width=width)
        field.grid(row=self.row, column=self.col, padx=1, sticky='ew')
        self.col += 1

        name = name.lower()
        self.params[name] = Bunch.Bunch(widget=field,
                                        var=tclvar,
                                        get=self.getvar)
        self.addParam(name)

    def add_list(self, name, optionList, label):
        
        lbl = Tkinter.Label(self.frame, text=label, relief='flat')
        lbl.grid(row=self.row-1, column=self.col, padx=1, sticky='ew')
        tclvar = Tkinter.StringVar(self.frame)
        optionsDict = {}
        options = []
        for opt, val in optionList:
            optionsDict[opt] = val
            options.append(opt)
        tclvar.set(options[0])
        menu = Tkinter.OptionMenu(self.frame, tclvar, *options)
        menu.grid(row=self.row, column=self.col, padx=1, sticky='ew')
        self.col += 1

        name = name.lower()
        self.params[name] = Bunch.Bunch(widget=menu, 
                                        var=tclvar,
                                        get=self.getdict,
                                        optionsDict=optionsDict)
        self.addParam(name)

    def add_radio(self, name, optionList, label):
        
        lbl = Tkinter.Label(self.frame, text=label, relief='flat')
        lbl.grid(row=self.row-1, column=self.col, padx=1, sticky='ew')
        tclvar = Tkinter.StringVar(self.frame)
        tclvar.set(optionList[0][1])
        for opt, val in optionList:
            b = Tkinter.Radiobutton(self.frame, text=opt, 
                                    variable=tclvar, value=str(val),
                                    relief='flat')
            b.grid(row=self.row, column=self.col, padx=1, sticky='ew')
            self.col += 1

        name = name.lower()
        self.params[name] = Bunch.Bunch(widget=b,
                                        get=self.getvar,
                                        var=tclvar)
        self.addParam(name)

    def getvar(self, bnch):
        return bnch.var.get()

    def getdict(self, bnch):
        key = bnch.var.get()
        return bnch.optionsDict[key]

    def getcmd(self):
        cmdstr = self.cmdstr
        
        for var in self.paramList:
            dvar = '$%s' % var.upper()
            if dvar in cmdstr:
                bnch = self.params[var]
                val = str(bnch.get(bnch))
                cmdstr = cmdstr.replace(dvar, val)

        return cmdstr

    def execute(self):
        cmdstr = self.getcmd()
        self.execfn(cmdstr)


class LauncherList(object):
    
    def __init__(self, frame, name, title, execfn):
        self.llist = []
        self.ldict = {}
        self.count = 0
        self.frame = frame
        self.execfn = execfn

    def addSeparator(self):
        separator = Tkinter.Frame(self.frame, height=2, bd=1,
                                  relief='sunken')
        separator.grid(row=self.count, column=0, sticky='ew',
                       padx=5, pady=5)
        self.count += 1

    def addLauncher(self, name, title):
        frame = Tkinter.Frame(self.frame, padx=2, pady=2)
        #frame.pack(side=Tkinter.TOP, fill='x', expand=False)
        frame.grid(row=self.count, column=0, sticky='w')
        self.count += 1
        
        launcher = Launcher(frame, name, title,
                            lambda cmdstr: self.execute(name, cmdstr))
        
        self.llist.append(launcher)
        self.ldict[name.lower()] = launcher
        
        return launcher

    def getLauncher(self, name):
        return self.ldict[name.lower()]

    def addLauncherFromDef(self, ast):
        assert ast.tag == 'launcher'
        ast_label, ast_body = ast.items

        assert ast_label.tag == 'label'
        name = ast_label.items[0]

        launcher = self.addLauncher(name, name)

        for ast in ast_body.items:
            assert ast.tag in ('cmd', 'list', 'select', 'input', 'break')
            
            if ast.tag == 'break':
                launcher.add_break()

            elif ast.tag == 'input':
                var, width, val, lbl = ast.items
                width = int(width)
                launcher.add_input(var, width, val, lbl)
        
            elif ast.tag == 'select':
                var, ast_list, lbl = ast.items
                vallst = []

                if ast_list.tag == 'pure_val_list':
                    for item in ast_list.items:
                        vallst.append((item, item))
                
                elif ast_list.tag == 'subst_val_list':
                    for item_ast in ast_list.items:
                        assert item_ast.tag == 'value_pair'
                        lhs, rhs = item_ast.items
                        vallst.append((lhs, rhs))
                        
                launcher.add_radio(var, vallst, lbl)
        
            elif ast.tag == 'list':
                var, ast_list, lbl = ast.items
                vallst = []

                if ast_list.tag == 'pure_val_list':
                    for item in ast_list.items:
                        vallst.append((item, item))
                
                elif ast_list.tag == 'subst_val_list':
                    for item_ast in ast_list.items:
                        assert item_ast.tag == 'value_pair'
                        lhs, rhs = item_ast.items
                        vallst.append((lhs, rhs))
                        
                launcher.add_list(var, vallst, lbl)
        
            elif ast.tag == 'cmd':
                cmd, ast_params = ast.items
                cmd_l = [cmd.upper()]

                for item_ast in ast_params.items:
                    assert item_ast.tag == 'param_pair'
                    lhs, rhs = item_ast.items
                    cmd_l.append('%s=%s' % (lhs.upper(), rhs))

                cmdstr = ' '.join(cmd_l)

                launcher.add_cmd(cmdstr)

            else:
                pass
        
    def addFromDefs(self, ast):
        assert ast.tag == 'launchers'
        
        for ast in ast.items:
            if ast.tag == 'sep':
                self.addSeparator()

            else:
                self.addLauncherFromDef(ast)


    def execute(self, name, cmdstr):
        self.execfn(cmdstr)


class LauncherPage(Page):

    def __init__(self, frame, name, title):

        super(LauncherPage, self).__init__(frame, name, title)

        self.queueName = 'launcher'

        scrolled_window = gtk.ScrolledWindow()
        scrolled_window.set_border_width(2)
        
        scrolled_window.set_policy(gtk.POLICY_AUTOMATIC,
                                   gtk.POLICY_AUTOMATIC)
        frame.pack_start(expand=True, fill=True)
        
        scrolled_window.show()

        self.fw = gtk.VBox()
        scrolled_window.add_with_viewport(self.fw)
        
        self.llist = LauncherList(self.fw, name, title,
                                  self.execute)

        # bottom buttons
        btns = gtk.HBox()
        self.btns = btns

        self.btn_close = gtk.Button("Close")
        self.btn_close.connect("clicked", lambda w: self.close())
        self.btn_close.show()
        btns.pack_end(self.btn_close, padding=4)

        self.btn_pause = gtk.Button("Pause")
        self.btn_pause.connect("clicked", lambda w: self.pause())
        self.btn_pause.show()
        btns.pack_end(self.btn_pause, padding=4)

        self.btn_cancel = gtk.Button("Cancel")
        self.btn_cancel.connect("clicked", lambda w: self.cancel())
        self.btn_cancel.show()
        btns.pack_end(self.btn_cancel, padding=4)

        frame.pack_end(btns, fill=False, expand=False, padding=2)

        scrolled_window.show_all()


    def load(self, buf):
        self.llist.loadLauncher(buf)

    def addFromDefs(self, ast):
        self.llist.addFromDefs(ast)

    def execute(self, cmdstr):
        """This is called when a launcher button is pressed."""
        view.execute_launcher(cmdstr)

    def close(self):
        super(LauncherPage, self).close()

    def cancel(self):
        #controller = self.parent.get_controller()
        controller.tm_cancel(self.queueName)

    def pause(self):
        #controller = self.parent.get_controller()
        controller.tm_pause(self.queueName)


                               
class Workspace(object):
    
    def __init__(self, frame, name, title):
        self.frame = frame
        self.name = name
        self.title = title

        self.widget = gtk.Notebook()
        self.widget.set_tab_pos(gtk.POS_TOP)
        self.widget.set_scrollable(True)
        self.widget.set_show_tabs(True)
        self.widget.set_show_border(True)
        self.widget.set_size_request(1000, 700)
        self.widget.show()

        frame.pack_start(self.widget, expand=True, fill=True,
                         padding=2)

        # Holds my pages
        self.pages = {}
        self.pagelist = []
        self.lock = threading.RLock()


    def addpage(self, name, title, klass):
        with self.lock:
            try:
                pageobj = self.pages[name]
                raise Exception("A page with name '%s' already exists!" % name)

            except KeyError:
                pass

            # Make a frame for the notebook tab content
            pagefr = gtk.VBox()

            # Create the new object in the frame
            pageobj = klass(pagefr, name, title)

            pagefr.show()

            # Create a label for the notebook tab
            label = gtk.Label(title)
            label.show()

            # Add the page to the notebook
            self.widget.append_page(pagefr, label)
            
            # Some attributes we force on our children
            pageobj.logger = self.logger
            # ?? cyclical reference causes problems for gc?
            pageobj.parent = self

            # store away our handles to the page
            self.pages[name] = pageobj
            self.pagelist.append(name)

            # select the new page
            self.select(name)

            return pageobj

        
    def delpage(self, name):
        with self.lock:
            i = self.pagelist.index(name)
            self.widget.remove_page(i)

            del self.pages[name]
            self.pagelist.remove(name)
            

    def delall(self):
        with self.lock:
            for name in self.pages.keys():
                self.delpage(name)
            
    def select(self, name):
        i = self.pagelist.index(name)
        self.widget.set_current_page(i)

    def getNames(self):
        with self.lock:
            return self.pages.keys()

    def getPage(self, name):
        with self.lock:
            return self.pages[name]


class WorkspacePage(Workspace, Page):
    pass

      
class Desktop(object):
    
    def __init__(self, frame, name, title):
        self.frame = frame
        self.name = name
        self.title = title

        # TODO: should generalize to number of rows and columns

        paned = gtk.HPaned()
        self.hframe = paned
        paned.show()

        frame.pack_start(paned, fill=True, expand=True)

        lframe = gtk.VPaned()
        rframe = gtk.VPaned()

        paned.add1(lframe)
        paned.add2(rframe)

        ul = gtk.VBox()
        lframe.add1(ul)
        ll = gtk.VBox()
        lframe.add2(ll)

        ur = gtk.VBox()
        rframe.add1(ur)
        lr = gtk.VBox()
        rframe.add2(lr)

        self.ws_fr = {
            'll': ll,
            'ul': ul,
            'lr': lr,
            'ur': ur,
            }

        self.ws = {}

        paned.show_all()


    def get_wsframe(self, name):
        return self.ws_fr[name]

    def addws(self, loc, name, title):

        frame = self.get_wsframe(loc)

        ws = Workspace(frame, name, title)
        # Some attributes we force on our children
        ws.logger = self.logger

        frame.show_all()
        
        self.ws[name] = ws
        return ws

    def getws(self, name):
        return self.ws[name]


class IntegView(object):

    def __init__(self, logger, ev_quit, queues, lnchmgr):

        self.logger = logger
        self.ev_quit = ev_quit
        self.queue = queues
        self.lnchmgr = lnchmgr
        self.lock = threading.RLock()
        # Used for tagging commands
        self.cmdcount = 0

        # Create the GUI
        self.w = Bunch.Bunch()

        # evil hack required to use threads with GTK
        gtk.gdk.threads_init()

        # Create top-level window
        root = gtk.Window(gtk.WINDOW_TOPLEVEL)
        root.set_size_request(1900, 1100)
        root.set_title('Gen2 Integrated GUI II')
        root.connect("delete_event", self.delete_event)
        root.set_border_width(2)

        # create main frame
        self.w.mframe = gtk.VBox(spacing=2)
        root.add(self.w.mframe)
        #self.w.mframe.show()

        self.w.root = root

        self.add_menus()
        self.add_dialogs()

        self.ds = Desktop(self.w.mframe, 'desktop', 'IntegGUI Desktop')
        # Some attributes we force on our children
        self.ds.logger = logger

        self.ojws = self.ds.addws('ul', 'obsjrn', "Observation Journal")
        self.framepage = self.ojws.addpage('frames', "Frames", FramesPage)

        self.lws = self.ds.addws('ll', 'launchers', "Command Launchers")

        self.oiws = self.ds.addws('ur', 'obsinfo', "Observation Info")
        self.obsinfo = self.oiws.addpage('obsinfo', "Obsinfo", ObsInfoPage)
        self.monpage = self.oiws.addpage('moninfo', "Monitor", skMonitorPage)
        self.logpage = self.oiws.addpage('loginfo', "Logs", WorkspacePage)
        self.oiws.select('obsinfo')

        self.exws = self.ds.addws('lr', 'executor', "Command Executers")
        self.exws.addpage('ddcommands', "Commands", DDCommandPage)

        self.add_statusbar()

        self.w.root.show_all()

    def toggle_var(self, widget, key):
        if widget.active: 
            self.__dict__[key] = True
        else:
            self.__dict__[key] = False

    def add_menus(self):

        menubar = gtk.MenuBar()
        self.w.mframe.pack_start(menubar, expand=False)

        # create a File pulldown menu, and add it to the menu bar
        filemenu = gtk.Menu()
        file_item = gtk.MenuItem(label="File")
        menubar.append(file_item)
        file_item.show()
        file_item.set_submenu(filemenu)

        item = gtk.MenuItem(label="Load ope")
        filemenu.append(item)
        item.connect_object ("activate", lambda w: self.gui_load_ope(),
                             "file.Load ope")
        item.show()

        item = gtk.MenuItem(label="Config from session")
        filemenu.append(item)
        item.connect_object ("activate", lambda w: self.reconfig(),
                             "file.Config from session")
        item.show()

        item = gtk.MenuItem(label="Load log")
        filemenu.append(item)
        item.connect_object ("activate", lambda w: self.gui_load_log(),
                             "file.Load log")
        item.show()
        
        item = gtk.MenuItem(label="Load sk")
        filemenu.append(item)
        item.connect_object ("activate", lambda w: self.gui_load_sk(),
                             "file.Load sk")
        item.show()

        item = gtk.MenuItem(label="Load task")
        filemenu.append(item)
        item.connect_object ("activate", lambda w: self.gui_load_task(),
                             "file.Load task")
        item.show()

        item = gtk.MenuItem(label="Load launcher")
        filemenu.append(item)
        item.connect_object ("activate", lambda w: self.gui_load_launcher(),
                             "file.Load launcher")
        item.show()

        sep = gtk.SeparatorMenuItem()
        filemenu.append(sep)
        sep.show()
        quit_item = gtk.MenuItem(label="Exit")
        filemenu.append(quit_item)
        quit_item.connect_object ("activate", self.quit, "file.exit")
        quit_item.show()

        # create an Option pulldown menu, and add it to the menu bar
        optionmenu = gtk.Menu()
        option_item = gtk.MenuItem(label="Option")
        menubar.append(option_item)
        option_item.show()
        option_item.set_submenu(optionmenu)

        # Option variables
        self.save_decode_result = False
        self.show_times = False
        self.track_elapsed = False
        self.audible_errors = True

        w = gtk.CheckMenuItem("Save Decode Result")
        w.set_active(False)
        optionmenu.append(w)
        w.connect("activate", lambda w: self.toggle_var(w, 'save_decode_result'))
        w = gtk.CheckMenuItem("Show Times")
        w.set_active(False)
        optionmenu.append(w)
        w.connect("activate", lambda w: self.toggle_var(w, 'show_times'))
        w = gtk.CheckMenuItem("Track Elapsed")
        w.set_active(False)
        optionmenu.append(w)
        w.connect("activate", lambda w: self.toggle_var(w, 'track_elapsed'))
        w = gtk.CheckMenuItem("Audible Errors")
        w.set_active(True)
        optionmenu.append(w)
        w.connect("activate", lambda w: self.toggle_var(w, 'audible_errors'))


    def add_dialogs(self):
        self.filesel = FileSelection()
    
    def logupdate(self):
        pass
    
    def add_statusbar(self):
        self.w.status = gtk.Statusbar()
        self.status_cid = self.w.status.get_context_id("msg")
        self.status_mid = self.w.status.push(self.status_cid, "")

        self.w.mframe.pack_end(self.w.status, expand=False, fill=True,
                               padding=2)


    def statusMsg(self, format, *args):
        if not format:
            s = ''
        else:
            s = format % args

        self.w.status.remove(self.status_cid, self.status_mid)
        self.status_mid = self.w.status.push(self.status_cid, s)


    def setPos(self, geom):
        # TODO: currently does not seem to be honoring size request
        match = re.match(r'^(?P<size>\d+x\d+)?(?P<pos>[\-+]\d+[\-+]\d+)?$',
                         geom)
        if not match:
            return
        
        size = match.group('size')
        pos = match.group('pos')

        if size:
            match = re.match(r'^(\d+)x(\d+)$', size)
            if match:
                width, height = map(int, match.groups())
                self.w.root.set_default_size(width, height)

        # TODO: placement
        if pos:
            pass

        #self.root.set_gravity(gtk.gdk.GRAVITY_NORTH_WEST)
        ##width, height = window.get_size()
        ##window.move(gtk.gdk.screen_width() - width, gtk.gdk.screen_height() - height)
        # self.root.move(x, y)


#     def set_controller(self, controller):
#         self.controller = controller

    def popup_error(self, errstr):
        w = gtk.MessageDialog(flags=gtk.DIALOG_DESTROY_WITH_PARENT,
                              type=gtk.MESSAGE_WARNING,
                              buttons=gtk.BUTTONS_OK,
                              message_format=errstr)
        #w.connect("close", self.close)
        w.connect("response", lambda w, id: w.destroy())
        w.set_title('IntegGUI Error')
        w.show()


    def popup_yesno(self, title, qstr):
        w = gtk.MessageDialog(flags=gtk.DIALOG_DESTROY_WITH_PARENT,
                              type=gtk.MESSAGE_QUESTION,
                              buttons=gtk.BUTTONS_YES_NO,
                              message_format=qstr)
        w.set_title(title)
        res = w.run()
        w.destroy()

        if res == gtk.RESPONSE_YES:
            return True

        return False


    def readfile(self, filepath):

        in_f = open(filepath, 'r')
        buf = in_f.read()
        in_f.close()

        return buf


    def gui_load_ope(self):
        initialdir = os.path.join(os.environ['HOME'], 'Procedure')

        self.filesel.popup("Load OPE file", self.load_ope,
                           initialdir=initialdir)

    def load_ope(self, filepath):
        try:
            buf = self.readfile(filepath)

            dirname, filename = os.path.split(filepath)

            page = self.exws.addpage(filepath, filename, OpePage)
            page.load(filepath, buf)

        except Exception, e:
            self.popup_error("Cannot load '%s': %s" % (
                    filepath, str(e)))


    def gui_load_log(self):
        initialdir = os.path.abspath(os.environ['LOGHOME'])
        
        self.filesel.popup("Follow log", self.load_log,
                           initialdir=initialdir)


    def load_log(self, filepath):
        try:
            dirname, filename = os.path.split(filepath)

            page = self.logpage.addpage(filepath, filename, LogPage)
            page.load(filepath)

        except Exception, e:
            self.popup_error("Cannot load '%s': %s" % (
                    filepath, str(e)))


    def gui_load_sk(self):
        initialdir = os.path.join(os.environ['PYHOME'], 'SOSS',
                                  'SkPara', 'sk')
        
        self.filesel.popup("Load skeleton file", self.load_sk,
                           initialdir=initialdir)

    def load_sk(self, filepath):
        try:
            buf = self.readfile(filepath)

            dirname, filename = os.path.split(filepath)

            page = self.exws.addpage(filepath, filename, SkPage)
            page.load(filepath, buf)

        except Exception, e:
            self.popup_error("Cannot load '%s': %s" % (
                    filepath, str(e)))
                               

    def gui_load_task(self):
        initialdir = os.path.join(os.environ['GEN2HOME'], 'Tasks')
        
        self.filesel.popup("Load python task", self.load_task,
                           initialdir=initialdir)

    def load_task(self, filepath):
        try:
            buf = self.readfile(filepath)

            dirname, filename = os.path.split(filepath)

            page = self.exws.addpage(filepath, filename, TaskPage)
            page.load(filepath, buf)

        except Exception, e:
            self.popup_error("Cannot load '%s': %s" % (
                    filepath, str(e)))


    def gui_load_launcher(self):
        initialdir = os.path.join(os.environ['GEN2HOME'], 'integgui2',
                                  'Launchers')
        
        self.filesel.popup("Load launcher", self.load_launcher,
                           initialdir=initialdir)


    def load_launcher(self, filepath):
        try:
            buf = self.readfile(filepath)

            dirname, filename = os.path.split(filepath)

            match = re.match(r'^(.+)\.def$', filename)
            if not match:
                return

            name = match.group(1).replace('_', ' ')
            page = self.lws.addpage(name, name, LauncherPage)
            #page.load(buf)

            ast = self.lnchmgr.parse_buf(buf)
            page.addFromDefs(ast)

        except Exception, e:
            self.popup_error("Cannot load '%s': %s" % (
                    filepath, str(e)))


    def get_launcher_paths(self, insname):

        filename = '%s*.def' % insname.upper()
        pathmatch = os.path.join(os.environ['GEN2HOME'], 'integgui2',
                                 'Launchers', filename)

        res = glob.glob(pathmatch)
        return res

        
    def close_launchers(self):
        for name in self.lws.getNames():
            page = self.lws.getPage(name)
            page.close()

    def get_log_path(self, insname):

        filename = '%s.log' % insname
        filepath = os.path.join(os.environ['LOGHOME'], filename)
        return filepath

    def close_logs(self):
        for name in self.logpage.getNames():
            page = self.logpage.getPage(name)
            page.close()

    def reconfig(self):
        self.close_logs()
        self.close_launchers()

        #update_idletasks()

        controller.config_from_session('main')

    def get_tag(self, format):
        with self.lock:
            tag = format % self.cmdcount
            self.cmdcount += 1
            return tag

    def delete_event(self, widget, event, data=None):
        self.ev_quit.set()
        gtk.main_quit()
        return False

    # callback to quit the program
    def quit(self, widget):
        self.ev_quit.set()
        gtk.main_quit()
        return False


    def execute(self, opepage):
        """Callback when the EXEC button is pressed.
        """
        queueObj = self.queue['executer']

        # Check whether we are busy executing a command here
        # and popup an error message if so
        #if queueObj.executingP():
        #    self.popup_error("Commands are executing!")
        #    return

        buf = opepage.buf
        #self.clear_marks(opepage)

        if not buf.get_has_selection():
            # No selection.  See if there are previously queued commands
            if len(queueObj) == 0:
                self.popup_error("No queued commands and no mouse selection!")
            else:
                queueObj.enable()
                
            return

        # Get the range of text selected
        first, last = buf.get_selection_bounds()
        frow = first.get_line()
        lrow = last.get_line()

        # flush queue--selection will override
        queueObj.flush()

        # Break selection into individual lines
        tags = []

        for i in xrange(int(lrow)+1-frow):

            row = frow+i

            first.set_line(row)
            last.set_line(row)
            last.forward_to_line_end()

            # skip comments and blank lines
            cmd = buf.get_text(first, last).strip()
            if cmd.startswith('#') or (len(cmd) == 0):
                continue
            self.logger.debug("cmd=%s" % (cmd))

            # tag the text so we can manipulate it later
            tag = self.get_tag('ope%d')
            buf.create_tag(tag, foreground="black")
            buf.apply_tag_by_name(tag, first, last)

            tags.append(Bunch.Bunch(tag=tag, opepage=opepage,
                                    type='opepage'))

        # deselect the region
        #tw.tag_remove(Tkinter.SEL, '1.0', 'end')

        # Add tags to queue
        queueObj.extend(tags)

        # Enable executor thread to proceed
        queueObj.enable()

            
    def execute_dd(self, opepage):
        """Callback when the EXEC button is pressed.
        """
        queueObj = self.queue['executer']

        # Check whether we are busy executing a command here
        # and popup an error message if so
        #if queueObj.executingP():
        #    self.popup_error("Commands are executing!")
        #    return

        tw = opepage.tw

        tag = self.get_tag('dd%d')

        tags = [Bunch.Bunch(tag=tag, opepage=opepage,
                            type='cmdpage')]

        # deselect the region
        #tw.tag_remove(Tkinter.SEL, '1.0', 'end')

        # Add tags to queue
        queueObj.extend(tags)

        # Enable executor thread to proceed
        queueObj.enable()


    def execute_launcher(self, cmdstr):
        self.logger.info(cmdstr)
        queueObj = self.queue['launcher']

        # tag the text so we can manipulate it later
        tag = self.get_tag('ln%d')

        bnch = Bunch.Bunch(tag=tag, type='launcher',
                           cmdstr=cmdstr)
        queueObj.add(bnch)

        # Enable executor thread to proceed
        queueObj.enable()


    def get_cmdstr(self, bnch):
        """Called to get a command string from the GUI.
        """

        if bnch.type == 'launcher':
            return bnch.cmdstr

        # Get the entire buffer from the page's text widget
        buf = bnch.opepage.buf
        start, end = buf.get_bounds()
        txtbuf = buf.get_text(start, end).strip()

        if bnch.type == 'cmdpage':
            # remove trailing semicolon, if present
            cmdstr = txtbuf
            if cmdstr.endswith(';'):
                cmdstr = cmdstr[:-1]

            return cmdstr

        # <-- Page is an OPE page type

        # Now get the command from the text widget
        start, end = get_region(buf, bnch.tag)
        cmdstr = buf.get_text(start, end).strip()

        # remove trailing semicolon, if present
        if cmdstr.endswith(';'):
            cmdstr = cmdstr[:-1]

        # Resolve all variables/macros
        try:
            self.logger.debug("Unprocessed command is: %s" % cmdstr)
            p_cmdstr = ope.getCmd(txtbuf, cmdstr)
            self.logger.debug("Processed command is: %s" % p_cmdstr)

            return p_cmdstr

        except Exception, e:
            errstr = "Error parsing command: %s" % (str(e))
            raise Exception(errstr)
            

    def clear_marks(self, opepage):
        return
        #rw = opepage.rw
        #rw.delete('1.0', 'end')


    def mark_exec(self, bnch, char, queueName):

        return
        # Get the entire OPE buffer
        tw = bnch.opepage.tw
        row, col = str(tw.index('end')).split('.')
        tw_len = int(row)
        index = tw.index('%s.first' % bnch.tag)

        # Make the row marks buffer the same length
        # as the text file buffer
        rw = bnch.opepage.rw
        row, col = str(rw.index('end')).split('.')
        rw_len = int(row)
        if rw_len < tw_len:
            rw.insert('end', '\n' * (tw_len - rw_len))

        #rw.delete('%s linestart' % index, '%s lineend' % index)
        rw.insert(index, char)

        # Mark pending tasks in the queue as '(S)cheduled'
        queueObj = self.queue['executer']

        for nbnch in queueObj.peekAll():
            index = tw.index('%s.first' % nbnch.tag)
            rw.insert(index, 'S')


    def get_queue(self, queueName):

        queueObj = self.queue[queueName]

        try:
            bnch = queueObj.get()
            
        except igctrl.QueueEmpty, e:
            # Disable queue until commands are available
            queueObj.disable()
            
            raise(e)

        self.logger.debug("bnch=%s" % str(bnch))
        cmdstr = self.get_cmdstr(bnch)

        if bnch.type == 'opepage':
            #self.clear_marks()
            self.mark_exec(bnch, 'X', queueName)
        
        return bnch, cmdstr


    def feedback_noerror(self, queueName, bnch, res):

        queueObj = self.queue[queueName]

        if bnch.type == 'opepage':
            self.mark_exec(bnch, 'D', queueName)
        #self.make_sound(cmd_ok)
        
        # If queue is empty, disable it until more commands are
        # added
        if len(queueObj) == 0:
            queueObj.disable()

            # Bing Bong!
            self.playSound(sound.success)

           
    def feedback_error(self, queueName, bnch, e):

        queueObj = self.queue[queueName]

        queueObj.disable()

        if bnch:
            if bnch.type == 'opepage':
                # Mark an (E)rror in the opepage
                self.mark_exec(bnch, 'E', queueName)

                # reselect the region
                #tw = bnch.opepage.tw
                #for nbnch in queueObj.peekAll():
                #    tw.tag_add(Tkinter.SEL, 
                #               '%s.first' % nbnch.tag,
                #               '%s.last' % nbnch.tag)

                # Put object back on the front of the queue
                queueObj.prepend(bnch)

        gobject.idle_add(self.popup_error, str(e))
        #self.statusMsg(str(e))

        # Peeeeeww!
        self.playSound(sound.failure)

        
    def audible_warn(self, cmd_str, vals):
        """Called when we get a failed command and should/could issue an audible
        error.  cmd_str, if not None, is the device dependent command that caused
        the error.
        """
        self.logger.debug("Audible warning: %s" % cmd_str)
        if not cmd_str:
            return

        if not self.audible_errors:
            return

        cmd_str = cmd_str.lower().strip()
        match = re.match(r'^exec\s+(\w+)\s+.*', cmd_str)
        if not match:
            subsys = 'general'
        else:
            subsys = match.group(1)

        #soundfile = 'g2_err_%s.au' % subsys
        soundfile = 'E_ERR%s.au' % subsys.upper()
        self.playSound(soundfile)


    def playSound(self, soundfile):
        soundpath = os.path.join(cfg.g2soss.producthome,
                                 'file/Sounds', soundfile)
        if os.path.exists(soundpath):
            cmd = "OSST_audioplay %s" % (soundpath)
            self.logger.debug(cmd)
            res = os.system(cmd)
        else:
            self.logger.error("No such audio file: %s" % soundpath)
        

    def update_frame(self, frameinfo):
        # because gtk thread handling sucks
        gobject.idle_add(self.framepage.update_frame, frameinfo)

    def update_frames(self, framelist):
        # because gtk thread handling sucks
        gobject.idle_add(self.framepage.update_frames, framelist)

    def update_obsinfo(self, infodict):
        self.logger.info("OBSINFO=%s" % str(infodict))
        # because gtk thread handling sucks
        gobject.idle_add(self.obsinfo.update_obsinfo, infodict)
   
    def process_ast(self, ast_id, vals):
        # because gtk thread handling sucks
        gobject.idle_add(self.monpage.process_ast_err, ast_id, vals)

    def process_task(self, path, vals):
        # because gtk thread handling sucks
        gobject.idle_add(self.monpage.process_task_err, path, vals)

    def mainloop(self):
        gtk.main()


rc = """
style "window"
{
}

style "button"
{
  # This shows all the possible states for a button.  The only one that
  # doesn't apply is the SELECTED state.
  
  #fg[PRELIGHT] = {255, 255, 0}
  fg[PRELIGHT] = 'yellow'
  #bg[PRELIGHT] = "#089D20"
  #bg[PRELIGHT] = {8, 157, 32}
  bg[PRELIGHT] = 'forestgreen'
  #bg[PRELIGHT] = {1.0, 0, 0}
#  bg[ACTIVE] = { 1.0, 0, 0 }
#  fg[ACTIVE] = { 0, 1.0, 0 }
#  bg[NORMAL] = { 1.0, 1.0, 0 }
#  fg[NORMAL] = { .99, 0, .99 }
#  bg[INSENSITIVE] = { 1.0, 1.0, 1.0 }
#  fg[INSENSITIVE] = { 1.0, 0, 1.0 }

#GtkButton::focus-line-width = 1
#GtkButton::focus-padding = 0
GtkLabel::width-chars = 20
}

# In this example, we inherit the attributes of the "button" style and then
# override the font and background color when prelit to create a new
# "main_button" style.

style "main_button" = "button"
{
  font = "-adobe-helvetica-medium-r-normal--*-100-*-*-*-*-*-*"
  bg[PRELIGHT] = { 0.75, 0, 0 }
}

style "toggle_button" = "button"
{
  fg[NORMAL] = { 1.0, 0, 0 }
  fg[ACTIVE] = { 1.0, 0, 0 }
 
}

style "text"
{
  fg[NORMAL] = { 1.0, 1.0, 1.0 }
  font_name = "Monospace 10"
}

# These set the widget types to use the styles defined above.
# The widget types are listed in the class hierarchy, but could probably be
# just listed in this document for the users reference.

widget_class "GtkWindow" style "window"
widget_class "GtkDialog" style "window"
widget_class "GtkFileSelection" style "window"
widget_class "*GtkCheckButton*" style "toggle_button"
widget_class "*GtkRadioButton*" style "toggle_button"
widget_class "*GtkButton*" style "button"
widget_class "*GtkTextView" style "text"

# This sets all the buttons that are children of the "main window" to
# the main_button style.  These must be documented to be taken advantage of.
widget "main window.*GtkButton*" style "main_button"
"""
gtk.rc_parse_string(rc) 

#END
