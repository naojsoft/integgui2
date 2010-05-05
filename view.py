# 
#[ Eric Jeschke (eric@naoj.org) --
#  Last edit: Wed Apr 21 14:21:56 HST 2010
#]

# remove once we're certified on python 2.6
from __future__ import with_statement

# Standard library imports
import sys, os
import re, time
import threading, Queue
import Tkinter
import tkMessageBox, tkFileDialog
import logging

# Special library imports
import Pmw

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


def update_line(tw, row, val):
    """Update a line of the text widget _tw_, defined by _row_,
    with the value _val_.
    """
    tw.delete('%d.0linestart' % row, '%d.0lineend' % row)
    tw.insert('%d.0' % row, str(val))

class StatusBar(Tkinter.Frame):

    def __init__(self, master, **kwdargs):
        Tkinter.Frame.__init__(self, master)
        self.label = Tkinter.Label(self, **kwdargs)
        self.label.pack(fill='x')

    def set(self, format, *args):
        self.label.config(text=format % args)
        self.label.update_idletasks()

    def clear(self):
        self.label.config(text="")
        self.label.update_idletasks()


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
        btns = Tkinter.Frame(frame) 
        self.btns = btns

        self.btn_close = Tkinter.Button(btns, text="Close",
                                    width=10,
                                    command=self.close,
                                    activebackground="#089D20",
                                    activeforeground="#FFFF00")
        self.btn_close.pack(padx=5, pady=2, side=Tkinter.RIGHT)

        self.btn_reload = Tkinter.Button(btns, text="Reload",
                                     width=10,
                                     command=self.reload,
                                     activebackground="#089D20",
                                     activeforeground="#FFFF00")
        self.btn_reload.pack(padx=5, pady=2, side=Tkinter.RIGHT)

        self.btn_save = Tkinter.Button(btns, text="Save",
                                   width=10,
                                   command=self.save,
                                   activebackground="#089D20",
                                   activeforeground="#FFFF00")
        self.btn_save.pack(padx=5, pady=2, side=Tkinter.RIGHT)

        btns.pack(padx=2, pady=2, side=Tkinter.BOTTOM, fill='x',
                  expand=False)

        self.modified = True


    def loadbuf(self, buf):

        # get text widget
        tw = self.tw

        # insert text
        tags = ['code']
        try:
            tw.delete('1.0', 'end')
        except:
            pass
        tw.insert('end', buf, tuple(tags))

        tw.tag_configure('code', foreground="black")

        #tw.tag_raise('code')


    def load(self, filepath, buf):
        self.loadbuf(buf)
        self.filepath = filepath
        lw = self.txt.component('label')
        lw.config(text=filepath)

        
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

        res = tkMessageBox.askokcancel("Save file", 
                                       'Really save "%s"?' % filename)
        if not res:
            return

        # get text widget
        tw = self.tw
        buf = tw.get('1.0', 'end')

        try:
            out_f = open(self.filepath, 'w')
            out_f.write(buf)
            out_f.close()
            #self.statusMsg("%s saved." % self.filepath)
        except IOError, e:
            return view.popup_error("Cannot write '%s': %s" % (
                    self.filepath, str(e)))


    def close(self):
        if self.modified:
            res = tkMessageBox.askokcancel("Close Tab",
                                           'Really close tab "%s"?' % (
                    self.title))
            if not res:
                return

        super(CodePage, self).close()


