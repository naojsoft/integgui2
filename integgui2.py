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

color_blue = '#cae1ff'     # pale blue
color_green = '#c1ffc1'     # pale green
color_yellow = '#fafad2'     # cream
color_white = 'whitesmoke'

color_bg = 'light grey'

# Define sounds used in IntegGUI
sound = Bunch.Bunch(success='doorbell.au',
                    failure='splat.au')

# These are the status variables pulled from the status system. "%s" is
# replaced by the 3-letter instrument mnemonic of the currently allocated
# primary instrument in IntegGUI.
#
statvars_t = [(1, 'STATOBS.%s.OBSINFO1'), (2, 'STATOBS.%s.OBSINFO2'),
              (3, 'STATOBS.%s.OBSINFO3'), (4, 'STATOBS.%s.OBSINFO4'),
              (5, 'STATOBS.%s.OBSINFO5'), # 6 is error log string
              (7, 'STATOBS.%s.TIMER_SEC'), (8, 'FITS.%s.PROP-ID'),
              ]


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


class IntegGUI(object):
    def __init__(self, parent, logger, ev_quit, **kwdargs):

        self.logger = logger
        self.ev_quit = ev_quit
        self.__dict__.update(kwdargs)
        self.lock = threading.RLock()

        self.track = {}
        self.pages = {}
        self.pagelist = []
        self.pagelimit = 10
        # Holds executor pages
        self.opepages = {}

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

        self.add_panels()
        self.add_menus()
        self.add_dialogs()
        self.closelog(self.w.log)
        
        self.w.status = StatusBar(self.w.root, text="", 
                                  relief='flat', anchor='w')
        self.w.status.pack(side='bottom', fill='x')

        # Used for tagging commands
        self.cmdcount = 0

        # command queues
        self.queue = Bunch.Bunch(executer=[], launcher=[])
        self.executing = threading.Event()


    def set_controller(self, controller):
        self.controller = controller

    def add_menus(self):
        menubar = Tkinter.Menu(self.w.root, relief='flat')

        # create a pulldown menu, and add it to the menu bar
        filemenu = Tkinter.Menu(menubar, tearoff=0)
        filemenu.add('command', label="Load ope", command=self.gui_load_ope)
        filemenu.add('command', label="Load sk", command=self.gui_load_sk)
        filemenu.add('command', label="Load task", command=self.gui_load_task)
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

    def statusMsg(self, format, *args):
        if not format:
            self.w.status.clear()
        else:
            self.w.status.set(format, *args)

    def add_panels(self):
        # LFrame
        #   JFrame (Observation Journal)
        #   LFrame (Command Launcher)
        # RFrame
        #   TFrame
        #     IFrame (Information)
        #   BFrame
        #     Executor
        #
        self.w.mframe = Tkinter.Frame(self.w.root, padx=2, pady=2)
        
        paned = Pmw.PanedWidget(self.w.mframe, orient='horizontal',
                                handlesize=16) 
        self.w.hframe = paned
        paned.pack(fill='both', expand=True)

        paned.add('lframe', size=0.35)
        paned.add('rframe', size=0.65)
        self.w.lframe = paned.pane('lframe')
        self.w.rframe = paned.pane('rframe')

        lpane = Pmw.PanedWidget(self.w.lframe, orient='vertical',
                                handlesize=16)
        self.w.lpane = lpane
        lpane.add('journal')
        lpane.add('launchers')
        lpane.pack(fill='both', expand=True)
        rpane = Pmw.PanedWidget(self.w.rframe, orient='vertical',
                                handlesize=16)
        self.w.rpane = rpane
        rpane.add('info')
        rpane.add('executor')
        rpane.pack(fill='both', expand=True)

        self.w.obsjnl = self.w.lpane.pane('journal')
        self.w.cmdlnch = self.w.lpane.pane('launchers')
        self.w.exectr = self.w.rpane.pane('executor')
        self.w.info = self.w.rpane.pane('info')

##         self.w.obsjnl = Tkinter.Frame(self.w.mframe)
##         self.w.info = Tkinter.Frame(self.w.mframe)
##         self.w.cmdlnch = Tkinter.Frame(self.w.mframe)
##         self.w.exectr = Tkinter.Frame(self.w.mframe)

