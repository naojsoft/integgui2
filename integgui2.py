#! /usr/bin/env python
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
import Monitor
import Bunch
import cfg.g2soss
from cfg.INS import INSdata
import ssdlog

# Local integgui2 imports
import ope, fits
import controller as igctrl
import launcher

color_blue = '#cae1ff'     # pale blue
color_green = '#c1ffc1'     # pale green
color_yellow = '#fafad2'     # cream
#color_white = 'whitesmoke'
color_white = 'white'

color_bg = 'light grey'

# Define sounds used in IntegGUI
sound = Bunch.Bunch(success='doorbell.au',
                    failure='splat.au')


gui = None
controller = None


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

        # every page has a lock
        self.lock = threading.RLock()

    def close(self):
        # parent attribute is added by parent workspace
        self.parent.delpage(self.name)


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
        self.btn_close.pack(padx=5, pady=4, side=Tkinter.RIGHT)

        self.btn_reload = Tkinter.Button(btns, text="Reload",
                                     width=10,
                                     command=self.reload,
                                     activebackground="#089D20",
                                     activeforeground="#FFFF00")
        self.btn_reload.pack(padx=5, pady=4, side=Tkinter.RIGHT)

        self.btn_save = Tkinter.Button(btns, text="Save",
                                   width=10,
                                   command=self.save,
                                   activebackground="#089D20",
                                   activeforeground="#FFFF00")
        self.btn_save.pack(padx=5, pady=4, side=Tkinter.RIGHT)

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
            return gui.popup_error("Cannot write '%s': %s" % (
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
            return gui.popup_error("Cannot write '%s': %s" % (
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
                                          command=lambda: gui.execute(self))
        self.btn_execute.pack(padx=5, pady=4, side=Tkinter.LEFT)

        self.btn_pause = Tkinter.Button(self.btns, text="Pause",
                                        width=10,
                                        command=self.pause,
                                        activebackground="#089D20",
                                        activeforeground="#FFFF00")
        self.btn_pause.pack(padx=5, pady=4, side=Tkinter.LEFT)

        self.btn_cancel = Tkinter.Button(self.btns, text="Cancel",
                                         width=10,
                                         command=self.cancel,
                                         activebackground="#089D20",
                                         activeforeground="#FFFF00")
        self.btn_cancel.pack(padx=5, pady=4, side=Tkinter.LEFT)

        self.btn_kill = Tkinter.Button(self.btns, text="Restart TM",
                                       width=10,
                                       command=self.kill,
                                       activebackground="#089D20",
                                       activeforeground="#FFFF00")
        self.btn_kill.pack(padx=5, pady=4, side=Tkinter.LEFT)

        self.queueName = 'executer'


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
        self.btn_close.pack(padx=5, pady=4, side=Tkinter.RIGHT)

        self.btn_execute = Tkinter.Button(self.btns, text="Exec",
                                          width=10,
                                          activebackground="#089D20",
                                          activeforeground="#FFFF00",
                                          command=lambda: gui.execute_dd(self))
        self.btn_execute.pack(padx=5, pady=4, side=Tkinter.LEFT)

        self.btn_pause = Tkinter.Button(self.btns, text="Pause",
                                        width=10,
                                        command=self.pause,
                                        activebackground="#089D20",
                                        activeforeground="#FFFF00")
        self.btn_pause.pack(padx=5, pady=4, side=Tkinter.LEFT)

        self.btn_cancel = Tkinter.Button(self.btns, text="Cancel",
                                         width=10,
                                         command=self.cancel,
                                         activebackground="#089D20",
                                         activeforeground="#FFFF00")
        self.btn_cancel.pack(padx=5, pady=4, side=Tkinter.LEFT)

        self.btn_kill = Tkinter.Button(self.btns, text="Restart TM",
                                       width=10,
                                       command=self.kill,
                                       activebackground="#089D20",
                                       activeforeground="#FFFF00")
        self.btn_kill.pack(padx=5, pady=4, side=Tkinter.LEFT)

        btns.pack(padx=2, pady=2, side=Tkinter.BOTTOM, fill='x',
                  expand=False)

        self.queueName = 'executer'

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
        self.timer_interval(gui.w.root)


    def timer_interval(self, rootw):
        self.logger.debug("timer: %d sec" % self.timer_val)
        self.timer_val -= 1
        update_line(self.tw, 2, 'Timer: %s' % str(self.timer_val))
        if self.timer_val > 0:
            rootw.after(1000, self.timer_interval, rootw)
        else:
            # Do something when timer expires?
            pass
        

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

        super(skMonitorPage, self).__init__(frame, name, title)

        self.nb = Pmw.NoteBook(frame, tabpos='n')
        self.nb.pack(padx=2, pady=2, fill='both', expand=1)

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
        if not gui.show_times.get():
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
            gui.audible_warn(cmd_str, vals)

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
                if gui.save_decode_result.get():
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
            
        
class LauncherPage(Page):

    def __init__(self, frame, name, title):
        super(LauncherPage, self).__init__(frame, name, title)

        self.fr = Pmw.ScrolledFrame(frame, 
                               #labelpos='n', label_text=title,
                               vscrollmode='dynamic', hscrollmode='dynamic')

        self.fw = self.fr.component('frame')
        #self.fw.configure(padx=5, pady=5, highlightthickness=0)

        self.llist = launcher.LauncherList(self.fw, name, title)

        self.fr.pack(side=Tkinter.TOP, fill='both', expand=True,
                     padx=4, pady=4)

    def load(self, buf):
        self.llist.loadLauncher(buf)

                               
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

    def select(self, name):
        self.widget.selectpage(name)


      
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


class IntegGUI(object):

    def __init__(self, parent, logger, ev_quit, **kwdargs):

        self.logger = logger
        self.ev_quit = ev_quit

        self.w = Bunch.Bunch()
        self.w.root = parent
        self.w.root.protocol("WM_DELETE_WINDOW", self.quit)

        parent.tk_setPalette(background=color_bg,
                             foreground='black')

        #parent.option_add('*background', color_blue)
        #parent.option_add('*foreground', 'black')
        parent.option_add('*Text*background', color_white)
        #parent.option_add('*Text*highlightthickness', 0)
        parent.option_add('*Button*activebackground', '#089D20')
        parent.option_add('*Button*activeforeground', '#FFFF00')

        self.fixedFont = Pmw.logicalfont('Fixed')

        parent.option_add('*Text*font', self.fixedFont)

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

        self.logger = logger
        self.ev_quit = ev_quit
        self.__dict__.update(kwdargs)
        self.lock = threading.RLock()

        # Used for tagging commands
        self.cmdcount = 0

        # command queues
        self.queue = Bunch.Bunch(executer=[], launcher=[])
        self.executing = threading.Event()


    def add_menus(self):
        menubar = Tkinter.Menu(self.w.root, relief='flat')

        # create a pulldown menu, and add it to the menu bar
        filemenu = Tkinter.Menu(menubar, tearoff=0)
        filemenu.add('command', label="Load ope", command=self.gui_load_ope)
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

        try:
            buf = self.readfile(filepath)

            dirname, filename = os.path.split(filepath)

            match = re.match(r'^OSSO_ICmdUnit(.+)\.def$', filename)
            if not match:
                return

            name = match.group(1).replace('_', ' ')
            page = self.lws.addpage(name, name, LauncherPage)
            page.load(buf)

        except Exception, e:
            self.popup_error("Cannot load '%s': %s" % (
                    filepath, str(e)))


    def quit(self):
        # TODO: check for unsaved buffers
        self.ev_quit.set()
        sys.exit(0)


    def execute(self, opepage):
        """Callback when the EXEC button is pressed.
        """
        # Check whether we are busy executing a command here
        # and popup an error message if so
        if self.executing.isSet():
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
            while len(self.queue.executer) > 0:
                bnch = self.queue.executer.pop(0)

        except Exception, e:
            if len(self.queue.executer) > 0:
                self.executing.set()
            else:
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
            tag = 'exec%d' % self.cmdcount
            self.cmdcount += 1
            tw.tag_add(tag, '%d.0linestart' % row, '%d.0lineend' % row)

            tags.append(Bunch.Bunch(tag=tag, opepage=opepage))

        # deselect the region
        tw.tag_remove(Tkinter.SEL, '1.0', 'end')

        # Add tags to queue
        with self.lock:
            self.queue.executer.extend(tags)
            #self.logger.debug("Queue 'executer': %s" % (self.queue.executer))

        # Enable executor thread to proceed
        self.executing.set()

            
    def execute_dd(self, opepage):
        """Callback when the EXEC button is pressed.
        """
        # Check whether we are busy executing a command here
        # and popup an error message if so
        if self.executing.isSet():
            self.popup_error("Commands are executing!")
            return

        tw = opepage.tw

        # tag the text so we can manipulate it later
        tag = 'dd%d' % self.cmdcount
        self.cmdcount += 1
        tw.tag_add(tag, '1.0', 'end')

        tags = [Bunch.Bunch(tag=tag, opepage=opepage)]

        # deselect the region
        tw.tag_remove(Tkinter.SEL, '1.0', 'end')

        # Add tags to queue
        with self.lock:
            self.queue.executer.extend(tags)
            #self.logger.debug("Queue 'executer': %s" % (self.queue.executer))

        # Enable executor thread to proceed
        self.executing.set()

            
    def get_opecmd(self, bnch):
        """Called to get a command string from the GUI.
        """

        # Get the entire OPE buffer
        tw = bnch.opepage.tw
        opebuf = tw.get('1.0', 'end')

        # Now get the command
        cmdstr = tw.get('%s.first' % bnch.tag, '%s.last' % bnch.tag)

        # Is this an ope page or a dd cmd page?
        if bnch.tag.startswith('dd'):
            return cmdstr

        # Resolve all variables/macros
        try:
            self.logger.debug("Unprocessed command is: %s" % cmdstr)
            p_cmdstr = ope.getCmd(opebuf, cmdstr)
            self.logger.debug("Processed command is: %s" % p_cmdstr)

            return p_cmdstr

        except Exception, e:
            errstr = "Error parsing command: %s" % (str(e))
            raise Exception(errstr)
            

    def clear_marks(self, opepage):
        rw = opepage.rw
        rw.delete('1.0', 'end')


    def mark_exec(self, bnch, char, queueName):

        if bnch.tag.startswith('dd'):
            return

        # Get the entire OPE buffer
        tw = bnch.opepage.tw
        row, col = str(tw.index('end')).split('.')
        len = int(row)
        index = tw.index('%s.first' % bnch.tag)

        rw = bnch.opepage.rw
        #rw.delete('1.0', 'end')
        #rw.insert('1.0', '\n' * len)

        rw.insert(index, char)

        for nbnch in self.queue[queueName][1:]:
            index = tw.index('%s.first' % nbnch.tag)
            rw.insert(index, 'S')


    def get_queue(self, queueName):

        if not self.executing.isSet():
            raise igctrl.QueueEmpty('Queue %s is empty' % queueName)

        with self.lock:
            try:
                bnch = self.queue[queueName][0]
            except IndexError:
                raise igctrl.QueueEmpty('Queue %s is empty' % queueName)

        cmdstr = self.get_opecmd(bnch)

        #self.clear_marks()
        self.mark_exec(bnch, 'X', queueName)
        
        return bnch, cmdstr


    def feedback_noerror(self, queueName, bnch, res):

        self.mark_exec(bnch, 'D', queueName)
        #self.make_sound(cmd_ok)
        
        # Remove tagged command
        with self.lock:
            try:
                self.queue[queueName].remove(bnch)
            except ValueError:
                pass

            if len(self.queue[queueName]) == 0:
                self.executing.clear()

                # Bing Bong!
                self.playSound(sound.success)

           
    def feedback_error(self, queueName, bnch, e):

        self.executing.clear()

        if bnch:
            self.mark_exec(bnch, 'E', queueName)

            # reselect the region
            #tw = bnch.opepage.tw
            #for nbnch in self.queue[queueName]:
            #    tw.tag_add(Tkinter.SEL, 
            #               '%s.first' % nbnch.tag,
            #               '%s.last' % nbnch.tag)

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
        soundpath = os.path.join(cfg.g2soss.producthome, 'file/Sounds', soundfile)
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


def main(options, args):
    
    global controller, gui

    # Create top level logger.
    logger = ssdlog.make_logger('integgui2', options)

    ro.init()

    root = Tkinter.Tk()
    Pmw.initialise(root)
    title='Gen2 Integrated GUI II'
    root.title(title)

    ev_quit = threading.Event()

    # make a name for our monitor
    myMonName = options.name

    # monitor channels we are interested in
    channels = options.channels.split(',')

    # Create a local monitor
    mymon = Monitor.Monitor(myMonName, logger, numthreads=20)

    gui = IntegGUI(root, logger, ev_quit)

    controller = igctrl.IntegController(logger, ev_quit, mymon,
                                        options)

    #gui.set_controller(controller)
    controller.set_view(gui)

    # Configure for currently allocated instrument
    if options.instrument:
        insname = options.instrument
    else:
        insname = controller.get_alloc_instrument()
    controller.set_instrument(insname)

    if options.geometry:
        gui.setPos(options.geometry)
    gui.logupdate()

    # Subscribe our callback functions to the local monitor
    # Task info
    channels = [options.taskmgr, 'g2task']
    mymon.subscribe_cb(controller.arr_taskinfo, controller.arr_taskinfo, 
                       channels)
    
    # Obsinfo
    ig_ch = options.taskmgr + '-ig'
    mymon.subscribe_cb(controller.arr_obsinfo, controller.arr_obsinfo, 
                       [ig_ch])
    channels.append(ig_ch)

    # Fits info
    mymon.subscribe_cb(controller.arr_fitsinfo, controller.arr_fitsinfo, 
                       ['frames'])
    channels.append('frames')

    # TODO: sessions

    # Create network callable object for notifications
    notify_obj = fits.IntegGUINotify(gui.framepage, options.fitsdir)
    notify_obj.update_framelist()
    
    svc = ro.remoteObjectServer(svcname=options.svcname,
                                obj=notify_obj, logger=logger,
                                port=options.port,
                                ev_quit=ev_quit,
                                usethread=True)
    
    # Load any files specified on the command line
    #for opefile in args:
    #    gui.load_ope(opefile)

    server_started = False
    ro_server_started = False
    try:
        # Startup monitor threadpool
        mymon.start(wait=True)
        # start_server is necessary if we are subscribing, but not if only
        # publishing
        mymon.start_server(wait=True, port=options.monport)
        server_started = True

        # subscribe our monitor to the central monitor hub
        mymon.subscribe_remote(options.monitor, channels, ())

        controller.start_executors()

        svc.ro_start(wait=True)
        ro_server_started = True

        try:
            root.mainloop()

        except KeyboardInterrupt:
            logger.error("Received keyboard interrupt!")

    finally:
        if ro_server_started:
            svc.ro_stop(wait=True)
        if server_started:
            mymon.stop_server(wait=True)
        mymon.stop(wait=True)
    
    logger.info("Exiting Gen2/SCM IntegGUI II...")
    gui.quit()
    

# Create demo in root window for testing.
if __name__ == '__main__':
  
    from optparse import OptionParser

    usage = "usage: %prog [options]"
    optprs = OptionParser(usage=usage, version=('%%prog'))
    
    optprs.add_option("--debug", dest="debug", default=False,
                      action="store_true",
                      help="Enter the pdb debugger on main()")
    optprs.add_option("-c", "--channels", dest="channels", default='taskmgr0,g2task',
                      metavar="LIST",
                      help="Subscribe to the comma-separated LIST of channels")
    optprs.add_option("--display", dest="display", metavar="HOST:N",
                      help="Use X display on HOST:N")
    optprs.add_option("--fitsdir", dest="fitsdir",
                      metavar="DIR",
                      help="Specify DIR to look for FITS files")
    optprs.add_option("-g", "--geometry", dest="geometry",
                      metavar="GEOM", default="1860x1100+57+0",
                      help="X geometry for initial size and placement")
    optprs.add_option("-i", "--inst", dest="instrument",
                      help="Specify instrument(s) to use for integgui")
    optprs.add_option("-m", "--monitor", dest="monitor", default='monitor',
                      metavar="NAME",
                      help="Subscribe to feeds from monitor service NAME")
    optprs.add_option("-n", "--name", dest="name", default='monwatch',
                      metavar="NAME",
                      help="Use NAME as our subscriber name")
    optprs.add_option("-p", "--path", dest="monpath", default='mon.sktask',
                      metavar="PATH",
                      help="Show values for PATH in monitor")
    optprs.add_option("--monport", dest="monport", type="int", default=10013,
                      help="Register monitor using PORT", metavar="PORT")
    optprs.add_option("--port", dest="port", type="int", default=12030,
                      help="Register using PORT", metavar="PORT")
    optprs.add_option("--profile", dest="profile", action="store_true",
                      default=False,
                      help="Run the profiler on main()")
    optprs.add_option("--svcname", dest="svcname", metavar="NAME",
                      default="integgui-notify",
                      help="Register using NAME as service name")
    optprs.add_option("--taskmgr", dest="taskmgr", metavar="NAME",
                      default='taskmgr0',
                      help="Connect to TaskManager with name NAME")
    ssdlog.addlogopts(optprs)

    (options, args) = optprs.parse_args(sys.argv[1:])

##     if len(args) != 0:
##         optprs.error("incorrect number of arguments")

    if options.display:
        os.environ['DISPLAY'] = options.display

    # Are we debugging this?
    if options.debug:
        import pdb

        pdb.run('main(options, args)')

    # Are we profiling this?
    elif options.profile:
        import profile

        print "%s profile:" % sys.argv[0]
        profile.run('main(options, args)')

    else:
        main(options, args)

#END

