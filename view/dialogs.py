# 
#[ Eric Jeschke (eric@naoj.org) --
#  Last edit: Fri Feb 25 17:03:51 HST 2011
#]
import time

import gtk
import gobject

import common

dialog_count = 0

# NOTE [1]:
#   There seems to be a bug in the gtk.FileChooserDialog() where if the
# directory contents are changing while the dialog is open it will sometimes
# crash the program.  For this reason I changed the class to create the
# widget each time it is needed and destroy it afterwards
#

class FileSelection(object):
    
    # Get the selected filename and print it to the console
    def file_ok_sel(self, w, rsp):
        filepath = w.get_filename()
        self.close(w)
        if rsp == 0:
            return
        
        self.callfn(filepath)

    def __init__(self, action=gtk.FILE_CHOOSER_ACTION_OPEN):
        self.action = action

    def _create_widget(self, action):
        # Create a new file selection widget
        self.filew = gtk.FileChooserDialog(title="Select a file",
                                           action=action)
        # See NOTE [1]
        #self.filew.connect("destroy", self.close)
        if action == gtk.FILE_CHOOSER_ACTION_SAVE:
            self.filew.add_buttons(gtk.STOCK_SAVE, 1, gtk.STOCK_CANCEL, 0)
        else:
            self.filew.add_buttons(gtk.STOCK_OPEN, 1, gtk.STOCK_CANCEL, 0)
        self.filew.set_default_response(1)
        
        # Connect the ok_button to file_ok_sel method
        #self.filew.ok_button.connect("clicked", self.file_ok_sel)
        self.filew.connect("response", self.file_ok_sel)
    
        # Connect the cancel_button to destroy the widget
        #self.filew.cancel_button.connect("clicked", self.close)
    
    def popup(self, title, callfn, initialdir=None,
              filename=None):
        # See NOTE [1]
        self._create_widget(self.action)
        
        self.callfn = callfn
        self.filew.set_title(title)
        if initialdir:
            self.filew.set_current_folder(initialdir)

        if filename:
            #self.filew.set_filename(filename)
            self.filew.set_current_name(filename)

        self.filew.show()

    def close(self, widget):
        # See NOTE [1]
        #self.filew.hide()
        self.filew.destroy()
        self.filew = None


class MyDialog(gtk.Dialog):
    def __init__(self, title=None, flags=None, buttons=None,
                 callback=None):

        button_list = []
        for name, val in buttons:
            button_list.extend([name, val])

        super(MyDialog, self).__init__(title=title, flags=flags,
                                       buttons=tuple(button_list))
        #self.w.connect("close", self.close)
        if callback:
            self.connect("response", callback)
        

class Confirmation(object):

    def __init__(self, title='OBS Confirmation',
                 logger=None, soundfn=None, timefreq=3):
        self.title = title
        self.logger = logger
        
        self.soundfn = soundfn
        self.timertask = None
        self.interval = timefreq * 1000
        
    def _create_widget(self, title, iconfile, buttons, callback):
        global dialog_count
        
        if not common.view.embed_dialogs:
            ## self.w = gtk.Dialog(title=self.title,
            ##                     flags=gtk.DIALOG_DESTROY_WITH_PARENT,
            ##                     buttons=buttons)
            ## #self.w.connect("close", self.close)
            ## self.w.connect("response", callback)
            self.w = MyDialog(title=self.title,
                              flags=gtk.DIALOG_DESTROY_WITH_PARENT,
                              buttons=buttons,
                              callback=callback)
        else:
            dialog_count += 1
            name = 'Dialog_%d' % dialog_count
            self.w = common.view.create_dialog(name, name)
            # TODO: how do we know the location of this page!
            common.view.lmws.pushRaise('dialogs')
            common.view.dialogs.select(name)
            self.w.add_buttons(buttons, callback)
            
        cvbox = self.w.get_content_area()
        self.cvbox = cvbox
        lbl = gtk.Label()
        lbl.set_markup('<span size="x-large" weight="bold">%s</span>' % (
            title ))
        lbl.show()
        self.icon = gtk.Image()
        self.icon.set_from_file(iconfile)
        cvbox.pack_start(self.icon, expand=False, padding=2)
        cvbox.pack_start(lbl, expand=False, padding=5)

        self.anim = gtk.gdk.PixbufAnimation(iconfile)
        self.icon.set_from_animation(self.anim)
        self.icon.show_all()
        
    def popup(self, title, iconfile, soundfn, buttons, callfn):
        button_list = []
        button_vals = []
        i = 0
        for name, val in buttons:
            button_list.append([name, i])
            button_vals.append(val)
            i += 1

        def callback(w, rsp):
            self.close(w)
            if rsp < 0:
                val = None
            else:
                val = rsp
            return callfn(val, button_vals)
            
        self._create_widget(title, iconfile, tuple(button_list),
                            callback)
        self.w.show()
        self.timeraction(soundfn)

    def close(self, widget):
        #self.w.hide()
        self.w.destroy()
        self.w = None
        if self.timertask:
            gobject.source_remove(self.timertask)
        self.timertask = None

    def timeraction(self, soundfn):
        if self.w:
            if soundfn != None:
                # play sound
                soundfn()
            
                # Schedule next sound event
                self.timertask = gobject.timeout_add(self.interval,
                                                     self.timeraction,
                                                     soundfn)
        else:
            self.timertask = None

      