##         self.w.obsjnl.grid(row=0, column=0, sticky='wens', padx=2, pady=2)
##         self.w.info.grid(row=0, column=1, sticky='wens', padx=2, pady=2)
##         self.w.cmdlnch.grid(row=1, column=0, sticky='wens', padx=2, pady=2)
##         self.w.exectr.grid(row=1, column=1, sticky='wens', padx=2, pady=2)

        self.w.root.columnconfigure(0, weight=10)
        self.w.root.rowconfigure(0, weight=10)

        self.w.mframe.grid(column=0, row=0, sticky='wens')
##         self.w.mframe.rowconfigure(0, weight=1)
##         self.w.mframe.rowconfigure(1, weight=3)
##         self.w.mframe.columnconfigure(0, weight=1)
##         self.w.mframe.columnconfigure(1, weight=3)
        
        # Obs Journal
        self.w.jrnnb = Pmw.NoteBook(self.w.obsjnl, tabpos='n')
        self.w.jrnnb.pack(padx=2, pady=2, fill='both', expand=1)

        self.add_frame_journal(self.w.jrnnb)

        # Command Launchers
        self.w.lnchnb = Pmw.NoteBook(self.w.cmdlnch, tabpos='n')
        self.w.lnchnb.pack(padx=2, pady=2, fill='both', expand=1)

        # Information Display
        self.w.infonb = Pmw.NoteBook(self.w.info, tabpos='n')
        self.w.infonb.pack(padx=2, pady=2, fill='both', expand=1)
        
        self.add_obsinfo(self.w.infonb)

        # Command Executor
        self.w.execnb = Pmw.NoteBook(self.w.exectr, tabpos='n')
        self.w.execnb.pack(padx=2, pady=2, fill='both', expand=True)

        self.add_command_executor(self.w.execnb)

        self.w.mframe.pack(fill='both', expand=True)
        
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


    def add_command_executor(self, parent):

        # Add commands tab
        page = parent.add('commands', tab_text='Commands')
        pagefr = parent.page('commands')

        txt = Pmw.ScrolledText(pagefr, text_wrap='none',
                               labelpos='n', label_text='Command Execution',
                               vscrollmode='dynamic', hscrollmode='dynamic')
        # ???
        self.w.commands = txt

        tw = txt.component('text')
        tw.configure(padx=5, pady=5, highlightthickness=0)
        txt.pack(side=Tkinter.TOP, fill='both', expand=True, padx=4, pady=4)


    def add_ope_executor(self, parent, title):
        try:
            opepage = self.opepages[title]
            self.popup_error("A page with that name already exists!")
            return None
        except KeyError:
            opepage = Bunch.Bunch(name=title, title=title)
            self.opepages[title] = opepage

        # Add OPE File tab
        page = parent.add(title, tab_text=title)
        page.focus_set()
        pagefr = parent.page(title)

        txt = Pmw.ScrolledText(pagefr, text_wrap='none',
                               rowheader=True,
                               rowheader_width=1,
                               rowheader_padx=2, rowheader_pady=5,
                               labelpos='n', label_text=title,
                               vscrollmode='dynamic', hscrollmode='dynamic',
                               Header_foreground = 'blue')

        tw = txt.component('text')
        tw.configure(padx=5, pady=5, highlightthickness=0)
        rw = txt.component('rowheader')
        rw.configure(highlightthickness=0)
        txt.pack(side=Tkinter.TOP, fill='both', expand=True, padx=4, pady=4)

        opepage.txt = txt
        opepage.tw = tw
        opepage.rw = rw
        opepage.queue = 'executer'
        opepage.modified = True
        opepage.parent = parent

        # bottom buttons
        btns = Tkinter.Frame(pagefr) 

        opepage.execute = Tkinter.Button(btns, text="Exec",
                                     width=10,
                                     activebackground="#089D20",
                                     activeforeground="#FFFF00",
                                     command=lambda: self.execute(opepage))
        opepage.execute.pack(padx=5, pady=4, side=Tkinter.LEFT)

        opepage.pause = Tkinter.Button(btns, text="Pause",
                                     width=10,
                                     command=lambda: self.pause(opepage),
                                     activebackground="#089D20",
                                     activeforeground="#FFFF00")
        opepage.pause.pack(padx=5, pady=4, side=Tkinter.LEFT)

        opepage.cancel = Tkinter.Button(btns, text="Cancel",
                                     width=10,
                                     command=lambda: self.cancel(opepage),
                                     activebackground="#089D20",
                                     activeforeground="#FFFF00")
        opepage.cancel.pack(padx=5, pady=4, side=Tkinter.LEFT)

        opepage.kill = Tkinter.Button(btns, text="Restart TM",
                                     width=10,
                                     command=self.kill,
                                     activebackground="#089D20",
                                     activeforeground="#FFFF00")
        opepage.kill.pack(padx=5, pady=4, side=Tkinter.LEFT)

        opepage.save = Tkinter.Button(btns, text="Save",
                                     width=10,
                                     command=lambda: self.save_ope(opepage),
                                     activebackground="#089D20",
                                     activeforeground="#FFFF00")
        opepage.save.pack(padx=5, pady=4, side=Tkinter.LEFT)

        opepage.reload = Tkinter.Button(btns, text="Reload",
                                     width=10,
                                     command=lambda: self.reload_ope(opepage),
                                     activebackground="#089D20",
                                     activeforeground="#FFFF00")
        opepage.reload.pack(padx=5, pady=4, side=Tkinter.LEFT)

        opepage.close = Tkinter.Button(btns, text="Close",
                                     width=10,
                                     command=lambda: self.close(opepage),
                                     activebackground="#089D20",
                                     activeforeground="#FFFF00")
        opepage.close.pack(padx=5, pady=4, side=Tkinter.LEFT)

