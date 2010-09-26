# 
#[ Eric Jeschke (eric@naoj.org) --
#  Last edit: Sat Sep 25 14:37:58 HST 2010
#]

# remove once we're certified on python 2.6
from __future__ import with_statement

# Standard library imports
import sys, os, glob
import re
import thread, threading, Queue

# Special library imports
import pygtk
pygtk.require('2.0')
import gtk, gobject

# SSD/Gen2 imports
import Bunch
import Future

# Local integgui2 imports
import common
from pages import *
from dialogs import *


class IntegView(object):

    def __init__(self, logger, ev_quit, queues):

        self.logger = logger
        self.ev_quit = ev_quit
        self.queue = queues
        self.lock = threading.RLock()
        # Used for tagging commands
        self.cmdcount = 0

        self.gui_queue = Queue.Queue()
        self.placeholder = '--notdone--'
        self.gui_thread_id = None

        # Options that can be set graphically
        self.audible_errors = True
        self.suppress_confirm_exec = True

        # This is the home directory for loading all kinds of files
        self.procdir = os.path.join(os.environ['HOME'], 'Procedure')

        # Create the GUI
        self.w = Bunch.Bunch()

        # hack required to use threads with GTK
        gobject.threads_init()
        gtk.gdk.threads_init()

        # Create top-level window
        root = gtk.Window(gtk.WINDOW_TOPLEVEL)
        root.set_size_request(1900, 1050)
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
        self.framepage = self.ojws.addpage('frames', "Frames", FrameInfoPage)

        self.lws = self.ds.addws('ll', 'launchers', "Command Launchers")
        self.queuepage = self.lws.addpage('queues', "Queues", WorkspacePage)
        defqueue = self.queuepage.addpage('Default', "queue_default", QueuePage)
        defqueue.set_queue('default', self.queue.default)
        self.handsets = self.lws.addpage('handset', "Handset", WorkspacePage)

        self.oiws = self.ds.addws('ur', 'obsinfo', "Observation Info")
        self.obsinfo = self.oiws.addpage('obsinfo', "Obsinfo", ObsInfoPage)
        self.monpage = self.oiws.addpage('moninfo', "Monitor", SkMonitorPage)
        self.logpage = self.oiws.addpage('loginfo', "Logs", WorkspacePage)
        self.fitspage = self.oiws.addpage('fitsview', "Fits", WorkspacePage)
        self.history = self.oiws.addpage('history', "History", LogPage)
        self.oiws.select('obsinfo')

        self.exws = self.ds.addws('lr', 'executor', "Command Executers")
        self.gui_load_terminal()
        self.exws.addpage('Commands', "Commands", DDCommandPage)

        self.add_statusbar()

        self.w.root.show_all()

    def toggle_var(self, widget, key):
        if widget.active: 
            self.__dict__[key] = True
        else:
            self.__dict__[key] = False

    def set_procdir(self, path):
        self.procdir = path
        
    def add_menus(self):

        menubar = gtk.MenuBar()
        self.w.mframe.pack_start(menubar, expand=False)

        # create a File pulldown menu, and add it to the menu bar
        filemenu = gtk.Menu()
        file_item = gtk.MenuItem(label="File")
        menubar.append(file_item)
        file_item.show()
        file_item.set_submenu(filemenu)

        loadmenu = gtk.Menu()
        item = gtk.MenuItem(label="Load source")
        filemenu.append(item)
        item.show()
        item.set_submenu(loadmenu)

        item = gtk.MenuItem(label="ope")
        loadmenu.append(item)
        item.connect_object ("activate", lambda w: self.gui_load_ope(),
                             "file.Load ope")
        item.show()

        item = gtk.MenuItem(label="sk")
        loadmenu.append(item)
        item.connect_object ("activate", lambda w: self.gui_load_sk(),
                             "file.Load sk")
        item.show()

        item = gtk.MenuItem(label="task")
        loadmenu.append(item)
        item.connect_object ("activate", lambda w: self.gui_load_task(),
                             "file.Load task")
        item.show()

        item = gtk.MenuItem(label="launcher")
        loadmenu.append(item)
        item.connect_object ("activate", lambda w: self.gui_load_launcher_source(),
                             "file.Load launcher")
        item.show()

        item = gtk.MenuItem(label="handset")
        loadmenu.append(item)
        item.connect_object ("activate", lambda w: self.gui_load_handset_source(),
                             "file.Load handset")
        item.show()

        item = gtk.MenuItem(label="inf")
        loadmenu.append(item)
        item.connect_object ("activate", lambda w: self.gui_load_inf(),
                             "file.Load inf")
        item.show()

        loadmenu = gtk.Menu()
        item = gtk.MenuItem(label="Load")
        filemenu.append(item)
        item.show()
        item.set_submenu(loadmenu)

        # item = gtk.MenuItem(label="fits")
        # loadmenu.append(item)
        # item.connect_object ("activate", lambda w: self.gui_load_fits(),
        #                      "file.Load fits")
        # item.show()

        item = gtk.MenuItem(label="terminal")
        loadmenu.append(item)
        item.connect_object ("activate", lambda w: self.gui_load_terminal(),
                             "file.Load terminal")
        item.show()
        
        item = gtk.MenuItem(label="launcher")
        loadmenu.append(item)
        item.connect_object ("activate", lambda w: self.gui_load_launcher(),
                             "file.Load launcher")
        item.show()

        item = gtk.MenuItem(label="handset")
        loadmenu.append(item)
        item.connect_object ("activate", lambda w: self.gui_load_handset(),
                             "file.Load handset")
        item.show()

        item = gtk.MenuItem(label="commands")
        loadmenu.append(item)
        item.connect_object ("activate", lambda w: self.load_commands(),
                             "file.Load commands")
        item.show()

        item = gtk.MenuItem(label="log")
        loadmenu.append(item)
        item.connect_object ("activate", lambda w: self.gui_load_log(),
                             "file.Load log")
        item.show()
        
        item = gtk.MenuItem(label="monlog")
        loadmenu.append(item)
        item.connect_object ("activate", lambda w: self.gui_load_monlog(),
                             "file.Load mon log")
        item.show()
        
        item = gtk.MenuItem(label="Config from session")
        filemenu.append(item)
        item.connect_object ("activate", lambda w: self.reconfig(),
                             "file.Config from session")
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

        w = gtk.CheckMenuItem("Audible Errors")
        w.set_active(True)
        optionmenu.append(w)
        w.connect("activate", lambda w: self.toggle_var(w, 'audible_errors'))

        w = gtk.CheckMenuItem("Suppress 'Confirm Execute' popups")
        w.set_active(True)
        optionmenu.append(w)
        w.connect("activate", lambda w: self.toggle_var(w, 'suppress_confirm_exec'))

        # create a Queue pulldown menu, and add it to the menu bar
        queuemenu = gtk.Menu()
        item = gtk.MenuItem(label="Queue")
        menubar.append(item)
        item.show()
        item.set_submenu(queuemenu)

        item = gtk.MenuItem(label="Create queue ...")
        queuemenu.append(item)
        item.connect_object ("activate", lambda w: self.gui_create_queue(),
                             "queue.Create queue")
        item.show()


    def add_dialogs(self):
        self.filesel = FileSelection(action=gtk.FILE_CHOOSER_ACTION_OPEN)
        self.filesave = FileSelection(action=gtk.FILE_CHOOSER_ACTION_SAVE)


    def add_statusbar(self):
        hbox = gtk.HBox()
        btns = gtk.HButtonBox()

        btns.set_layout(gtk.BUTTONBOX_START)
        btns.set_spacing(5)

        self.btn_kill = gtk.Button("Kill")
        self.btn_kill.connect("clicked", lambda w: self.kill())
        self.btn_kill.modify_bg(gtk.STATE_NORMAL,
                                common.launcher_colors['killbtn'])

        btns.pack_end(self.btn_kill, fill=False, expand=False, padding=4)

        hbox.pack_end(btns, fill=False, expand=False, padding=4)
        
        self.w.status = gtk.Statusbar()
        self.status_cid = self.w.status.get_context_id("msg")
        self.status_mid = self.w.status.push(self.status_cid, "")

        hbox.pack_start(self.w.status, fill=True, expand=False,
                        padding=4)

        hbox.show_all()
        self.w.mframe.pack_end(hbox, expand=False, fill=True)


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


    def popup_confirm(self, title, qstr, f_res, *args, **kwdargs):
        w = gtk.MessageDialog(flags=gtk.DIALOG_DESTROY_WITH_PARENT,
                              type=gtk.MESSAGE_QUESTION,
                              buttons=gtk.BUTTONS_YES_NO,
                              message_format=qstr)
        w.set_title(title)

        def f(w, rsp):
            w.destroy()
            res = 'no'
            if rsp == gtk.RESPONSE_YES:
                res = 'yes'
            f_res(res, *args, **kwdargs)
            
        w.connect("response", f)
        w.show()

    def readfile(self, filepath):
        in_f = open(filepath, 'r')
        buf = in_f.read()
        in_f.close()

        return buf

    def popup_select(self, title, execfn, filedir):
        self.filesel.popup(title, execfn, initialdir=filedir)

    def popup_save(self, title, execfn, filedir, filename=None):
        self.filesave.popup(title, execfn, initialdir=filedir,
                            filename=filename)

    def gui_load_terminal(self):
        try:
            os.chdir(os.path.join(os.environ['HOME'], 'Procedure'))
            #os.chdir(os.environ['HOME'])

            name = 'Terminal'
            page = self.exws.addpage(name, name, TerminalPage)

            # Bring shell tab to front
            #self.exws.select(name)
        except Exception, e:
            self.popup_error("Cannot start terminal: %s" % (str(e)))

    def gui_load_monlog(self):

        def pick_log(w, rsp, cbox, names):
            logName = names[cbox.get_active()].strip()
            w.hide()
            if rsp == gtk.RESPONSE_OK:
                self.load_monlog(logName)
            return True
            
        dialog = gtk.MessageDialog(flags=gtk.DIALOG_DESTROY_WITH_PARENT,
                                   type=gtk.MESSAGE_QUESTION,
                                   buttons=gtk.BUTTONS_OK_CANCEL,
                                   message_format="Select a log to view")
        dialog.set_title("Choose Log")
        # Add a combo box to the content area containing the names of the
        # logs
        vbox = dialog.get_content_area()
        cbox = gtk.combo_box_new_text()
        index = 0
        names = list(common.controller.valid_monlogs)
        names.sort()
        for name in names:
            cbox.insert_text(index, name)
            index += 1
        cbox.set_active(0)
        vbox.add(cbox)
        cbox.show()
        dialog.connect("response", pick_log, cbox, names)
        dialog.show()
        return True

    def load_monlog(self, logname):
        try:
            try:
                page = self.logpage.getPage(logname)
                raise Exception("There is already a log open by that name!")
            except KeyError:
                pass
            page = self.logpage.addpage(logname, logname, MonLogPage)

            # Add standard error regex matching
            page.add_regexes(common.error_regexes)
            
            # Bring log tab to front
            self.oiws.select('loginfo')
        except Exception, e:
            self.popup_error("Cannot load log '%s': %s" % (
                    logname, str(e)))


    def gui_load_log(self):
        initialdir = os.path.abspath(os.environ['LOGHOME'])
        
        self.filesel.popup("Follow log", self.load_log,
                           initialdir=initialdir)

    def load_log(self, filepath):
        try:
            dirname, filename = os.path.split(filepath)
            # Drop ".log" from tab names
            filepfx, filesfx = os.path.splitext(filename)
            if filesfx.lower() == '.log':
                filename = filepfx

            name = filename
            page = self.logpage.addpage(name, name, LogPage)

            # Add standard error regex matching
            page.add_regexes(common.error_regexes)
            
            page.load(filepath)

            # Bring log tab to front
            self.oiws.select('loginfo')
        except Exception, e:
            self.popup_error("Cannot load '%s': %s" % (
                    filepath, str(e)))


    def gui_load_ope(self):
        #initialdir = os.path.join(os.environ['HOME'], 'Procedure')
        initialdir = self.procdir
        self.filesel.popup("Load OPE file",
                           lambda filepath: self.load_generic(filepath,
                                                              # ???!!!
                                                              OpePage.OpePage),
                           initialdir=initialdir)

    def gui_load_sk(self):
        initialdir = os.path.join(os.environ['PYHOME'], 'SOSS',
                                  'SkPara', 'sk')
        
        self.filesel.popup("Load skeleton file",
                           lambda filepath: self.load_generic(filepath,
                                                              SkPage),
                           initialdir=initialdir)

    def gui_load_task(self):
        initialdir = os.path.join(os.environ['GEN2HOME'], 'Tasks')
        
        self.filesel.popup("Load python task",
                           lambda filepath: self.load_generic(filepath,
                                                              TaskPage),
                           initialdir=initialdir)

    def gui_load_inf(self):
        initialdir = os.path.join(os.environ['HOME'], 'Procedure',
                                  'COMICS')
        
        self.filesel.popup("Load inf file",
                           lambda filepath: self.load_generic(filepath,
                                                              InfPage),
                           initialdir=initialdir)

    def gui_load_launcher_source(self):
        initialdir = os.path.join(os.environ['GEN2HOME'], 'integgui2',
                                  'Launchers')
        
        self.filesel.popup("Load launcher source",
                           lambda filepath: self.load_generic(filepath,
                                                              # ???!!!
                                                              CodePage.CodePage),
                           initialdir=initialdir)

    def gui_load_handset_source(self):
        initialdir = os.path.join(os.environ['GEN2HOME'], 'integgui2',
                                  'Handsets')
        
        self.filesel.popup("Load handset source",
                           lambda filepath: self.load_generic(filepath,
                                                              # ???!!!
                                                              CodePage.CodePage),
                           initialdir=initialdir)


    def open_generic(self, buf, filepath, pageKlass):
        try:
            dirname, filename = os.path.split(filepath)
            #print pageKlass

            name = filename
            page = self.exws.addpage(name, name, pageKlass)
            page.load(filepath, buf)

        except Exception, e:
            self.popup_error("Cannot load '%s': %s" % (
                    filepath, str(e)))


    def kill(self):
        controller = common.controller
        controller.tm_restart()
        # TODO!
        #self.global_reset_pause()

    def load_ope(self, filepath):
        return self.load_generic(filepath, OpePage.OpePage)

    def load_generic(self, filepath, pageKlass):
        try:
            buf = self.readfile(filepath)

            return self.open_generic(buf, filepath, pageKlass)

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

            match = re.match(r'^(.+)\.yml$', filename)
            if not match:
                return

            name = match.group(1).replace('_', ' ')
            page = self.lws.addpage(name, name, LauncherPage,
                                    adjname=False)
            page.load(buf)

        except Exception, e:
            self.popup_error("Cannot load '%s': %s" % (
                    filepath, str(e)))


    def gui_load_handset(self):
        initialdir = os.path.join(os.environ['GEN2HOME'], 'integgui2',
                                  'Handsets')
        
        self.filesel.popup("Load handset", self.load_handset,
                           initialdir=initialdir)


    def load_handset(self, filepath):
        try:
            buf = self.readfile(filepath)

            dirname, filename = os.path.split(filepath)

            match = re.match(r'^(.+)\.yml$', filename)
            if not match:
                return

            name = match.group(1).replace('_', ' ')
            page = self.handsets.addpage(name, name, HandsetPage,
                                         adjname=False)
            page.load(buf)

        except Exception, e:
            self.popup_error("Cannot load '%s': %s" % (
                    filepath, str(e)))


    def load_commands(self):
        try:
            page = self.exws.addpage('Commands', 'Commands', DDCommandPage)

        except Exception, e:
            self.popup_error("Cannot load command page: %s" % (
                    str(e)))


    def load_history(self):
        try:
            self.history = self.oiws.addpage('history', "History", LogPage)

        except Exception, e:
            self.popup_error("Cannot load history page: %s" % (
                    str(e)))
        
    def get_launcher_paths(self, insname):
        filename = '%s*.yml' % insname.upper()
        pathmatch = os.path.join(os.environ['GEN2HOME'], 'integgui2',
                                 'Launchers', filename)

        res = glob.glob(pathmatch)
        return res
        
    def close_launchers(self):
        for name in self.lws.getNames():
            page = self.lws.getPage(name)
            if isinstance(page, LauncherPage):
                page.close()

    def close_handsets(self):
        for name in self.handsets.getNames():
            page = self.handsets.getPage(name)
            if isinstance(page, HandsetPage):
                page.close()

    def reconfig(self):
        self.close_logs()
        self.close_handsets()
        self.close_launchers()

        try:
            common.controller.ctl_do(common.controller.config_from_session,
                                     'main')
        except Exception, e:
            self.gui.popup_error("Failed to initialize from session: %s" % (
                str(e)))

    def raise_queue(self):
        self.lws.select('queues')
        
    def raise_handset(self):
        self.lws.select('handset')
        
    def get_handset_paths(self, insname):
        filename = '%s*.yml' % insname.upper()
        pathmatch = os.path.join(os.environ['GEN2HOME'], 'integgui2',
                                 'Handsets', filename)

        res = glob.glob(pathmatch)
        return res
        
    def get_log_path(self, insname):
        filename = '%s.log' % insname
        filepath = os.path.join(os.environ['LOGHOME'], filename)
        return filepath

    def close_logs(self):
        for name in self.logpage.getNames():
            page = self.logpage.getPage(name)
            page.close()

    def gui_load_fits(self):
        initialdir = os.environ['DATAHOME']
        
        self.filesel.popup("Load FITS file", self.load_fits,
                           initialdir=initialdir)
        
    def load_fits(self, filepath):
            
        (filedir, filename) = os.path.split(filepath)
        (filepfx, fileext) = os.path.splitext(filename)
        try:
            page = self.fitspage.addpage(filepath, filepfx, FitsViewerPage)
            page.load(filepath)

            # Bring FITS tab to front
            self.oiws.select('fitsview')
        except Exception, e:
            self.popup_error("Cannot load '%s': %s" % (
                    filepath, str(e)))

    def gui_create_queue(self):
        dialog = gtk.MessageDialog(flags=gtk.DIALOG_DESTROY_WITH_PARENT,
                                   type=gtk.MESSAGE_QUESTION,
                                   message_format="Please enter a name for the new queue:")
        dialog.set_title("Create Queue")
        dialog.add_buttons("Ok", 1, "Cancel", 0)
        vbox = dialog.get_content_area()
        ent = gtk.Entry()
        vbox.add(ent)
        ent.show()
        dialog.connect("response", self.create_queue_res, ent)
        dialog.show()

    def create_queue_res(self, w, rsp, went):
        queueName = went.get_text().strip().lower()
        w.destroy()
        if rsp == 1:
            if self.queue.has_key(queueName):
                self.popup_error("A queue with that name already exists!")
                return True
            queue = common.controller.addQueue(queueName, self.logger)
            page = self.queuepage.addpage(queueName, queueName.capitalize(),
                                         QueuePage)
            page.set_queue(queueName, queue)
        return True
        
    def edit_command(self, cmdstr):
        try:
            page = self.exws.getPage('Commands')
            page.set_text(cmdstr)

            # Bring Commands tab to front
            self.exws.select('Commands')
        except Exception, e:
            self.popup_error("Cannot edit command: %s" % (
                    str(e)))

    def delete_event(self, widget, event, data=None):
        self.ev_quit.set()
        gtk.main_quit()
        return False

    # callback to quit the program
    def quit(self, widget):
        self.ev_quit.set()
        gtk.main_quit()
        return False

    def reset(self):
        # Perform a global reset across all command-type pages
        for ws in self.ds.getWorkspaces():
            for page in ws.getPages():
                if (isinstance(page, OpePage) or 
                    isinstance(page, LauncherPage) or
                    isinstance(page, DDCommandPage)):
                    page.reset()

    ############################################################
    # Interface from controller into the view
    #
    # Due to poor thread-handling in gtk, we are forced to spawn
    # these calls off to the GUI thread using gui_do()
    ############################################################

    def update_frame(self, frameinfo):
        if hasattr(self, 'framepage'):
            self.gui_do(self.framepage.update_frame, frameinfo)

    def update_frames(self, framelist):
        if hasattr(self, 'framepage'):
            self.gui_do(self.framepage.update_frames, framelist)

    def update_obsinfo(self, infodict):
        self.logger.info("OBSINFO=%s" % str(infodict))
        if hasattr(self, 'obsinfo'):
            self.gui_do(self.obsinfo.update_obsinfo, infodict)
   
    def update_history(self, data):
        if hasattr(self, 'history'):
            self.gui_do(self.history.push, data)
   
    def update_loginfo(self, logname, infodict):
        if hasattr(self, 'logpage'):
            try:
                page = self.logpage.getPage(logname)
                #print "%s --> %s" % (logname, str(infodict)) 
                self.gui_do(page.add2log, infodict)
            except KeyError:
                # No log page for this log loaded, so silently drop message
                # TODO: drop into the integgui2 log page?
                pass
   
    def process_ast(self, ast_id, vals):
        if hasattr(self, 'monpage'):
            self.gui_do(self.monpage.process_ast_err, ast_id, vals)

    def process_task(self, path, vals):
        if hasattr(self, 'monpage'):
            self.gui_do(self.monpage.process_task_err, path, vals)

    def gui_do(self, method, *args, **kwdargs):
        """General method for calling into the GUI.
        """
        #gobject.idle_add(method, *args, **kwdargs)
        self.gui_queue.put((method, args, kwdargs))
   
    def gui_do_res(self, method, *args, **kwdargs):
        """General method for calling into the GUI.
        """
        # Note: I suppose there may be a valid reason for the GUI thread
        # to create one of these, but better safe than sorry...
        self.assert_nongui_thread()
        
        future = Future.Future()
        self.gui_queue.put((future, method, args, kwdargs))
        return future

    def assert_gui_thread(self):
        my_id = thread.get_ident() 
        assert my_id == self.gui_thread_id, \
               Exception("Non-GUI thread (%d) is executing GUI code!" % (
            my_id))
        
    def assert_nongui_thread(self):
        my_id = thread.get_ident() 
        assert my_id != self.gui_thread_id, \
               Exception("GUI thread (%d) is executing non-GUI code!" % (
            my_id))
        
    def mainloop(self):
        # Mark our thread id
        self.gui_thread_id = thread.get_ident()

        while not self.ev_quit.isSet():
            # Process "in-band" GTK events
            try:
                tup = self.gui_queue.get(block=True, timeout=0.01)
                if len(tup) == 4:
                    (future, method, args, kwdargs) = tup
                elif len(tup) == 3:
                    (method, args, kwdargs) = tup
                    future = None
                else:
                    raise Exception("Don't understand contents of queue: %s" % (
                        str(tup)))

                # Execute the GUI method
                gtk.gdk.threads_enter()
                try:
                    try:
                        res = method(*args, **kwdargs)
                    except Exception, e:
                        res = e

                finally:
                    gtk.gdk.threads_leave()

                # Store results to future if this was a call to gui_do_res()
                if future:
                    future.resolve(res)
                    
            except Queue.Empty:
                pass
                
            except Exception, e:
                self.logger.error("Main GUI loop error: %s" % str(e))
                #pass
                
            # Process "out-of-band" GTK events
            gtk.gdk.threads_enter()
            try:
                while gtk.events_pending():
                    gtk.main_iteration()
            finally:
                gtk.gdk.threads_leave()

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
#GtkLabel::width-chars = 20
}

