#
# E. Jeschke
#

# Standard library imports
import os
import glob
import re
import time
import threading
import queue as Queue

from ginga.gw import Widgets, GwMain, Desktop as GwDesktop

# SSD/Gen2 imports
from ginga.misc import Bunch

# Local integgui2 imports
from . import common
# Page modules used as ``Module.Class`` (formerly via ``from .pages import *``)
from . import OpePage, CodePage, WorkspacePage
# Page classes used by name
from .Desktop import Desktop
from .TagPage import TagPage
from .SkPage import SkPage
from .TaskPage import TaskPage
from .DirectoryPage import DirectoryPage
from .QueuePage import QueuePage
from .InfPage import InfPage
from .EphemPage import EphemPage
from .TSCTrackPage import TSCTrackPage
from .CopyTSCTrackPage import CopyTSCTrackPage
from .HandsetPage import HandsetPage
from .FrameInfoPage import FrameInfoPage
from .CommandHistoryPage import CommandHistoryPage
from .LauncherPage import LauncherPage
from .ObsInfoPage import ObsInfoPage
from .SkMonitorPage import SkMonitorPage
from .LogPage import LogPage, MonLogPage
from .DialogPage import DialogPage
from .OptionsPage import OptionsPage
from . import Page
from . import Workspace
from . import dialogs
from ..version import __version__