class OpePage(CodePage):

    def __init__(self, frame, name, title):

        super(OpePage, self).__init__(frame, name, title)

        self.queueName = 'executer'

        txt = Pmw.ScrolledText(frame, text_wrap='none',
                               rowheader=True,
                               rowheader_width=1,
                               rowheader_padx=2, rowheader_pady=5,
                               labelpos='n', label_text=title,
                               vscrollmode='dynamic', hscrollmode='dynamic',
                               Header_foreground = 'blue')

        self.txt = txt
        self.tw = txt.component('text')
        self.tw.configure(padx=5, pady=5, highlightthickness=0)
        self.rw = txt.component('rowheader')
        self.rw.configure(highlightthickness=0)

        txt.pack(side=Tkinter.TOP, fill='both', expand=True, padx=4, pady=4)

        self.btn_execute = Tkinter.Button(self.btns, text="Exec",
                                          width=10,
                                          activebackground="#089D20",
                                          activeforeground="#FFFF00",
                                          command=lambda: view.execute(self))
        self.btn_execute.pack(padx=5, pady=2, side=Tkinter.LEFT)

        self.btn_pause = Tkinter.Button(self.btns, text="Pause",
                                        width=10,
                                        command=self.pause,
                                        activebackground="#089D20",
                                        activeforeground="#FFFF00")
        self.btn_pause.pack(padx=5, pady=2, side=Tkinter.LEFT)

        self.btn_cancel = Tkinter.Button(self.btns, text="Cancel",
                                         width=10,
                                         command=self.cancel,
                                         activebackground="#089D20",
                                         activeforeground="#FFFF00")
        self.btn_cancel.pack(padx=5, pady=2, side=Tkinter.LEFT)

        self.btn_kill = Tkinter.Button(self.btns, text="Kill",
                                       width=10,
                                       command=self.kill,
                                       activebackground="#089D20",
                                       activeforeground="#FFFF00")
        self.btn_kill.pack(padx=5, pady=2, side=Tkinter.LEFT)


    def loadbuf(self, buf):

        super(OpePage, self).loadbuf(buf)

        lines = buf.split('\n')
        header = '\n' * len(lines)
        hw = self.txt.component('rowheader')
        hw.delete('1.0', 'end')
        hw.insert('end', header)


    def load(self, filepath, buf):

        super(OpePage, self).load(filepath, buf)

        name, ext = os.path.splitext(self.filepath)
        ext = ext.lower()

        if ext in ('.ope', '.cd'):
            self.color()


    def color(self):
        tw = self.tw

        def addtags(lineno, tags):
            for tag in tags:
                tw.tag_add(tag, '%d.0 linestart' % lineno,
                           '%d.0 lineend' % lineno)
            
        buf = tw.get('1.0', 'end')
        lineno = 1
        for line in buf.split('\n'):
            line = line.strip()
            if line.startswith('###'):
                addtags(lineno, ['comment3'])
        
            elif line.startswith('##'):
                addtags(lineno, ['comment2'])
        
            elif line.startswith('#'):
                addtags(lineno, ['comment1'])

            lineno += 1

        tw.tag_configure('comment3', foreground="indian red")
        tw.tag_configure('comment2', foreground="saddle brown")
        tw.tag_configure('comment1', foreground="dark green")

        #tw.tag_lower('code')


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

        txt = Pmw.ScrolledText(frame, text_wrap='none',
                               labelpos='n', label_text=title,
                               vscrollmode='dynamic', hscrollmode='dynamic')

        self.txt = txt
        self.tw = txt.component('text')
        self.tw.configure(padx=5, pady=5, highlightthickness=0)

        txt.pack(side=Tkinter.TOP, fill='both', expand=True, padx=4, pady=4)


class TaskPage(CodePage):

    def __init__(self, frame, name, title):
        super(TaskPage, self).__init__(frame, name, title)

        txt = Pmw.ScrolledText(frame, text_wrap='none',
                               labelpos='n', label_text=title,
                               vscrollmode='dynamic', hscrollmode='dynamic')

        self.txt = txt
        self.tw = txt.component('text')
        self.tw.configure(padx=5, pady=5, highlightthickness=0)

        txt.pack(side=Tkinter.TOP, fill='both', expand=True, padx=4, pady=4)

                               