class UserInput(Confirmation):

    def __init__(self, title='OBS UserInput', logger=None, soundfn=None):
        super(UserInput, self).__init__(title=title, logger=logger,
                                        soundfn=soundfn)
        
    def popup(self, title, iconfile, soundfn, itemlist, callfn):
        button_vals = [1, 0]
        # NOTE: numbers here are INDEXES into self.button_vals, not values!
        button_list = [['OK', 0], ['Cancel', 1]]
            
        resDict = {}

        def callback(w, rsp):
            if rsp < 0:
                val = None
            else:
                val = rsp

            # Read out the entry widgets before we close the dialog
            d = {}
            for key, ent in resDict.items():
                s = ent.get_text()
                d[key] = s

            self.close(w)
            return callfn(val, button_vals, d)
            
        self._create_widget(title, iconfile, tuple(button_list),
                            callback)

        tbl = gtk.Table(rows=len(itemlist), columns=2)
        tbl.set_row_spacings(2)
        tbl.set_col_spacings(2)

        row = 0
        for name, val in itemlist:
            lbl = gtk.Label(name)
            lbl.set_alignment(1.0, 0.5)
            ent = gtk.Entry()
            val_s = str(val)
            ent.set_text(val_s)
            resDict[name] = ent

            tbl.attach(lbl, 0, 1, row, row+1, xoptions=gtk.FILL)
            tbl.attach(ent, 1, 2, row, row+1, xoptions=gtk.EXPAND|gtk.FILL)
            row += 1

        tbl.show_all()
        self.cvbox.pack_start(tbl, fill=True, expand=False, padding=2)
        
        self.w.show()
        self.timeraction(soundfn)


class Timer(Confirmation):

    def __init__(self, title='OBS Timer', logger=None, soundfn=None):
        super(Timer, self).__init__(title=title, logger=logger,
                                    soundfn=soundfn)
        # override time interval to 1 sec
        self.interval = 1000

        self.fmtstr = '<span size="120000" weight="bold">%s</span>'
        
        # rgb triplets we use
        self.green = gtk.gdk.Color(0.0, 0.5, 0.0)
        self.white = gtk.gdk.Color(1.0, 1.0, 1.0)

    def redraw(self):
        s = self.timestr.rjust(5)
        self.area.set_markup(self.fmtstr % (s))

    def popup(self, title, iconfile, soundfn, time_sec, callfn):
        button_vals = [0]
        # NOTE: numbers here are INDEXES into self.button_vals, not values!
        button_list = [['Close', 0]]
            
        def callback(w, rsp):
            self.close(w)
            if rsp < 0:
                val = None
            else:
                val = rsp

            return callfn(val, button_vals)
            
        self._create_widget(title, iconfile, tuple(button_list),
                            callback)

        val = float(time_sec)
        self.duration = val
        self.timestr = str(int(val)).rjust(5)
        self.timer_val = time.time() + val
        
        self.area = gtk.Label()
        self.area.modify_bg(gtk.STATE_NORMAL, self.white)
        self.area.modify_fg(gtk.STATE_NORMAL, self.green)
        self.area.show()

        self.pbar = gtk.ProgressBar()
        self.pbar.show()
        self.pbar.set_orientation(gtk.PROGRESS_LEFT_TO_RIGHT)
        self.pbar.set_fraction(0.0)
        self.pbar.set_text("0%")
        self.cvbox.pack_start(self.area, fill=True, expand=False, padding=2)
        self.cvbox.pack_start(self.pbar, fill=True, expand=False, padding=2)

        self.w.show()
        self.redraw()

        self.timertask = gobject.timeout_add(1000, self.timeraction,
                                             soundfn)

    def timeraction(self, soundfn):
        diff = self.timer_val - time.time()
        diff = max(0, int(round(diff)))
        #self.logger.debug("timer: %d sec" % diff)
        self.timestr = str(diff).rjust(5)
        if self.w:
            self.redraw()
        if diff > 0:
            frac = 1.0 - diff/self.duration
            self.pbar.set_fraction(frac)
            self.pbar.set_text("%d%%" % int(frac*100))
            self.timertask = gobject.timeout_add(1000, self.timeraction,
                                                 soundfn)
        else:
            self.timertask = None
            self.pbar.set_fraction(1.0)
            self.pbar.set_text("100%")
            self.timerstr = '0'
            self.redraw()

            # Play sound
            soundfn()
        
            self.close(self.w)
            
#END