##         btns.grid(row=1, column=0, sticky='we')
##         pagefr.rowconfigure(0, weight=1)
##         pagefr.columnconfigure(0, weight=10)
##         pagefr.rowconfigure(1, weight=0)
##         pagefr.columnconfigure(1, weight=10)
        btns.pack(padx=2, pady=2, side=Tkinter.BOTTOM, fill='x',
                  expand=False)

        #self.w.execnb.setnaturalsize()
        parent.selectpage(title)
        return opepage


    def add_launcher(self, parent):
        pass

    def add_obsinfo(self, parent):
        page = parent.add('obsinfo', tab_text='Info')
        page.focus_set()
        pagefr = parent.page('obsinfo')

        txt = Pmw.ScrolledText(pagefr, text_wrap='none',
                               #labelpos='n', label_text='FITS Data Frames',
                               vscrollmode='dynamic', hscrollmode='dynamic')
        self.w.obstext = txt

        tw = txt.component('text')
        tw.configure(padx=5, pady=3, highlightthickness=0)

        tw.insert('0.1', '\n' * 10)

        txt.pack(fill='both', expand=True, padx=4, pady=4)

    def add_frame_journal(self, parent):
        
        page = parent.add('frames', tab_text='Frames')
        page.focus_set()
        pagefr = parent.page('frames')

        txt = Pmw.ScrolledText(pagefr, text_wrap='none',
                               columnheader=True,
                               columnheader_width=1,
                               columnheader_padx=5, columnheader_pady=3,
                               labelpos='n', label_text='FITS Data Frames',
                               vscrollmode='dynamic', hscrollmode='dynamic')
        # ???
        self.w.jnltext = txt

        tw = txt.component('text')
        tw.configure(padx=5, pady=3, highlightthickness=0)

        cw = txt.component('columnheader')
        cw.configure(highlightthickness=0)

        txt.pack(fill='both', expand=True, padx=4, pady=4)

        
    def setPos(self, geom):
        self.w.root.geometry(geom)

    def closelog(self, w):
        # close log window
        self.w.log.withdraw()
        
    def showlog(self):
        # open log window
         self.w.log.show()

    def logupdate(self):
        try:
            while True:
                msgstr = self.logqueue.get(block=False)

                self.w.log.insert('end', msgstr + '\n')

        except Queue.Empty:
            self.w.root.after(200, self.logupdate)
    
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

    def _load_ope(self, opepage, buf):

        # get text widget
        tw = opepage.tw

        # insert text
        tags = ['code']
        try:
            tw.delete('1.0', 'end')
        except:
            pass
        tw.insert('end', buf, tuple(tags))

        lines = buf.split('\n')
        header = '\n' * len(lines)
        hw = opepage.txt.component('rowheader')
        hw.delete('1.0', 'end')
        hw.insert('end', header)

        tw.tag_configure('code', foreground="black")
        tw.tag_raise('code')

    def gui_load_ope(self):
        initialdir = os.path.join(os.environ['HOME'], 'Procedure')
        
        filepath = tkFileDialog.askopenfilename(title="Load OPE file",
                                                initialdir=initialdir,
                                                parent=self.w.root)
        if not filepath:
            return

        self.load_ope(filepath)
                               
    def gui_load_sk(self):
        initialdir = os.path.join(os.environ['PYHOME'], 'SOSS',
                                  'SkPara', 'sk')
        
        filepath = tkFileDialog.askopenfilename(title="Load sk file",
                                                initialdir=initialdir,
                                                parent=self.w.root)
        if not filepath:
            return

        self.load_ope(filepath)
                               
    def gui_load_task(self):
        initialdir = os.path.join(os.environ['GEN2HOME'], 'Tasks')
        
        filepath = tkFileDialog.askopenfilename(title="Load task file",
                                                initialdir=initialdir,
                                                parent=self.w.root)
        if not filepath:
            return

        self.load_ope(filepath)
                               
    def load_ope(self, filepath):

        opedir, opefile = os.path.split(filepath)
        try:
            in_f = open(filepath, 'r')
            buf = in_f.read()
            in_f.close()
        except IOError, e:
            return self.popup_error("Cannot load '%s': %s" % (
                    filepath, str(e)))

        opepage = self.add_ope_executor(self.w.execnb, opefile)
        if opepage != None:
            opepage.filepath = filepath
            self._load_ope(opepage, buf)
        
    def reload_ope(self, opepage):
        try:
            in_f = open(opepage.filepath, 'r')
            buf = in_f.read()
            in_f.close()
        except IOError, e:
            return self.popup_error("Cannot reload '%s': %s" % (
                    opepage.filepath, str(e)))

        self._load_ope(opepage, buf)

    def save_ope(self, opepage):
        # TODO: make backup?

        opedir, opefile = os.path.split(opepage.filepath)

        res = tkMessageBox.askokcancel("Save file", 
                                       'Really save "%s"?' % opefile)
        if not res:
            return

        # get text widget
        tw = opepage.tw
        buf = tw.get('1.0', 'end')

        try:
            out_f = open(opepage.filepath, 'w')
            out_f.write(buf)
            out_f.close()
            self.statusMsg("%s saved." % opepage.filepath)
        except IOError, e:
            return self.popup_error("Cannot write '%s': %s" % (
                    opepage.filepath, str(e)))


    def astIdtoTitle(self, ast_id):
        page = self.pages[ast_id]
        return page.title
        
    def delpage(self, ast_id):
        #title = self.astIdtoTitle(ast_id)
        self.w.infonb.delete(ast_id)
        del self.pages[ast_id]

    def addpage(self, ast_id, title, text):
        with self.lock:

            # Make room for new pages
            while len(self.pagelist) >= self.pagelimit:
                oldast_id = self.pagelist.pop(0)
                self.delpage(oldast_id)
                
            page = self.w.infonb.add(ast_id, tab_text=title)
            #page.focus_set()

            txt = Pmw.ScrolledText(page, text_wrap='none',
                                   vscrollmode='dynamic', hscrollmode='dynamic')

            tw = txt.component('text')
            tw.configure(
                         borderwidth=2, padx=10, pady=5)

            self.insert_ast(tw, text)
            txt.pack(fill='both', expand=True, padx=4, pady=4)

            self.w.infonb.setnaturalsize()

            try:
                page = self.pages[ast_id]
                page.tw = tw
                page.title = title
            except KeyError:
                self.pages[ast_id] = Bunch.Bunch(tw=tw, title=title)

            self.pagelist.append(ast_id)
            #self.w.infonb.selectpage(ast_id)

        
    def parsefile(self, filepath):
        bnch = self.parser.parse_skfile(filepath)
        if bnch.errors == 0:
            (path, filename) = os.path.split(filepath)

            text = self.issue.issue(bnch.ast, [])
            print text
            #print dir(txt)
            self.addpage(filename, filename, text)
            
        
    def popup_error(self, errstr):
        tkMessageBox.showerror("IntegGUI Error", errstr)

    

    def update_frame(self, frameinfo):
        self.logger.debug("UPDATE FRAME: %s" % str(frameinfo))
        tw = self.w.jnltext.component('text')

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

        tw = self.w.jnltext.component('text')
        tw.delete('1.0', 'end')
        
        # Create header
        cw = self.w.jnltext.component('columnheader')
        cw.insert('1.0', fits.header)

        for frameinfo in framelist:
            self.update_frame(frameinfo)

    def update_obsinfo(self, obsdict):

        self.logger.debug("obsinfo update: %s" % str(obsdict))
        tw = self.w.obstext.component('text')

        if obsdict.has_key('PROP-ID'):
            update_line(tw, 1, 'Prop-Id: %s' % obsdict['PROP-ID'])
        if obsdict.has_key('TIMER_SEC'):
            self.set_timer(obsdict['TIMER_SEC'])
        
        offset = 2
        for i in xrange(1, 6):
            try:
                val = str(obsdict['OBSINFO%d' % i])
                update_line(tw, i+offset, val)
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
        self.timer_interval(self.w.root)

    def timer_interval(self, w):
        self.logger.debug("timer: %d sec" % self.timer_val)
        self.timer_val -= 1
        tw = self.w.obstext.component('text')
        update_line(tw, 2, 'Timer: %s' % str(self.timer_val))
        if self.timer_val > 0:
            self.w.root.after(1000, self.timer_interval, [])
        else:
            # Do something when timer expires?
            pass
        
    def quit(self):
        # TODO: check for unsaved buffers
        self.ev_quit.set()
        sys.exit(0)


    def close(self, opepage):
        if opepage.modified:
            res = tkMessageBox.askokcancel("Close Tab",
                                           'Really close tab "%s"?' % (
                    opepage.title))
            if not res:
                return

        opepage.parent.delete(opepage.name)

    def kill(self):
        self.controller.tm_restart()

    def cancel(self, opepage):
        self.controller.tm_cancel(opepage.queue)

    def pause(self, opepage):
        self.controller.tm_pause(opepage.queue)


    def execute(self, opepage):
        """Callback when the EXEC button is pressed.
        """
        # Check whether we are busy executing a command here
        # and popup an error message if so
        if self.executing.isSet():
            self.popup_error("Commands are executing!")
            return

        tw = opepage.tw
        self.clear_marks(opepage)

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
            self.logger.debug("Queue 'executer': %s" % (self.queue.executer))

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

    def mark_exec(self, bnch, char):

        # Get the entire OPE buffer
        tw = bnch.opepage.tw
        row, col = str(tw.index('end')).split('.')
        len = int(row)
        index = tw.index('%s.first' % bnch.tag)

        rw = bnch.opepage.rw
        rw.delete('1.0', 'end')
        rw.insert('1.0', '\n' * len)

        rw.insert(index, char)


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
        self.mark_exec(bnch, 'X')
        
        return bnch, cmdstr


    def feedback_noerror(self, queueName, bnch, res):

        self.mark_exec(bnch, 'D')
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

        if bnch:
            self.mark_exec(bnch, 'E')

        #self.make_sound(cmd_err)
        self.executing.clear()
       
        #self.w.root.after(100, self.popup_error, [str(e)])
        self.statusMsg(str(e))

        # Peeeeeww!
        self.playSound(sound.failure)

        
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

        if not self.show_times.get():
            return

        if vals.has_key('time_added'):
            length = vals['time_added']
            page.tw.delete('%s.first' % ast_num, '%s.first+%dc' % (ast_num, length))
            
        vals['time_added'] = len(time_s)
        page.tw.insert('%s.first' % ast_num, time_s, (ast_num,))
        

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
            self.audible_warn(cmd_str, vals)

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
                if self.save_decode_result.get():
                    self.addpage(ast_id + '.decode', title, ast_str)

                self.addpage(ast_id, title, ast_str)

            elif vals.has_key('ast_track'):
                path = vals['ast_track']

                curvals = self.controller.getvals(path)
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
            

def main(options, args):
    
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

    gui.set_controller(controller)
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
    channels = [options.taskmgr, 'g2task']
    # Task info
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
    notify_obj = fits.IntegGUINotify(gui, options.fitsdir)
    notify_obj.update_framelist()
    
    svc = ro.remoteObjectServer(svcname=options.svcname,
                                obj=notify_obj, logger=logger,
                                port=options.port,
                                ev_quit=ev_quit,
                                usethread=True)
    
    # Load any files specified on the command line
    for opefile in args:
        gui.load_ope(opefile)

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