class DDCommandPage(Page):

    def __init__(self, frame, name, title):

        super(DDCommandPage, self).__init__(frame, name, title)

        self.queueName = 'executer'

        txt = Pmw.ScrolledText(frame, text_wrap='none',
                               labelpos='n', label_text=title,
                               vscrollmode='dynamic', hscrollmode='dynamic')
        self.txt = txt
        self.tw = txt.component('text')
        self.tw.configure(padx=5, pady=5, highlightthickness=0)

        txt.pack(side=Tkinter.TOP, fill='both', expand=True, padx=4, pady=4)

        # bottom buttons
        btns = Tkinter.Frame(frame) 
        self.btns = btns

        self.btn_close = Tkinter.Button(btns, text="Close",
                                    width=10,
                                    command=self.close,
                                    activebackground="#089D20",
                                    activeforeground="#FFFF00")
        self.btn_close.pack(padx=5, pady=2, side=Tkinter.RIGHT)

        self.btn_execute = Tkinter.Button(self.btns, text="Exec",
                                          width=10,
                                          activebackground="#089D20",
                                          activeforeground="#FFFF00",
                                          command=lambda: view.execute_dd(self))
        self.btn_execute.pack(padx=5, pady=2, side=Tkinter.LEFT)

        self.btn_pause = Tkinter.Button(self.btns, text="Pause",
                                        width=10,
                                        command=self.pause,
                                        activebackground="#089D20",
                                        activeforeground="#FFFF00")
        self.btn_pause.pack(padx=5, pady=2, side=Tkinter.LEFT)

        self.btn_cancel = Tkinter.Button(self.btns, text="Cancel",
                                         width=10,
                                         command=self.cancel,
                                         activebackground="#089D20",
                                         activeforeground="#FFFF00")
        self.btn_cancel.pack(padx=5, pady=2, side=Tkinter.LEFT)

        self.btn_kill = Tkinter.Button(self.btns, text="Kill",
                                       width=10,
                                       command=self.kill,
                                       activebackground="#089D20",
                                       activeforeground="#FFFF00")
        self.btn_kill.pack(padx=5, pady=2, side=Tkinter.LEFT)

        btns.pack(padx=2, pady=2, side=Tkinter.BOTTOM, fill='x',
                  expand=False)

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

        txt = Pmw.ScrolledText(frame, text_wrap='none',
                               #labelpos='n', label_text='FITS Data Frames',
                               vscrollmode='dynamic', hscrollmode='dynamic')
        self.txt = txt

        self.tw = txt.component('text')
        self.tw.configure(padx=5, pady=3, highlightthickness=0)

        self.tw.insert('0.1', '\n' * 10)

        txt.pack(fill='both', expand=True, padx=4, pady=4)


    def update_obsinfo(self, obsdict):

        self.logger.debug("obsinfo update: %s" % str(obsdict))

        if obsdict.has_key('PROP-ID'):
            update_line(self.tw, 1, 'Prop-Id: %s' % obsdict['PROP-ID'])
        if obsdict.has_key('TIMER_SEC'):
            self.set_timer(obsdict['TIMER_SEC'])
        
        offset = 2
        for i in xrange(1, 6):
            try:
                val = str(obsdict['OBSINFO%d' % i])
                update_line(self.tw, i+offset, val)
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


    def timer_interval(self, rootw):
        self.logger.debug("timer: %d sec" % self.timer_val)
        self.timer_val -= 1
        update_line(self.tw, 2, 'Timer: %s' % str(self.timer_val))
        if self.timer_val > 0:
            rootw.after(1000, self.timer_interval, rootw)
        else:
            # Do something when timer expires?
            pass
        

class LogPage(Page):

    def __init__(self, frame, name, title):

        super(LogPage, self).__init__(frame, name, title)

        txt = Pmw.ScrolledText(frame, text_wrap='none',
                               #labelpos='n', label_text='FITS Data Frames',
                               vscrollmode='dynamic', hscrollmode='dynamic')
        self.txt = txt

        self.tw = txt.component('text')
        self.tw.configure(padx=5, pady=3, highlightthickness=0)

        txt.pack(fill='both', expand=True, padx=4, pady=4)

        # bottom buttons
        btns = Tkinter.Frame(frame) 
        self.btns = btns

        self.btn_close = Tkinter.Button(btns, text="Close",
                                    width=10,
                                    command=self.close,
                                    activebackground="#089D20",
                                    activeforeground="#FFFF00")
        self.btn_close.pack(padx=5, pady=2, side=Tkinter.RIGHT)

        btns.pack(padx=2, pady=2, side=Tkinter.BOTTOM, fill='x',
                  expand=False)


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
            self.tw.insert('end', data)
            self.tw.see('end')

        # READ GLOBAL
        view.w.root.after(100, self.poll)