class IntegView(GwMain.GwMain, Widgets.Application):

    def __init__(self, logger, preferences,
                 ev_quit, queues, logtype='normal'):

        app_settings = preferences.create_category('general')

        # Create the top level app
        Widgets.Application.__init__(self, logger=logger, settings=app_settings)
        GwMain.GwMain.__init__(self, logger=logger, ev_quit=ev_quit, app=self)

        self.queue = queues
        self.logtype = logtype
        self.lock = threading.RLock()
        # Used for tagging commands
        self.cmdcount = 0
        # ugh--ugly race condition hack
        common.set_view(self)

        self.gui_queue = Queue.Queue()
        self.placeholder = '--notdone--'
        self.gui_thread_id = None

        # for managing timers
        self.obs_timers = []
        self._obs_timer = None

        self.w = Bunch.Bunch()

        self.prefs = preferences
        self.settings = self.prefs.create_category('default')
        self.settings.set_defaults(audible_errors=True,
                                   suppress_confirm_exec=True,
                                   embed_dialogs=False,
                                   wrap_lines=False,
                                   show_line_numbers=False,
                                   clear_obs_info=True)

        # This is the home directory for loading all kinds of files
        self.procdir = None
        # This is the list of directories to search for include
        # (e.g. PRM) files named by other files
        self.include_dirs = []

        # Set default location, until changed
        procdir = os.path.join(os.environ['HOME'], 'Procedure')
        self.set_procdir(procdir, 'SUKA')

    def build_toplevel(self, layout):
        # Give every button built from here on a hover highlight (dark green
        # background, yellow text), as the GTK version did.  Left set for the
        # whole UI; bracket with Button.set_hover_color(None, None) to exclude
        # a region.
        Widgets.Button.set_hover_color('forestgreen', 'yellow')

        # Dynamically create the desktop layout
        self.desk = GwDesktop.Desktop(self)
        self.desk.make_desktop(layout, widget_dict=self.w)
        #self.desk.add_callback('all-closed', self.quit)

        # this is the old integgui2 desktop, grafted on to the
        # ginga desktop
        self.ds = Desktop(self.w, 'desktop', 'IntegGUI Desktop')
        self.ds.logger = self.logger

        root = self.desk.toplevels[0]
        self.w.root = root
        root.add_callback('close', self.confirm_close_cb)

        root.set_title(f"Gen2 Integrated GUI II v{__version__}")
        root.set_border_width(2)

        self.w.menubar = Widgets.Menubar()
        hbox = self.w['menu']
        hbox.add_widget(self.w.menubar, stretch=1)

        self.add_statusbar()

        # Add workspaces
        self.ojws = self.ds.addws('ul', 'obsjrn', "Upper Left Workspace")
        self.oiws = self.ds.addws('ur', 'obsinfo', "Upper Right Workspace")
        #self.umws = self.ds.addws('um', 'umws', "Upper Middle Workspace")
        self.lmws = self.ds.addws('lm', 'lmws', "Lower Middle Workspace")
        self.lws = self.ds.addws('ll', 'launchers', "Lower Left Workspace")
        self.exws = self.ds.addws('lr', 'executor', "Lower Right Workspace")

        # Populate "Observation Journal" ws
        self.add_frameinfo(self.ojws)
        self.add_options(self.ojws)
        self.ojws.select('frames')

        # Populate "Lower Middle" ws
        self.handsets = self.lmws.addpage('handset', "Handset",
                                          WorkspacePage.WorkspacePage)
        self.queuepage = self.lmws.addpage('queues', "Queues",
                                           WorkspacePage.WorkspacePage)
        # QueuePage and TagPage are ported to the TextSource widget; the
        # Tags page is required for OpePage.color().
        self.add_queue(self.queuepage, 'default', create=False)
        self.add_tagpage(self.lmws)
        self.lmws.select('queues')

        self.dialogs = self.lmws.addpage('dialogs', "Dialogs",
                                         WorkspacePage.WorkspacePage)

        self.add_obsinfo(self.oiws)
        # Populate "Observation Info" ws (SkMonitorPage ported to TextSource)
        self.add_monitor(self.oiws)

        self.logpage = self.oiws.addpage('loginfo', "Logs",
                                         WorkspacePage.WorkspacePage)
        self.add_history(self.oiws)
        self.oiws.select('obsinfo')

        # The scratch page used by "Pop and edit command".  Its tab title is
        # "Commands" but its page name is a generated filename, so keep a
        # direct handle rather than looking it up by title.
        self.cmd_page = self.new_source('command', self.exws, title='Commands')

        # Add menubar and menus
        self.add_menus(self.w.menubar)

        # Add popup dialogs
        self.add_dialogs()

        self.w.root.show()

    # Define some functions that depend on the workspace
    def raise_page(self, name):
        ws, page = self.ds.getPage(name)
        self.ds.show_ws(ws.name)
        ws.select(name)

    def lower_page(self, name):
        ws, page = self.ds.getPage(name)
        self.ds.restore_ws(ws.name)

    def raise_page_transient(self, name):
        ws, page = self.ds.getPage(name)
        self.ds.show_ws(ws.name)
        ws.showTransient(name)

    def lower_page_transient(self, name):
        ws, page = self.ds.getPage(name)
        ws.hideTransient(name)
        self.ds.restore_ws(ws.name)

    def toggle_var(self, widget, key):
        if widget.get_active():
            self.__dict__[key] = True
        else:
            self.__dict__[key] = False

    def get_settings(self):
        return self.settings

    def set_procdir(self, path, inst):
        topprocdir = common.topprocdir
        inst = inst.upper()

        if not os.path.isdir(path):
            path = os.path.join(topprocdir, inst)
            if not os.path.isdir(path):
                path = topprocdir

        self.procdir = path

        # Calculate list of include directories for this path
        # TODO: add a graphical way to modify this
        self.include_dirs = [
            path,
            os.path.join(path, 'COMMON'),
            os.path.join(topprocdir, inst),
            os.path.join(topprocdir, inst, 'COMMON'),
            os.path.join(topprocdir, 'COMMON'),
        ]
        self.logger.info("include_dirs: %s" % str(self.include_dirs))

    def add_menus(self, menubar):

        # create a File pulldown menu, and add it to the menu bar
        filemenu = menubar.add_name("File")

        # Add all the different kind of loaders to load up into these
        # default workspaces
        d = {'executers': self.exws,
             'launchers': self.lws,
             'journals': self.ojws,
             'logs': self.logpage,
             #'fits': self.fitspage,
             'handsets': self.handsets,
             'queues': self.queuepage,
             }
        self.add_load_menus(filemenu, d)

        item = filemenu.add_name("Config from session")
        item.add_callback('activated', lambda w: self.reconfig())

        filemenu.add_separator()

        quit_item = filemenu.add_name("Exit")
        quit_item.add_callback('activated', lambda w: self.confirm_close_cb(self))

        # create a Queue pulldown menu, and add it to the menu bar
        queuemenu = menubar.add_name("Queue")

        item = queuemenu.add_name("New queue ...")
        item.add_callback('activated', lambda w: self.gui_create_queue(self.queuepage))

        # create a Misc pulldown menu, and add it to the menu bar
        miscmenu = menubar.add_name("Misc")

        item = miscmenu.add_name("Sound check")
        item.add_callback('activated', lambda w: common.controller.sound_check())

        miscmenu.add_separator()

        item = miscmenu.add_name("Reset Executer")
        item.add_callback('activated',
                          lambda w: common.controller.reset_executer())

    def add_load_menus(self, filemenu, where):

        def _get_ws(bnch, name, where):
            if isinstance(where, Workspace.Workspace):
                bnch[name] = where
            ## elif isinstance(where, Desktop):
            ##     bnch[name] = where.getws(name)
            elif isinstance(where, dict):
                bnch[name] = where[name]
            else:
                raise Exception("I don't know how to find the workspace '%s' in %s" % (
                    name, where))

        ws = Bunch.Bunch()

        loadmenu = filemenu.add_menu("Load source")

        _get_ws(ws, 'executers', where)

        item = loadmenu.add_name("ope")
        item.add_callback('activated', lambda w: self.gui_load_ope(ws.executers))

        item = loadmenu.add_name("sk")
        item.add_callback('activated', lambda w: self.gui_load_sk(ws.executers))

        item = loadmenu.add_name("task")
        item.add_callback('activated', lambda w: self.gui_load_task(ws.executers))

        item = loadmenu.add_name("launcher")
        item.add_callback('activated', lambda w: self.gui_load_launcher_source(ws.executers))

        item = loadmenu.add_name("handset")
        item.add_callback('activated', lambda w: self.gui_load_handset_source(ws.executers))

        item = loadmenu.add_name("inf")
        item.add_callback('activated', lambda w: self.gui_load_inf(ws.executers))

        item = loadmenu.add_name("eph")
        item.add_callback('activated', lambda w: self.gui_load_ephem(ws.executers))

        item = loadmenu.add_name("tsc track")
        item.add_callback('activated', lambda w: self.gui_load_tscTrack(ws.executers))

        loadmenu = filemenu.add_menu("Load")

        item = loadmenu.add_name("directory")
        item.add_callback('activated', lambda w: self.gui_load_folder(ws.executers, '*'))

        _get_ws(ws, 'launchers', where)

        item = loadmenu.add_name("launcher")
        item.add_callback('activated', lambda w: self.gui_load_launcher(ws.launchers))

        _get_ws(ws, 'handsets', where)

        item = loadmenu.add_name("handset")
        item.add_callback('activated', lambda w: self.gui_load_handset(ws.handsets))

        _get_ws(ws, 'logs', where)

        item = loadmenu.add_name("log")
        item.add_callback('activated', lambda w: self.gui_load_log(ws.logs))

        item = loadmenu.add_name("monlog")
        item.add_callback('activated', lambda w: self.gui_load_monlog(ws.logs))

        # "New" submenu
        newmenu = filemenu.add_menu("New")

        # New->Source sub-sub-menu
        newsrcmenu = newmenu.add_menu("Source")

        item = newsrcmenu.add_name("Command page")
        item.add_callback('activated', lambda w: self.new_source('command',
                                                                 ws.executers))

        item = newsrcmenu.add_name("OPE file")
        item.add_callback('activated', lambda w: self.new_source('ope',
                                                                 ws.executers))

        # end of New->Source

        _get_ws(ws, 'queues', where)

        item = newmenu.add_name("Queue ...")
        item.add_callback('activated', lambda w: self.gui_create_queue(ws.queues))

        _get_ws(ws, 'journals', where)

        item = newmenu.add_name("Workspace ...")
        item.add_callback('activated', lambda w: self.gui_create_workspace(ws.journals))

    def add_dialogs(self):
        self.filesel = dict()

        # OPE files
        f = Widgets.FileDialog(parent=self.w.root)
        f.set_mode('file')
        f.set_title("Load OPE file")
        f.set_directory(self.procdir)
        f.clear_filters()
        # OPE and CD files are both loaded as OpePage (and colored the same)
        f.add_ext_filter("OPE/CD files", ".ope")
        f.add_ext_filter("OPE/CD files", ".cd")
        self.filesel['ope'] = f

        # Observation scripts
        f = Widgets.FileDialog(parent=self.w.root)
        f.set_mode('file')
        f.set_title("Load observation script (.sk file)")
        f.set_directory(os.environ['OBSHOME'])
        f.clear_filters()
        f.add_ext_filter(".sk files", ".sk")
        self.filesel['sk'] = f

        # Python tasks
        f = Widgets.FileDialog(parent=self.w.root)
        f.set_mode('file')
        f.set_title("Load Python task (.py file)")
        f.set_directory(os.environ['OBSHOME'])
        f.clear_filters()
        f.add_ext_filter(".py files", ".py")
        self.filesel['task'] = f

        # Folders
        f = Widgets.FileDialog(parent=self.w.root)
        f.set_mode('directory')
        f.set_title("Load folder")
        f.set_directory(self.procdir)
        f.clear_filters()
        self.filesel['folder'] = f

        # .INF files
        f = Widgets.FileDialog(parent=self.w.root)
        f.set_mode('file')
        f.set_title("Load INF file (.inf) for COMICS")
        initialdir = os.path.join(os.environ['HOME'], 'Procedure',
                                  'COMICS')
        if not os.path.isdir(initialdir):
            initialdir = self.procdir
        f.set_directory(initialdir)
        f.clear_filters()
        f.add_ext_filter(".inf files", ".inf")
        self.filesel['inf'] = f

        # Ephemeris files
        f = Widgets.FileDialog(parent=self.w.root)
        f.set_mode('file')
        f.set_title("Load ephemeris file")
        f.set_directory(self.procdir)
        f.clear_filters()
        #f.add_ext_filter(".eph files", ".eph")
        self.filesel['eph'] = f

        # TSC non-sidereal tracking files
        f = Widgets.FileDialog(parent=self.w.root)
        f.set_mode('files')
        f.set_title("Load non-sidereal TSC-native tracking file(s)")
        f.set_directory(self.procdir)
        f.clear_filters()
        f.add_ext_filter(".tsc files", ".tsc")
        self.filesel['tsc'] = f

        # Launcher source files
        f = Widgets.FileDialog(parent=self.w.root)
        f.set_mode('file')
        f.set_title("Load launcher source file")
        f.set_directory(os.environ['OBSHOME'])
        f.clear_filters()
        f.add_ext_filter("YAML files", ".yml")
        self.filesel['launcher_source'] = f

        # Handset source files
        f = Widgets.FileDialog(parent=self.w.root)
        f.set_mode('file')
        f.set_title("Load handset source file")
        f.set_directory(os.environ['OBSHOME'])
        f.clear_filters()
        f.add_ext_filter("YAML files", ".yml")
        self.filesel['handset_source'] = f

        # Launcher as non-source
        f = Widgets.FileDialog(parent=self.w.root)
        f.set_mode('file')
        f.set_title("Load launcher")
        f.set_directory(os.environ['OBSHOME'])
        f.clear_filters()
        f.add_ext_filter("YAML files", ".yml")
        self.filesel['launcher'] = f

        # Handset as non-source
        f = Widgets.FileDialog(parent=self.w.root)
        f.set_mode('file')
        f.set_title("Load handset")
        f.set_directory(os.environ['OBSHOME'])
        f.clear_filters()
        f.add_ext_filter("YAML files", ".yml")
        self.filesel['handset'] = f

        # Log files
        f = Widgets.FileDialog(parent=self.w.root)
        f.set_mode('file')
        f.set_title("Follow log")
        initialdir = os.path.abspath(os.environ['LOGHOME'])
        f.set_directory(initialdir)
        f.clear_filters()
        f.add_ext_filter("Log files", ".log")
        self.filesel['log'] = f

    def message_box(self, category, title, message, parent=None):
        if parent is None:
            parent = self.w.root

        def callback(w, val):
            self.remove_window(w)
            w.delete()

        warn = Widgets.MessageDialog(title=title, modal=False,
                                     parent=parent,
                                     buttons=[("Dismiss", 0)],
                                     autoclose=False)
        warn.set_message(category, message)
        warn.add_callback('activated', callback)
        warn.add_callback('close', lambda w: callback(w, 0))
        self.add_window(warn)
        warn.show()

    def add_statusbar(self):
        hbox = self.w['status']

        # TODO: should we use a TextWidget so we can use tags?
        self.w.status = Widgets.Label("")
        hbox.add_widget(self.w.status, stretch=1)

        btns = Widgets.ButtonBox()
        btns.set_margins(2, 2, 2, 2)
        btns.set_spacing(5)

        self.btn_kill = Widgets.Button("Kill")
        self.btn_kill.add_callback('activated', lambda w: self.kill())
        self.btn_kill.set_color(bg=common.launcher_colors['killbtn'])

        btns.add_widget(self.btn_kill)

        hbox.add_widget(btns, stretch=0)

    def statusMsg(self, format, *args):
        if not format:
            msgstr = ''
        else:
            msgstr = format % args

        # sanity check on message string
        maxlen = 140
        if len(msgstr) > maxlen:
            # trim excess characters that can cause the label to become
            # too large
            msgstr = msgstr[:maxlen]

        self.w.status.set_text(msgstr)

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
                width, height = [int(x) for x in match.groups()]
                self.w.root.resize(width, height)

        # TODO: placement
        if pos:
            pass