# In this example, we inherit the attributes of the "button" style and then
# override the font and background color when prelit to create a new
# "main_button" style.

style "main_button" = "button"
{
  font = "-adobe-helvetica-medium-r-normal--*-100-*-*-*-*-*-*"
  bg[PRELIGHT] = { 0.75, 0, 0 }
}

style "launcher_button" = "button"
{
  font_name = "Monospace 10"
}

style "menubar-style"
{
GtkMenuBar::shadow_type = none
}

style "statusbar-style"
{
GtkStatusbar::shadow_type = none
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
##  gtk-key-theme-name = "Emacs" 
}

# These set the widget types to use the styles defined above.
# The widget types are listed in the class hierarchy, but could probably be
# just listed in this document for the users reference.

widget_class "*GtkMenuBar" style "menubar-style"
widget_class "*GtkStatusbar" style "statusbar-style"
widget_class "GtkWindow" style "window"
widget_class "GtkDialog" style "window"
widget_class "GtkFileSelection" style "window"
## widget_class "*GtkToggleButton*" style "toggle_button"
## widget_class "*GtkCheckButton*" style "toggle_button"
## widget_class "*GtkRadioButton*" style "toggle_button"
widget_class "launcher.GtkButton*" style "launcher_button"
widget_class "*GtkButton*" style "button"
widget_class "*GtkTextView" style "text"

# This sets all the buttons that are children of the "main window" to
# the main_button style.  These must be documented to be taken advantage of.
widget "main window.*GtkButton*" style "main_button"
"""
gtk.rc_parse_string(rc) 

#END