class FramesPage(Page):

    def __init__(self, frame, name, title):

        super(FramesPage, self).__init__(frame, name, title)

        txt = Pmw.ScrolledText(frame, text_wrap='none',
                               columnheader=True,
                               columnheader_width=1,
                               columnheader_padx=5, columnheader_pady=3,
                               labelpos='n', label_text='FITS Data Frames',
                               vscrollmode='dynamic', hscrollmode='dynamic')
        self.txt = txt

        self.tw = txt.component('text')
        self.tw.configure(padx=5, pady=3, highlightthickness=0)

        self.cw = txt.component('columnheader')
        self.cw.configure(highlightthickness=0)

        txt.pack(fill='both', expand=True, padx=4, pady=4)


    def update_frame(self, frameinfo):
        self.logger.debug("UPDATE FRAME: %s" % str(frameinfo))
        tw = self.tw

        frameid = frameinfo.frameid
        with self.lock:
            if hasattr(frameinfo, 'row'):
                row = frameinfo.row
                #index = tw.index(frameid)
                index = 'none'
                self.logger.debug("row=%d index=%s" % (row, index))
                tw.delete('%s.first' % frameid, '%s.last' % frameid)
                tw.insert('%d.0' % row, fits.format_str % frameinfo,
                          (frameid,))

            else:
                row, col = str(tw.index('end')).split('.')
                row = int(row)
                self.logger.debug("row is %d" % row)
                frameinfo.row = row
                tw.insert('end', fits.format_str % frameinfo,
                          (frameid,))

        
    def update_frames(self, framelist):

        # Create header
        self.cw.delete('1.0', 'end')
        self.cw.insert('1.0', fits.header)

        # Delete frames text
        self.tw.delete('1.0', 'end')
        
        # add frames
        for frameinfo in framelist:
            self.update_frame(frameinfo)


class skMonitorPage(Page):

    def __init__(self, frame, name, title):

        self.nb = Pmw.NoteBook(frame, tabpos='n')
        self.nb.pack(padx=2, pady=2, fill='both', expand=1)

        super(skMonitorPage, self).__init__(frame, name, title)

        self.track = {}
        self.pages = {}
        self.pagelist = []
        self.pagelimit = 10


    def insert_ast(self, tw, text):

        def insert(text, tags):
            try:
                foo = text.index("<div ")

            except ValueError:
                tw.insert('end', text, tuple(tags))
                return

            match = re.match(r'^\<div\sclass=([^\>]+)\>', text[foo:],
                             re.MULTILINE | re.DOTALL)
            if not match:
                tw.insert('end', 'ERROR 1: %s' % text, tuple(tags))
                return

            num = int(match.group(1))
            regex = r'^(.*)\<div\sclass=%d\>(.+)\</div\sclass=%d\>(.*)$' % (
                num, num)
            #print regex
            match = re.match(regex, text, re.MULTILINE | re.DOTALL)
            if not match:
                tw.insert('end', 'ERROR 2: %s' % text, tuple(tags))
                return

            tw.insert('end', match.group(1), tuple(tags))

            serial_num = '%d' % num
            tw.tag_config(serial_num, foreground="black")
            newtags = [serial_num]
            newtags.extend(tags)
            insert(match.group(2), newtags)

            insert(match.group(3), tags)

        tw.tag_configure('code', foreground="black")
        insert(text, ['code'])
        tw.tag_raise('code')


    def astIdtoTitle(self, ast_id):
        page = self.pages[ast_id]
        return page.title
        
    def delpage(self, ast_id):
        with self.lock:
            #title = self.astIdtoTitle(ast_id)
            self.nb.delete(ast_id)
            del self.pages[ast_id]

    def addpage(self, ast_id, title, text):
        with self.lock:

            # Make room for new pages
            while len(self.pagelist) >= self.pagelimit:
                oldast_id = self.pagelist.pop(0)
                self.delpage(oldast_id)
                
            page = self.nb.add(ast_id, tab_text=title)
            #page.focus_set()

            txt = Pmw.ScrolledText(page, text_wrap='none',
                                   vscrollmode='dynamic', hscrollmode='dynamic')
            tw = txt.component('text')
            tw.configure(borderwidth=2, padx=10, pady=5)

            self.insert_ast(tw, text)
            txt.pack(fill='both', expand=True, padx=4, pady=4)

            self.nb.setnaturalsize()

            try:
                page = self.pages[ast_id]
                page.tw = tw
                page.title = title
            except KeyError:
                self.pages[ast_id] = Bunch.Bunch(tw=tw, title=title)

            self.pagelist.append(ast_id)
            self.nb.selectpage(ast_id)

        
    def change_text(self, page, ast_num, **kwdargs):
        page.tw.tag_config(ast_num, **kwdargs)
        page.tw.tag_raise(ast_num)
        try:
            page.tw.see('%s.first' % ast_num)
        except KeyError, e:
            # this throws a KeyError due to a bug in Python megawidgets
            # but it is benign
            self.logger.error(str(e))
            pass


    def update_time(self, page, ast_num, vals, time_s):

        # GLOBAL VAR READ
        if not view.show_times.get():
            return

        if vals.has_key('time_added'):
            length = vals['time_added']
            page.tw.delete('%s.first' % ast_num, '%s.first+%dc' % (ast_num, length))
            
        vals['time_added'] = len(time_s)
        page.tw.insert('%s.first' % ast_num, time_s, (ast_num,))
        

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
                pos = page.tw.index('%s.first' % ast_num)
                page.tw.delete('%s.first' % ast_num, '%s.last' % ast_num)
                page.tw.insert(pos, cmd_str, (ast_num,))
                vals['inserted'] = True
                try:
                    del vals['time_added']
                except KeyError:
                    pass

        if vals.has_key('task_error'):
            self.change_text(page, ast_num, foreground="red", background="lightyellow")
            page.tw.insert('%s.last' % ast_num, '\n ==> ' + vals['task_error'],
                           (ast_num,))
            
            # audible warnings
            # GLOBAL
            view.audible_warn(cmd_str, vals)

        elif vals.has_key('task_end'):
            if vals.has_key('task_start'):
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

                # TODO: what if this page has already been deleted?
                # GLOBAL VAR READ
                if view.save_decode_result.get():
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
                pos = page.tw.index('%s.first' % ast_num)
                page.tw.delete('%s.first' % ast_num, '%s.last' % ast_num)
                page.tw.insert(pos, vals['ast_str'],
                               (ast_num,))

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
            

    def parsefile(self, filepath):
        bnch = self.parser.parse_skfile(filepath)
        if bnch.errors == 0:
            (path, filename) = os.path.split(filepath)

            text = self.issue.issue(bnch.ast, [])
            print text
            #print dir(txt)
            self.addpage(filename, filename, text)
            
        