#     def set_controller(self, controller):
#         self.controller = controller

    def popup_error(self, errstr):
        self.logger.error(errstr)
        self.message_box('error', "IntegGUI Error", errstr)

    def popup_confirm(self, title, qstr, f_res, *args, **kwdargs):
        w = Widgets.MessageDialog(title=title, modal=False,
                                  parent=self.w.root,
                                  buttons=[("NO", 0), ("YES", 1)],
                                  autoclose=False)
        w.set_message('question', qstr)

        def f(w, rsp):
            self.remove_window(w)
            w.delete()
            res = 'yes' if rsp == 1 else 'no'
            f_res(res, *args, **kwdargs)

        w.add_callback("activated", f)
        self.add_window(w)
        w.show()

    def popup_info(self, title, qstr):
        w = Widgets.MessageDialog(title=title, modal=False,
                                  parent=self.w.root,
                                  autoclose=False)
        w.set_message('info', qstr)

        def f(w, rsp):
            self.remove_window(w)
            w.delete()

        w.add_callback('close', lambda w: f(w, 0))
        w.add_callback('activated', f)
        self.add_window(w)
        w.show()

    def readfile(self, filepath):
        with open(filepath, 'r') as in_f:
            buf = in_f.read()
        return buf

    # NOT USED?
    def popup_select(self, title, execfn, filedir):
        def callback(w, filepaths):
            self.remove_window(w)
            w.delete()
            if len(filepaths) > 0:
                execfn(filepaths[0])

        f = Widgets.FileDialog(parent=self.w.root)
        f.set_mode('file')
        f.set_title(title)
        f.set_directory(filedir)
        f.clear_filters()
        f.add_callback('activated', callback)
        self.add_window(f)
        f.popup()

    def popup_save(self, title, execfn, filedir, filename=None):
        def callback(w, filepaths):
            self.remove_window(w)
            w.delete()
            if len(filepaths) > 0:
                execfn(filepaths[0])

        f = Widgets.FileDialog(parent=self.w.root)
        f.set_mode('save')
        f.set_title(title)
        f.set_directory(filedir)
        f.clear_filters()
        if filename is not None:
            f.set_filename(filename)
        f.add_callback('activated', callback)
        self.add_window(f)
        f.popup()

    def gui_load_monlog(self, workspace):

        def pick_log(w, rsp, cbox, names):
            self.remove_window(w)
            logName = names[cbox.get_text()].strip()
            w.delete()
            if rsp == 1:
                self.load_monlog(workspace, logName)
            return True

        dialog = Widgets.Dialog(title="Choose Log", flags=0,
                                parent=self.w.root,
                                buttons=[("Cancel", 0), ("Ok", 1)])
        vbox = dialog.get_content_area()
        vbox.set_border_width(4)
        vbox.add_widget(Widgets.Label("Select a log to view"),
                        stretch=0)
        # Add a combo box to the content area containing the names of the
        cbox = Widgets.ComboBox()
        names = list(common.controller.valid_monlogs)
        names.sort()
        for name in names:
            cbox.append_text(name)
        cbox.set_index(0)
        vbox.add_widget(cbox, stretch=0)
        dialog.add_callback("activated", pick_log, cbox, names)
        dialog.add_callback("close", 0, pick_log, cbox, names)
        self.add_window(dialog)
        dialog.show()
        return True

    def load_monlog(self, workspace, logname):
        try:
            try:
                page = workspace.getPage(logname)
                raise Exception("There is already a log open by that name!")
            except KeyError:
                pass
            page = workspace.addpage(logname, logname, MonLogPage)

            # Add standard error regex matching
            page.add_regexes(common.error_regexes)

            # Bring log tab to front
            workspace.select(page.name)
            return page

        except Exception as e:
            self.popup_error("Cannot load log '%s': %s" % (
                logname, str(e)))
            return None

    def gui_load_log(self, workspace):
        f = self.filesel['log']
        f.set_callback('activated',
                       lambda filepaths: self.load_log(workspace, filepaths[0]))
        f.popup()

    def load_log(self, workspace, filepath):
        try:
            dirname, filename = os.path.split(filepath)
            # Drop ".log" from tab names
            filepfx, filesfx = os.path.splitext(filename)
            if filesfx.lower() == '.log':
                filename = filepfx

            name = filename
            page = workspace.addpage(name, name, LogPage)

            # Add standard error regex matching
            page.add_regexes(common.error_regexes)

            page.load(filepath)

            # Bring log tab to front
            workspace.select(page.name)
            return page

        except Exception as e:
            self.popup_error("Cannot load '%s': %s" % (
                filepath, str(e)))
            return None

    def gui_load_ope(self, workspace):
        f = self.filesel['ope']
        # procdir can change at runtime (e.g. when the proposal/instrument is
        # set), so refresh the dialog's directory to the current value instead
        # of using the one captured when the dialog was created
        if self.procdir is not None and os.path.isdir(self.procdir):
            f.set_directory(self.procdir)
        f.set_callback('activated',
                       lambda w, filepaths: self.load_generic(workspace,
                                                              filepaths[0],
                                                              OpePage.OpePage))
        f.popup()

    def gui_load_sk(self, workspace):
        f = self.filesel['sk']
        f.set_callback('activated',
                       lambda w, filepaths: self.load_generic(workspace,
                                                              filepaths[0],
                                                              SkPage))
        f.popup()

    def gui_load_task(self, workspace):
        f = self.filesel['task']
        f.set_callback('activated',
                       lambda w, filepaths: self.load_generic(workspace,
                                                              filepaths[0],
                                                              TaskPage)),
        f.popup()

    def gui_load_folder(self, workspace, pattern):
        f = self.filesel['folder']
        # refresh to the current procdir (it can change at runtime)
        if self.procdir is not None and os.path.isdir(self.procdir):
            f.set_directory(self.procdir)
        f.set_callback('activated',
                       lambda w, dirpaths: self.load_folder(workspace,
                                                            dirpaths[0],
                                                            pattern=pattern))
        f.popup()

    def gui_load_inf(self, workspace):
        f = self.filesel['inf']
        f.set_callback('activated',
                       lambda w, filepaths: self.load_generic(workspace,
                                                              filepaths[0],
                                                              InfPage))
        f.popup()

    def gui_load_ephem(self, workspace):
        f = self.filesel['eph']
        # refresh to the current procdir (it can change at runtime)
        if self.procdir is not None and os.path.isdir(self.procdir):
            f.set_directory(self.procdir)
        f.set_callback('activated',
                       lambda w, filepaths: self.load_generic(workspace,
                                                              filepaths[0],
                                                              EphemPage))
        f.popup()

    def gui_load_tscTrack(self, workspace):
        f = self.filesel['tsc']
        # refresh to the current procdir (it can change at runtime)
        if self.procdir is not None and os.path.isdir(self.procdir):
            f.set_directory(self.procdir)

        def callback(w, filepaths):
            for filepath in filepaths:
                self.load_generic(workspace, filepath, TSCTrackPage)
        f.set_callback('activated', callback)
        f.popup()

    def gui_load_launcher_source(self, workspace):
        f = self.filesel['launcher_source']
        f.set_callback('activated',
                       lambda w, filepaths: self.load_generic(workspace,
                                                              filepaths[0],
                                                              # ???!!!
                                                              CodePage.CodePage))
        f.popup()

    def gui_load_handset_source(self, workspace):
        f = self.filesel['handset_source']
        f.set_callback('activated',
                       lambda w, filepaths: self.load_generic(workspace,
                                                              filepaths[0],
                                                              # ???!!!
                                                              CodePage.CodePage))
        f.popup()

    def open_generic(self, workspace, buf, filepath, pageKlass,
                     title=None):
        try:
            dirname, filename = os.path.split(filepath)
            #print(pageKlass)

            name = filename
            if not title:
                title = name
            page = workspace.addpage(name, title, pageKlass)
            page.load(filepath, buf)

            workspace.select(page.name)
            return page

        except Exception as e:
            self.popup_error("Cannot load '%s': %s" % (
                filepath, str(e)))
            return None

    def kill(self):
        controller = common.controller
        controller.tm_restart()

    def load_ope(self, filepath):
        return self.load_generic(self.exws, filepath, OpePage.OpePage)

    def load_inf(self, filepath):
        return self.load_generic(self.exws, filepath, InfPage)

    def load_ephem(self, filepath):
        return self.load_generic(self.exws, filepath, EphemPage)

    def load_tscTrack(self, filepath):
        return self.load_generic(self.exws, filepath, TSCTrackPage)

    def load_file(self, filepath):
        if os.path.isdir(filepath):
            return self.load_folder(self.exws, filepath)
        else:
            pfx, ext = os.path.splitext(filepath)
            ext = ext.lower()[1:]
            try:
                d = {'ope': OpePage.OpePage,
                     'cd': OpePage.OpePage,
                     'sk': SkPage,
                     'py': TaskPage,
                     'inf': InfPage,
                     'eph': EphemPage,
                     'tsc': TSCTrackPage,
                     }
                pageKlass = d[ext]
            except KeyError:
                pageKlass = CodePage.CodePage

            return self.load_generic(self.exws, filepath, pageKlass)

    def load_generic(self, workspace, filepath, pageKlass):
        try:
            buf = self.readfile(filepath)

            return self.open_generic(workspace, buf, filepath, pageKlass)

        except Exception as e:
            self.popup_error("Cannot load '%s': %s" % (
                filepath, str(e)))

    def load_folder(self, workspace, dirpath, pattern='*'):
        try:
            pathpfx, dirname = os.path.split(dirpath)

            page = workspace.addpage(dirpath, dirname, DirectoryPage)
            page.load(dirpath, pattern)
            workspace.select(page.name)
            return page

        except Exception as e:
            self.popup_error("Cannot load directory '%s': %s" % (
                dirpath, str(e)))
            return None

    def gui_load_launcher(self, workspace):
        f = self.filesel['launcher']
        f.set_callback('activated',
                       lambda w, filepaths: self.load_launcher(workspace,
                                                               filepaths[0]))
        f.popup()

    def load_launcher(self, workspace, filepath):
        try:
            buf = self.readfile(filepath)

            dirname, filename = os.path.split(filepath)

            match = re.match(r'^(.+)\.yml$', filename)
            if not match:
                return

            name = match.group(1).replace('_', ' ')
            page = workspace.addpage(name, name, LauncherPage,
                                     adjname=False)
            page.load(buf)
            workspace.select(page.name)
            return page

        except Exception as e:
            self.popup_error("Cannot load '%s': %s" % (
                filepath, str(e)))
            return None

    def gui_load_handset(self, workspace):
        f = self.filesel['handset']
        f.set_callback('activated',
                       lambda w, filepaths: self.load_handset(workspace,
                                                              filepaths[0]))
        f.popup()

    def load_handset(self, workspace, filepath):
        try:
            buf = self.readfile(filepath)

            dirname, filename = os.path.split(filepath)

            match = re.match(r'^(.+)\.yml$', filename)
            if not match:
                return None

            name = match.group(1).replace('_', ' ')
            page = workspace.addpage(name, name, HandsetPage,
                                     adjname=False)
            page.load(buf)
            workspace.select(page.name)
            return page

        except Exception as e:
            self.popup_error("Cannot load '%s': %s" % (
                filepath, str(e)))
            return None

    def new_source(self, pagetype, workspace, title=None):
        if pagetype == 'command':
            buf = ":COMMAND\n# paste or type commands below\n\n"
            ext = '.cd'
            pageKlass = OpePage.OpePage
        elif pagetype == 'ope':
            buf = """
:HEADER
:PARAMETER
# targets and definitions here

:COMMAND
# paste or type commands below
"""
            ext = '.ope'
            pageKlass = OpePage.OpePage

        filename = time.strftime("%Y%m%d-%H%M%S", time.localtime())
        filename = filename + ext
        filepath = os.path.join(self.procdir, filename)

        return self.open_generic(workspace, buf, filepath, pageKlass,
                                 title=title)

    def add_history(self, workspace):
        try:
            page = workspace.addpage('history', "History", CommandHistoryPage)

            # Global side effect--for now we can only have one history page
            self.history = page
            workspace.select(page.name)
            return page

        except Exception as e:
            self.popup_error(f"Cannot load history page: {e}")
            return None

    def add_tagpage(self, workspace):
        try:
            page = workspace.addpage('tags', "Tags", TagPage)

            # Global side effect--for now we can only have one tag page
            self.tagpage = page
            workspace.select(page.name)
            return page

        except Exception as e:
            self.popup_error("Cannot load tag page: %s" % (
                str(e)))
            return None

    def add_frameinfo(self, workspace):
        try:
            page = workspace.addpage('frames', "Frames", FrameInfoPage)

            # Global side effect--for now we can only have one frame info page
            self.framepage = page
            workspace.select(page.name)
            return page

        except Exception as e:
            self.popup_error("Cannot load frame info page: %s" % (
                str(e)))
            return None

    def add_options(self, workspace):
        try:
            page = workspace.addpage('options', "Options", OptionsPage)

            workspace.select(page.name)
            return page

        except Exception as e:
            self.popup_error("Cannot load options page: %s" % (
                str(e)))
            return None

    def add_obsinfo(self, workspace):
        try:
            page = workspace.addpage('obsinfo', "Obsinfo", ObsInfoPage)

            # Global side effect--for now we can only have one obs info page
            self.obsinfo = page
            workspace.select(page.name)
            return page

        except Exception as e:
            self.popup_error("Cannot load obs info page: %s" % (
                str(e)))
            return None

    def add_monitor(self, workspace):
        try:
            page = workspace.addpage('moninfo', "Monitor", SkMonitorPage)

            # Global side effect--for now we can only have one monitor page
            self.monpage = page
            workspace.select(page.name)
            return page

        except Exception as e:
            self.popup_error("Cannot load monitor page: %s" % (
                str(e)))
            return None

    def get_launcher_paths(self, insname, launcherpfx):
        insname = insname.upper()
        filename = '%s*.yml' % launcherpfx
        pathmatch = os.path.join(os.environ['OBSHOME'], insname,
                                 'launcher', filename)

        res = glob.glob(pathmatch)
        return res

    def get_file_paths_workspace(self, workspace, regex=None):
        """This returns a list of all the paths of files loaded into
        windows in workspace, that match regular expression _regex_.
        """
        res = []
        for page in workspace.getPages():
            if hasattr(page, 'get_filepath'):
                path = page.get_filepath()
                if (not regex) or re.match(regex, path):
                    res.append(path)
        return res

    def get_file_paths_desktop(self, desktop, regex=None):
        res = []
        for ws in desktop.getWorkspaces():
            res.extend(self.get_file_paths_workspace(ws, regex=regex))

        return res

    def get_ope_paths(self):
        return self.get_file_paths_desktop(self.ds, regex=r'^.*\.(ope|OPE)$')

    def get_target_info(self):
        res_lst = []
        for ws in self.ds.getWorkspaces():
            for page in ws.getPages():
                if isinstance(page, OpePage.OpePage):
                    tgt_info = page.get_target_info()
                    res_lst.append(tgt_info)
        return res_lst

    def create_dialog(self, name, title, buttons=None, callback=None):
        try:
            try:
                page = self.dialogs.getPage(name)
                raise Exception("There is already a paage open by that name!")
            except KeyError:
                pass
            page = self.dialogs.addpage(name, title, DialogPage)

            if buttons is not None and callback is not None:
                page.add_buttons(list(buttons), callback)

            # Bring tab to front
            self.dialogs.select(page.name)
            return page

        except Exception as e:
            self.popup_error("Cannot create dialog '%s': %s" % (
                title, str(e)))
            return None

    def close_pages_workspace(self, workspace, pageKlass, exclude=[]):
        try:
            for page in workspace.getPages():
                if isinstance(page, pageKlass) and \
                        (page.name not in exclude):
                    self.logger.debug("closing page '%s'" % (page.name))
                    page.close()

                elif isinstance(page, WorkspacePage.WorkspacePage):
                    # Recurse into workspace pages
                    self.close_pages_workspace(page, pageKlass, exclude=exclude)

        except Exception as e:
            self.logger.error("Error closing pages: %s" % str(e))

    def close_pages_desktop(self, desktop, pageKlass, exclude=[]):
        for ws in desktop.getWorkspaces():
            self.close_pages_workspace(ws, pageKlass, exclude=exclude)

    def close_pages(self, pageKlass, exclude=[]):
        self.close_pages_desktop(self.ds, pageKlass)

    def close_launchers(self):
        return self.close_pages(LauncherPage)

    def close_handsets(self):
        return self.close_pages(HandsetPage)

    def close_logs(self):
        if self.logtype == 'monlog':
            return self.close_pages(MonLogPage)
        self.close_pages_workspace(self.logpage, LogPage)

    def reconfig(self):
        self.close_logs()
        self.close_handsets()
        self.close_launchers()

        if self.settings.get('clear_obs_info', True):
            self.clear_observation()

        try:
            common.controller.ctl_do(common.controller.config_from_session,
                                     common.controller.options.session)
        except Exception as e:
            self.gui.popup_error("Failed to initialize from session: %s" % (
                str(e)))

    def clear_observation(self):

        # Clear some pages
        for name in ('history', 'frames', 'tags', 'moninfo'):
            try:
                ws, page = self.ds.getPage(name)
                page.clear()
            except BaseException:
                # possibly they don't have this page open
                pass

        # TODO: breaks abstraction to know that the controller has this.
        # Fix!
        #common.controller.fits.clear()

    def get_handset_paths(self, insname, handsetpfx):
        insname = insname.upper()
        filename = '%s*.yml' % handsetpfx
        pathmatch = os.path.join(os.environ['OBSHOME'], insname,
                                 'handset', filename)

        res = glob.glob(pathmatch)
        return res

    def get_log_path(self, insname):
        filename = '%s.log' % insname
        filepath = os.path.join(os.environ['LOGHOME'], filename)
        return filepath

    def gui_create_queue(self, workspace):

        def create_queue_res(w, rsp, went):
            self.remove_window(w)
            queueName = went.get_text().strip()
            w.delete()
            if rsp == 1:
                self.add_queue(workspace, queueName)
            return True

        dialog = Widgets.Dialog(title="Create Queue", flags=0,
                                parent=self.w.root,
                                buttons=[("Cancel", 0), ("Ok", 1)])
        vbox = dialog.get_content_area()
        vbox.set_border_width(4)
        vbox.add_widget(Widgets.Label("Please enter a name for the new queue:"),
                        stretch=0)
        ent = Widgets.TextEntry(editable=True)
        vbox.add_widget(ent, stretch=0)
        dialog.add_callback("activated", create_queue_res, ent)
        dialog.add_callback("close", lambda w: create_queue_res(w, 0, ent))
        self.add_window(dialog)
        dialog.show()

    def add_queue(self, workspace, name, create=True):
        queueName = name.strip().lower()
        try:
            if create:
                if queueName in self.queue:
                    raise Exception("A queue with that name already exists!")
                queue = common.controller.addQueue(queueName, self.logger)
            else:
                queue = self.queue[queueName]

            page = workspace.addpage(queueName, queueName.capitalize(),
                                     QueuePage)
            page.set_queue(queueName, queue)

            workspace.select(page.name)
            return page

        except Exception as e:
            self.popup_error("Cannot add queue page '%s': %s" % (
                name, str(e)))
            return None

    def gui_create_workspace(self, workspace):

        def create_workspace_res(w, rsp, went):
            self.remove_window(w)
            name = went.get_text()
            w.delete()
            if rsp == 1:
                self.add_workspace(workspace, name)
            return True

        dialog = Widgets.Dialog(title="Create Workspace",
                                flags=0, buttons=[("Cancel", 0), ("Ok", 1)])
        vbox = dialog.get_content_area()
        vbox.set_border_width(4)
        vbox.add_widget(Widgets.Label("Please enter a name for the new workspace:"),
                        stretch=0)
        ent = Widgets.TextEntry(editable=True)
        vbox.add_widget(ent, stretch=0)
        dialog.add_callback("activated", create_workspace_res, ent)
        self.add_window(dialog)
        dialog.show()

    def add_workspace(self, workspace, name):
        try:
            page = workspace.addpage(name, name,
                                     WorkspacePage.WorkspacePage)

            workspace.select(page.name)

            page.menu_close.set_sensitive(True)

            #self.add_load_menus(page.wsmenu, page)
            return page

        except Exception as e:
            self.popup_error("Cannot create workspace page: %s" % (
                str(e)))
            return None

    def edit_command(self, cmdstr):
        try:
            page = getattr(self, 'cmd_page', None)
            if page is None or getattr(page, 'closed', False):
                # scratch page was closed (or never created) -- remake it
                page = self.cmd_page = self.new_source('command', self.exws,
                                                       title='Commands')
            # accumulate popped commands (append) rather than replacing;
            # make sure each lands on its own line
            if not cmdstr.endswith('\n'):
                cmdstr = cmdstr + '\n'
            page.tw.append_text(cmdstr)

            # Bring the Commands tab to front (select by page name, not title)
            self.exws.select(page.name)
        except Exception as e:
            self.popup_error("Cannot edit command: %s" % (
                str(e)))

    def delete_event(self, widget, event, data=None):
        self.ev_quit.set()
        return False

    def confirm_close_cb(self, app):
        # confirm close with a dialog here
        q_quit = Widgets.MessageDialog(title="Confirm Quit", modal=False,
                                       buttons=[("Cancel", False), ("Confirm", True)],
                                       autoclose=False)
        # necessary so it doesn't get garbage collected right away
        self.w.quit_dialog = q_quit
        q_quit.set_message('question', "Do you really want to quit?")
        q_quit.add_callback('activated', self._confirm_quit_cb)
        q_quit.add_callback('close', lambda w: self._confirm_quit_cb(w, False))
        self.add_window(q_quit)
        q_quit.show()

    def _confirm_quit_cb(self, w, tf):
        self.remove_window(w)
        self.w.quit_dialog.delete()
        self.w.quit_dialog = None
        if not tf:
            return

        self.ev_quit.set()
        self.quit()
        return False

    def reset_pause(self):
        try:
            # Perform a global reset across all command-type pages
            for ws in self.ds.getWorkspaces():
                for page in ws.getPages():
                    if isinstance(page, Page.CommandPage):
                        page.reset_pause()
        except Exception as e:
            self.logger.error("Error resetting pages: %s" % str(e))

    def _rm_timer(self, timer):
        with self.lock:
            try:
                self.obs_timers.remove(timer)
            except ValueError:
                pass
            if self._obs_timer is timer:
                self._obs_timer = None
        # The countdown has reached zero (the timer expired): drive a final
        # update to 0 so the display shows 0 and the dialog dismisses itself.
        # The per-second tick can't be relied on for this last step, since it
        # races with this expiry callback.
        obsinfo = timer.data.obsinfo
        if obsinfo is not None:
            try:
                obsinfo.update_timer(0)
            except Exception as e:
                self.logger.error("error finalizing obsinfo timer: %s" % str(e))
        dialog = timer.data.dialog
        if dialog is not None and getattr(dialog, 'w', None) is not None:
            try:
                dialog.update_timer(0)
            except Exception as e:
                self.logger.error("error finalizing timer dialog: %s" % str(e))
        # stop the per-second display tick, if any
        try:
            if timer.data.tick_timer is not None:
                timer.data.tick_timer.stop()
        except Exception:
            pass

    def _obs_timer_tick(self, timer):
        # Drive the per-second countdown display.  This is owned by the view
        # (not the dialog) so the ObsInfoPage keeps counting down even after
        # the Timer dialog is closed.
        secs = timer.time_left()

        obsinfo = timer.data.obsinfo
        if obsinfo is not None:
            try:
                obsinfo.update_timer(secs)
            except Exception as e:
                self.logger.error("error updating obsinfo timer: %s" % str(e))

        dialog = timer.data.dialog
        if dialog is not None and getattr(dialog, 'w', None) is not None:
            try:
                dialog.update_timer(secs)
            except Exception as e:
                self.logger.error("error updating timer dialog: %s" % str(e))

        # keep ticking every second while the timer is still running
        if secs > 0.0 and timer in self.obs_timers:
            if timer.data.tick_timer is None:
                tick = self.make_timer()
                tick.add_callback('expired',
                                  lambda t: self._obs_timer_tick(timer))
                timer.data.tick_timer = tick
            timer.data.tick_timer.start(1.0)

    ############################################################
    # Interface from controller into the view
    #
    ############################################################

    def obs_timer(self, tag, title, iconfile, soundfn, time_sec, callfn):
        # obs_timer is invoked from a remoteObjects worker thread; the
        # backend timer wraps a QTimer that must be created on the GUI
        # thread, so build it there (gui_call blocks for the result).
        timer = self.gui_call(self.make_timer)
        timer.duration = time_sec
        timer.data.obsinfo = None
        timer.data.dialog = None
        timer.data.tick_timer = None
        timer.add_callback('expired', self._rm_timer)
        with self.lock:
            self.obs_timers.append(timer)
            if self._obs_timer is not None:
                # new timer was
                self._obs_timer.data.obsinfo = None
            self._obs_timer = timer

        self.gui_do(timer.start)

        dialog = dialogs.Timer(logger=self.logger)
        self.gui_do(dialog.popup, title, iconfile, soundfn, timer, callfn,
                    tag=tag)
        # per-second display tick, tied to the timer itself (not the dialog)
        self.gui_do(self._obs_timer_tick, timer)

    def obs_confirmation(self, tag, title, iconfile, soundfn, btnlist, callfn):
        dialog = dialogs.Confirmation(logger=self.logger, parent=self.w.root)
        self.gui_do(dialog.popup, title, iconfile, soundfn, btnlist, callfn,
                    tag=tag)

    def obs_userinput(self, tag, title, iconfile, soundfn, itemlist, callfn):
        dialog = dialogs.UserInput(logger=self.logger, parent=self.w.root)
        self.gui_do(dialog.popup, title, iconfile, soundfn, itemlist, callfn,
                    tag=tag)

    def obs_combobox(self, tag, title, iconfile, soundfn, itemlist, callfn):
        dialog = dialogs.ComboBox(logger=self.logger, parent=self.w.root)
        self.gui_do(dialog.popup, title, iconfile, soundfn, itemlist, callfn,
                    tag=tag)

    def obs_fileselection(self, tag, title, callfn, initialdir=None, initialfile=None, multiple=True, button='open'):
        # if button.lower() == 'copy':
        #     button = "Copy"
        # elif button.lower() == 'ok':
        #     button = "Ok"
        # else:
        #     button = "Open"
        # Handset as non-source

        def callback(w, filepaths):
            self.remove_window(w)
            w.delete()
            if len(filepaths) > 0:
                if multiple:
                    callfn(filepaths)
                else:
                    callfn(filepaths[0])

        dialog = Widgets.FileDialog(parent=self.w.root, title=title)
        dialog.set_mode('files' if multiple else 'file')
        dialog.set_title(title)
        if initialdir is not None:
            dialog.set_directory(initialdir)
        if initialfile is not None:
            dialog.set_file(initialfile)
        dialog.add_callback('activated', callback)
        self.add_window(dialog)
        dialog.popup()

    def add_tscTrackPage(self, title, callfn, fileSelectionPath, checkFormat):
        # See if we already have a page with the specified title. If
        # so, use it. If not, create one using the CopyTSCTrackPage
        # class.
        try:
            copyTSCTrackPage = self.exws.getPage(title)
        except KeyError:
            copyTSCTrackPage = self.exws.addpage(title, title, CopyTSCTrackPage)
        # Setup the CopyTSCTrackPage object with the list of files and
        # then select it so the user can see it.
        copyTSCTrackPage.setup(callfn, fileSelectionPath, True, self.logger)
        self.exws.select('CopyTSCTrackFile')
        return copyTSCTrackPage

    def obs_copyfilestotsc(self, tag, title, callfn, fileSelectionPath, checkFormat=True, copyMode='manual'):
        copyTSCTrackPage = self.add_tscTrackPage(title, callfn, fileSelectionPath, checkFormat)
        if copyTSCTrackPage.okFileCount < 1:
            self.logger.error('Did not find any TSC tracking files to copy')
            if callfn:
                callfn(copyTSCTrackPage.status, copyTSCTrackPage.statusMsg, [])
        if copyMode.lower() == 'auto':
            copyTSCTrackPage.startCopy()

    def cancel_dialog(self, tag):
        self.gui_do(dialogs.cancel_dialog, tag)

    def update_frame(self, frameinfo):
        if hasattr(self, 'framepage'):
            self.gui_do(self.framepage.update_frame, frameinfo)

    def update_frames(self, framelist):
        if hasattr(self, 'framepage'):
            self.gui_do(self.framepage.update_frames, framelist)

    def update_obsinfo(self, infodict):
        self.logger.debug("OBSINFO=%s" % str(infodict))
        if hasattr(self, 'obsinfo'):
            self.gui_do(self.obsinfo.update_obsinfo, infodict)

    def update_history(self, key, info):
        if hasattr(self, 'history'):
            self.gui_do(self.history.update_command, info)

    def update_loginfo(self, logname, infodict):
        if hasattr(self, 'logpage'):
            try:
                page = self.logpage.getPage(logname)
                #print("%s --> %s" % (logname, str(infodict)))
                self.gui_do(page.add2log, infodict)
            except KeyError:
                # No log page for this log loaded, so silently drop message
                # TODO: drop into the integgui2 log page?
                pass

    def process_ast(self, ast_id, vals):
        if hasattr(self, 'monpage'):
            self.gui_do(self.monpage.process_ast, ast_id, vals)

    def process_subcommand(self, parent_path, subpath, vals):
        if hasattr(self, 'monpage'):
            self.gui_do(self.monpage.process_subcommand,
                        parent_path, subpath, vals)

    def process_task(self, path, vals):
        if hasattr(self, 'monpage'):
            self.gui_do(self.monpage.process_task, path, vals)

    def update_statusMsg(self, format, *args):
        self.gui_do(self.statusMsg, format, *args)

    def gui_do_res(self, method, *args, **kwdargs):
        """General method for calling into the GUI.
        """
        # Note: I suppose there may be a valid reason for the GUI thread
        # to create one of these, but better safe than sorry...
        self.assert_nongui_thread()

        return self.gui_do(method, *args, **kwdargs)

#END
