# 
#[ Eric Jeschke (eric@naoj.org) --
#  Last edit: Tue May 18 15:38:28 HST 2010
#]

# remove once we're certified on python 2.6
from __future__ import with_statement

# Standard library imports
import sys, os, glob
import re
import threading

# Special library imports
import pygtk
pygtk.require('2.0')
import gtk, gobject

# SSD/Gen2 imports
import Bunch
import cfg.g2soss

# Local integgui2 imports
import ope
import controller as igctrl
import view.common as common
from view.pages import *
from view.dialogs import *


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

        self.oiws = self.ds.addws('ur', 'obsinfo', "Observation Info")
        self.obsinfo = self.oiws.addpage('obsinfo', "Obsinfo", ObsInfoPage)
        self.monpage = self.oiws.addpage('moninfo', "Monitor", SkMonitorPage)
        self.logpage = self.oiws.addpage('loginfo', "Logs", WorkspacePage)
        self.fitspage = self.oiws.addpage('fitsview', "Fits", WorkspacePage)
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

        loadmenu = gtk.Menu()
        item = gtk.MenuItem(label="Load")
        filemenu.append(item)
        item.show()
        item.set_submenu(loadmenu)

        item = gtk.MenuItem(label="ope")
        loadmenu.append(item)
        item.connect_object ("activate", lambda w: self.gui_load_ope(),
                             "file.Load ope")
        item.show()

        item = gtk.MenuItem(label="fits")
        loadmenu.append(item)
        item.connect_object ("activate", lambda w: self.gui_load_fits(),
                             "file.Load fits")
        item.show()

        item = gtk.MenuItem(label="log")
        loadmenu.append(item)
        item.connect_object ("activate", lambda w: self.gui_load_log(),
                             "file.Load log")
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
        item.connect_object ("activate", lambda w: self.gui_load_launcher(),
                             "file.Load launcher")
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

        monitormenu = gtk.Menu()
        # Option variables
        self.save_decode_result = False
        self.show_times = False
        self.track_elapsed = False
        self.audible_errors = True

        item = gtk.MenuItem(label="Monitor")
        optionmenu.append(item)
        item.show()
        item.set_submenu(monitormenu)

        # Monitor menu
        w = gtk.CheckMenuItem("Save Decode Result")
        w.set_active(False)
        monitormenu.append(w)
        w.connect("activate", lambda w: self.toggle_var(w, 'save_decode_result'))
        w = gtk.CheckMenuItem("Show Times")
        w.set_active(False)
        monitormenu.append(w)
        w.connect("activate", lambda w: self.toggle_var(w, 'show_times'))
        w = gtk.CheckMenuItem("Track Elapsed")
        w.set_active(False)
        monitormenu.append(w)
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

            # Bring FITS tab to front
            self.oiws.select('loginfo')
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

            # Bring FITS tab to front
            self.oiws.select('loginfo')
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


    def reconfig(self):
        self.close_logs()
        self.close_launchers()

        common.controller.config_from_session('main')

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
        self.clear_marks(opepage)

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

        # Clear the selection
        buf.move_mark_by_name("insert", first)         
        buf.move_mark_by_name("selection_bound", first)

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
            buf.create_tag(tag)
            buf.apply_tag_by_name(tag, first, last)

            tags.append(Bunch.Bunch(tag=tag, opepage=opepage,
                                    type='opepage'))

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

        # Clear the selection
        buf = opepage.buf
        itr = buf.get_end_iter()
        buf.move_mark_by_name("insert", itr)         
        buf.move_mark_by_name("selection_bound", itr)

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
        start, end = common.get_region(buf, bnch.tag)
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
        buf = opepage.buf
        start, end = buf.get_bounds()
        for tag, bnch in common.execution_tags:
            buf.remove_tag_by_name(tag, start, end)


    def mark_exec(self, bnch, tag, queueName):

        # Get the entire OPE buffer
        buf = bnch.opepage.buf
##         start, end = buf.get_bounds()
##         rows = end.get_line()

        start, end = common.get_region(buf, bnch.tag)
        buf.apply_tag_by_name(tag, start, end)

##         # Make the row marks buffer the same length
##         # as the text file buffer
##         rw = bnch.opepage.rw
##         row, col = str(rw.index('end')).split('.')
##         rw_len = int(row)
##         if rw_len < tw_len:
##             rw.insert('end', '\n' * (tw_len - rw_len))

##         #rw.delete('%s linestart' % index, '%s lineend' % index)
##         rw.insert(index, char)

        # Mark pending tasks in the queue as '(S)cheduled'
        queueObj = self.queue['executer']

        for nbnch in queueObj.peekAll():
##             index = tw.index('%s.first' % nbnch.tag)
##             rw.insert(index, 'S')
            start, end = common.get_region(buf, nbnch.tag)
            buf.apply_tag_by_name('scheduled', start, end)
            

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
            #self.mark_exec(bnch, 'executing', queueName)
            gobject.idle_add(self.mark_exec, bnch, 'executing', queueName)
        
        return bnch, cmdstr


    def feedback_noerror(self, queueName, bnch, res):

        queueObj = self.queue[queueName]

        if bnch.type == 'opepage':
            self.mark_exec(bnch, 'done', queueName)
        #self.make_sound(cmd_ok)
        
        # If queue is empty, disable it until more commands are
        # added
        if len(queueObj) == 0:
            queueObj.disable()

            # Bing Bong!
            self.playSound(common.sound.success)

           
    def feedback_error(self, queueName, bnch, e):

        queueObj = self.queue[queueName]

        queueObj.disable()

        if bnch:
            if bnch.type == 'opepage':
                # Mark an (E)rror in the opepage
                self.mark_exec(bnch, 'error', queueName)

                # Put object back on the front of the queue
                queueObj.prepend(bnch)

        gobject.idle_add(self.popup_error, str(e))
        #self.statusMsg(str(e))

        # Peeeeeww!
        self.playSound(common.sound.failure)

        
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
#GtkLabel::width-chars = 20
}

style "nobevel"
{
GtkMenuBar::shadow-type = none
GtkStatusbar::shadow-type = none
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

## style "toggle_button" = "button"
## {
##   fg[NORMAL] = { 1.0, 0, 0 }
##   fg[ACTIVE] = { 1.0, 0, 0 }
 
## }

style "text"
{
  fg[NORMAL] = { 1.0, 1.0, 1.0 }
  font_name = "Monospace 10"
}

# These set the widget types to use the styles defined above.
# The widget types are listed in the class hierarchy, but could probably be
# just listed in this document for the users reference.

widget_class "GtkMenuBar" style "nobevel"
widget_class "GtkStatusbar" style "nobevel"
widget_class "GtkWindow" style "window"
widget_class "GtkDialog" style "window"
widget_class "GtkFileSelection" style "window"
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