class Launcher(object):
    
    def __init__(self, frame, name, title, execfn):
        self.frame = frame
        self.params = Bunch.Bunch()
        self.paramList = []
        self.row = 1
        self.col = 1
        self.btn_width = 20
        self.execfn = execfn

        self.btn_exec = Tkinter.Button(frame, text=title,
                                       relief='raised',
                                       activebackground="#089D20",
                                       activeforeground="#FFFF00",
                                       command=self.execute,
                                       width=self.btn_width)
        self.btn_exec.grid(row=1, column=0, padx=1, sticky='ew')
        

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

        self.fr = Pmw.ScrolledFrame(frame, 
                               #labelpos='n', label_text=title,
                               vscrollmode='dynamic', hscrollmode='dynamic')

        self.fw = self.fr.component('frame')
        self.fw.configure(padx=2, pady=2, highlightthickness=0)

        self.llist = LauncherList(self.fw, name, title,
                                  self.execute)

        self.fr.pack(side=Tkinter.TOP, fill='both', expand=True,
                     padx=4, pady=4)

        # bottom buttons
        btns = Tkinter.Frame(frame) 
        self.btns = btns

        self.btn_close = Tkinter.Button(btns, text="Close",
                                    width=10,
                                    command=self.close,
                                    activebackground="#089D20",
                                    activeforeground="#FFFF00")
        self.btn_close.pack(padx=5, pady=2, side=Tkinter.RIGHT)

        self.btn_pause = Tkinter.Button(self.btns, text="Pause",
                                        width=10,
                                        command=self.pause,
                                        activebackground="#089D20",
                                        activeforeground="#FFFF00")
        self.btn_pause.pack(padx=5, pady=2, side=Tkinter.LEFT)

        self.btn_cancel = Tkinter.Button(self.btns, text="Cancel",
                                         width=10,
                                         command=self.cancel,
                                         activebackground="#089D20",
                                         activeforeground="#FFFF00")
        self.btn_cancel.pack(padx=5, pady=2, side=Tkinter.LEFT)

        btns.pack(padx=2, pady=2, side=Tkinter.BOTTOM, fill='x',
                  expand=False)

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

        self.widget = Pmw.NoteBook(frame, tabpos='n')
        self.widget.pack(padx=2, pady=2, fill='both', expand=1)

        # Holds my pages
        self.pages = {}
        self.lock = threading.RLock()


    def addpage(self, name, title, klass):
        with self.lock:
            try:
                pageobj = self.pages[title]
                raise Exception("A page with name '%s' already exists!" % name)

            except KeyError:
                pass

            page = self.widget.add(name, tab_text=title)
            page.focus_set()
            pagefr = self.widget.page(name)

            pageobj = klass(pagefr, name, title)

            # Some attributes we force on our children
            pageobj.logger = self.logger
            # ?? cyclical reference causes problems for gc?
            pageobj.parent = self

            self.pages[name] = pageobj
            
            #self.widget.setnaturalsize()
            self.widget.selectpage(name)
            return pageobj

        
    def delpage(self, name):
        with self.lock:
            del self.pages[name]
            
            self.widget.delete(name)

    def delall(self):
        with self.lock:
            for name in self.pages.keys():
                self.delpage(name)
            
    def select(self, name):
        self.widget.selectpage(name)

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

        paned = Pmw.PanedWidget(frame, orient='horizontal',
                                handlesize=16) 
        self.hframe = paned
        paned.pack(fill='both', expand=True)

        paned.add('lframe', size=0.35)
        paned.add('rframe', size=0.65)
        self.lframe = paned.pane('lframe')
        self.rframe = paned.pane('rframe')

        lpane = Pmw.PanedWidget(self.lframe, orient='vertical',
                                handlesize=16)
        self.lpane = lpane
        lpane.add('ul')
        lpane.add('ll')
        lpane.pack(fill='both', expand=True)

        rpane = Pmw.PanedWidget(self.rframe, orient='vertical',
                                handlesize=16)
        self.rpane = rpane
        rpane.add('ur')
        rpane.add('lr')
        rpane.pack(fill='both', expand=True)

        self.ws_fr = {
            'll': lpane.pane('ll'),
            'ul': lpane.pane('ul'),
            'lr': rpane.pane('lr'),
            'ur': rpane.pane('ur'),
            }

        self.ws = {}


    def get_wsframe(self, name):
        return self.ws_fr[name]

    def addws(self, loc, name, title):

        frame = self.get_wsframe(loc)

        ws = Workspace(frame, name, title)
        # Some attributes we force on our children
        ws.logger = self.logger
        
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

        root = Tkinter.Tk()
        Pmw.initialise(root)
        root.title('Gen2 Integrated GUI II')

        self.w.root = root
        self.w.root.protocol("WM_DELETE_WINDOW", self.quit)

        root.tk_setPalette(background=color_bg,
                           foreground='black')

        #root.option_add('*background', color_blue)
        #root.option_add('*foreground', 'black')
        root.option_add('*Text*background', color_white)
        root.option_add('*Entry*background', color_white)
        #root.option_add('*Text*highlightthickness', 0)
        root.option_add('*Button*activebackground', '#089D20')
        root.option_add('*Button*activeforeground', '#FFFF00')

        self.fixedFont = Pmw.logicalfont('Fixed')

        root.option_add('*Text*font', self.fixedFont)

        self.w.mframe = Tkinter.Frame(self.w.root, padx=2, pady=2)

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

        #self.w.mframe.columnconfigure(0, weight=10)
        #self.w.mframe.rowconfigure(0, weight=10)

        #self.w.mframe.grid(column=0, row=0, sticky='wens')

        self.w.mframe.pack(fill='both', expand=True)

        self.add_menus()
        self.add_dialogs()
        self.closelog(self.w.log)
        self.add_statusbar()



    def add_menus(self):
        menubar = Tkinter.Menu(self.w.root, relief='flat')

        # create a pulldown menu, and add it to the menu bar
        filemenu = Tkinter.Menu(menubar, tearoff=0)
        filemenu.add('command', label="Load ope", command=self.gui_load_ope)
        filemenu.add('command', label="Config from session",
                     command=self.reconfig)
        filemenu.add('command', label="Load log", command=self.gui_load_log)
        filemenu.add('command', label="Load sk", command=self.gui_load_sk)
        filemenu.add('command', label="Load task", command=self.gui_load_task)
        filemenu.add('command', label="Load launcher",
                     command=self.gui_load_launcher)
        #filemenu.add('command', label="Show Log", command=self.showlog)
        filemenu.add_separator()
        filemenu.add_command(label="Exit", command=self.quit)
        menubar.add_cascade(label="File", menu=filemenu)

        logmenu = Tkinter.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Logs", menu=logmenu)

        optionmenu = Tkinter.Menu(menubar, tearoff=0)
        self.save_decode_result = Tkinter.IntVar(0)
        #self.save_decode_result.set(0)
        optionmenu.add('checkbutton', label="Save Decode Result", 
                       variable=self.save_decode_result)
        self.show_times = Tkinter.IntVar(0)
        #self.show_times.set(0)
        optionmenu.add('checkbutton', label="Show Times", 
                       variable=self.show_times)
        self.audible_errors = Tkinter.IntVar(0)
        self.audible_errors.set(1)
        optionmenu.add('checkbutton', label="Audible Errors", 
                       variable=self.audible_errors)
        menubar.add_cascade(label="Option", menu=optionmenu)

        self.w.root.config(menu=menubar)


    def add_statusbar(self):
        self.w.status = StatusBar(self.w.root, text="", 
                                  relief='flat', anchor='w')
        self.w.status.pack(side='bottom', fill='x')


    def statusMsg(self, format, *args):
        if not format:
            self.w.status.clear()
        else:
            self.w.status.set(format, *args)


    def add_dialogs(self):

        # pop-up log file
        self.w.log = Pmw.TextDialog(self.w.root, scrolledtext_labelpos='n',
                                    title='Log',
                                    buttons=('Close',),
                                    defaultbutton=None,
                                    command=self.closelog)
                                    #label_text = 'Log')        
        self.logqueue = Queue.Queue()
        guiHdlr = ssdlog.QueueHandler(self.logqueue)
        fmt = logging.Formatter(ssdlog.STD_FORMAT)
        guiHdlr.setFormatter(fmt)
        guiHdlr.setLevel(logging.INFO)
        self.logger.addHandler(guiHdlr)


    def setPos(self, geom):
        self.w.root.geometry(geom)


    def closelog(self, w):
        # close log window
        self.w.log.withdraw()
        
    def showlog(self):
        # open log window
         self.w.log.show()


#     def set_controller(self, controller):
#         self.controller = controller

    def logupdate(self):
        try:
            while True:
                msgstr = self.logqueue.get(block=False)

                self.w.log.insert('end', msgstr + '\n')

        except Queue.Empty:
            self.w.root.after(200, self.logupdate)
    
    def popup_error(self, errstr):
        tkMessageBox.showerror("IntegGUI Error", errstr)


    def readfile(self, filepath):

        in_f = open(filepath, 'r')
        buf = in_f.read()
        in_f.close()

        return buf


    def gui_load_ope(self):
        initialdir = os.path.join(os.environ['HOME'], 'Procedure')
        
        filepath = tkFileDialog.askopenfilename(title="Load OPE file",
                                                initialdir=initialdir,
                                                parent=self.w.root)
        if not filepath:
            return

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
        
        filepath = tkFileDialog.askopenfilename(title="Follow log file",
                                                initialdir=initialdir,
                                                parent=self.w.root)
        if not filepath:
            return

        self.load_log(filepath)


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
        
        filepath = tkFileDialog.askopenfilename(title="Load sk file",
                                                initialdir=initialdir,
                                                parent=self.w.root)
        if not filepath:
            return

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
        
        filepath = tkFileDialog.askopenfilename(title="Load task file",
                                                initialdir=initialdir,
                                                parent=self.w.root)
        if not filepath:
            return

        try:
            buf = self.readfile(filepath)

            dirname, filename = os.path.split(filepath)

            page = self.exws.addpage(filepath, filename, TaskPage)
            page.load(filepath, buf)

        except Exception, e:
            self.popup_error("Cannot load '%s': %s" % (
                    filepath, str(e)))


    def gui_load_launcher(self):
        initialdir = os.path.join(os.environ['CONFHOME'], 'product',
                                  'file', 'Launchers')
        
        filepath = tkFileDialog.askopenfilename(title="Load launcher file",
                                                initialdir=initialdir,
                                                parent=self.w.root)
        if not filepath:
            return

        self.load_launcher(filepath)


    def load_launcher(self, filepath):
        try:
            buf = self.readfile(filepath)

            dirname, filename = os.path.split(filepath)

            match = re.match(r'^OSSO_ICmdUnit(.+)\.def$', filename)
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


    def get_launcher_path(self, insname):

        filename = 'OSSO_ICmdUnit%s.def' % insname.upper()
        filepath = os.path.join(os.environ['CONFHOME'], 'product',
                                  'file', 'Launchers', filename)
        return filepath

        
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

    def quit(self):
        # TODO: check for unsaved buffers
        self.ev_quit.set()
        sys.exit(0)

    def execute(self, opepage):
        """Callback when the EXEC button is pressed.
        """
        queueObj = self.queue['executer']

        # Check whether we are busy executing a command here
        # and popup an error message if so
        if queueObj.executingP():
            self.popup_error("Commands are executing!")
            return

        tw = opepage.tw
        #self.clear_marks(opepage)

        try:
            # Get the range of text selected
            first = tw.index(Tkinter.SEL_FIRST)
            frow, fcol = str(first).split('.')
                        
            last = tw.index(Tkinter.SEL_LAST)
            lrow, lcol = str(last).split('.')

            # flush queue--selection will override
            queueObj.flush()

        except Exception, e:
            if not queueObj.enableIfPending():
                self.popup_error("No queued commands and no mouse selection!")
            return

        # Break selection into individual lines
        tags = []
        frow = int(frow)

        for i in xrange(int(lrow)+1-frow):

            row = frow+i

            # skip comments and blank lines
            cmd = tw.get('%d.0linestart' % row, '%d.0lineend' % row)
            if cmd.startswith('#') or (len(cmd) == 0):
                continue
            self.logger.debug("cmd=%s" % (cmd))

            # tag the text so we can manipulate it later
            tag = self.get_tag('ope%d')
            tw.tag_add(tag, '%d.0linestart' % row, '%d.0lineend' % row)

            tags.append(Bunch.Bunch(tag=tag, opepage=opepage,
                                    type='opepage'))

        # deselect the region
        tw.tag_remove(Tkinter.SEL, '1.0', 'end')

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
        if queueObj.executingP():
            self.popup_error("Commands are executing!")
            return

        tw = opepage.tw

        # tag the text so we can manipulate it later
        tag = self.get_tag('dd%d')

        tags = [Bunch.Bunch(tag=tag, opepage=opepage,
                            type='cmdpage')]

        # deselect the region
        tw.tag_remove(Tkinter.SEL, '1.0', 'end')

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
        tw = bnch.opepage.tw
        txtbuf = tw.get('1.0', 'end').strip()

        if bnch.type == 'cmdpage':
            # remove trailing semicolon, if present
            cmdstr = txtbuf
            if cmdstr.endswith(';'):
                cmdstr = cmdstr[:-1]

            return cmdstr

        # <-- Page is an OPE page type

        # Now get the command from the text widget
        cmdstr = tw.get('%s.first' % bnch.tag, '%s.last' % bnch.tag).strip()

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
        rw = opepage.rw
        rw.delete('1.0', 'end')


    def mark_exec(self, bnch, char, queueName):

        # Get the entire OPE buffer
        tw = bnch.opepage.tw
        row, col = str(tw.index('end')).split('.')
        len = int(row)
        index = tw.index('%s.first' % bnch.tag)

        rw = bnch.opepage.rw
        #rw.delete('1.0', 'end')
        #rw.insert('1.0', '\n' * len)

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

        self.w.root.after(100, self.popup_error, [str(e)])
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

        if not self.audible_errors.get():
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
        

    def update_obsinfo(self, infodict):
        self.logger.info("OBSINFO=%s" % str(infodict))
        self.obsinfo.update_obsinfo(infodict)

    
    def process_ast(self, ast_id, vals):
        self.monpage.process_ast(ast_id, vals)

    def process_task(self, path, vals):
        self.monpage.process_task(path, vals)

    def mainloop(self):
        self.w.root.mainloop()


#END
