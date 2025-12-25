#
# E. Jeschke
#
import time
import threading

from ginga.gw import Widgets

from . import common

dialog_count = 0

# This is a table of dialogs that have been opened by a remote task.
dialog_table = {}
# A lock to protect the table
dialog_table_lock = threading.RLock()

def register_dialog(tag, dialog):
    """Register a dialog in the dialog table."""
    if not tag:
        # dialog is not associated with a remote task
        return
    with dialog_table_lock:
        #print("Registering dialog %s" % tag)
        dialog_table[tag] = dialog

def unregister_dialog(tag):
    """Unregister a dialog from the dialog table."""
    if not tag:
        return
    with dialog_table_lock:
        #print("Unregistering dialog %s" % tag)
        try:
            del dialog_table[tag]
        except KeyError:
            # if already deleted no big deal
            pass

def cancel_dialog(tag):
    """Cancel any dialogs associated with a remote task.
    """
    with dialog_table_lock:
        items = list(dialog_table.items())

    # Search the dialog table for a tag that starts with this tag
    for key, obj in items:
        if key.startswith(tag):
            # Found one--it must be associated with that command
            #print("Command cancelled--closing dialog %s" % key)
            unregister_dialog(key)
            if obj.w:
                obj.close(obj.w)


# NOTE [1]:
#   There seems to be a bug in the Gtk.FileChooserDialog() where if the
# directory contents are changing while the dialog is open it will sometimes
# crash the program.  For this reason I changed the class to create the
# widget each time it is needed and destroy it afterwards
#

class FileSelection:

    # Get the selected filename
    def file_ok_sel(self, w, filenames):
        self.close(w)

        self.callfn(filenames)

    def __init__(self, action='file'):
        self.action = action

    def _create_widget(self, action):
        if action == 'save':
            buttons = [("Save", 1), ("Cancel", 0)]
        else:
            buttons = [("Open", 1), ("Cancel", 0)]

        # Create a new file selection widget
        self.filew = Widgets.FileDialog(title="Select a file",
                                        parent=common.view.w.root)
        self.filew.set_mode(action)
        self.filew.connect("close", self.close)
        self.filew.connect("activated", self.file_ok_sel)

    def popup(self, title, callfn, initialdir=None,
              filename=None):
        # See NOTE [1]
        self._create_widget(self.action)

        self.callfn = callfn
        self.filew.set_title(title)
        if initialdir:
            self.filew.set_directory(initialdir)

        if filename:
            self.filew.set_filename(filename)

        self.filew.show()

    def close(self, widget):
        #self.filew.hide()
        w, self.filew = self.filew, None
        w.destroy()


class MyDialog(Widgets.Dialog):
    def __init__(self, title=None, flags=None, buttons=None,
                 callback=None):

        super().__init__(title=title, flags=flags, buttons=buttons)
        #self.w.connect("close", self.close)
        if callback:
            self.connect("activated", callback)


class SearchReplace(object):

    def __init__(self, title='Search and/or Replace'):
        self.title = title

        self.what = ''
        self.replacement = ''

    def _create_widget(self, buttons, callback):
        global dialog_count

        settings = common.view.get_settings()
        embed_dialogs = settings.get('embed_dialogs', False)

        if not embed_dialogs:
            self.w = MyDialog(title=self.title, flags=0,
                              buttons=buttons, callback=callback)
        else:
            dialog_count += 1
            name = 'Dialog_%d' % dialog_count
            self.w = common.view.create_dialog(name, name, buttons=buttons,
                                               callback=callback)
            self.w.add_callback('close', lambda w: common.view.lower_page_transient('dialogs'))
            common.view.raise_page_transient('dialogs')
            common.view.dialogs.select(name)

        cvbox = self.w.get_content_area()
        self.cvbox = cvbox
        cvbox.set_spacing(2)

        lbl = Widgets.Label('Search string:')
        self.cvbox.add_widget(lbl, stretch=0)
        self._search_widget = Widgets.Entry()
        if self.what:
            self._search_widget.set_text(self.what)
        #self._search_widget.set_activates_default(True)
        self.cvbox.add_widget(self._search_widget, stretch=0)

        lbl = Widgets.Label('Replacement string:')
        self.cvbox.add_widget(lbl, stretch=0)
        self._replace_widget = Widgets.Entry()
        if self.replacement:
            self._replace_widget.set_text(self.replacement)
        #self._replace_widget.set_activates_default(True)
        self.cvbox.add_widget(self._replace_widget, stretch=0)

        self._case_sensitive = Widgets.CheckButton("Case sensitive")
        self._case_sensitive.set_state(True)
        self._case_sensitive.set_sensitive(False)
        self.cvbox.add_widget(self._case_sensitive, stretch=0)

        self._reverse = Widgets.CheckButton("Reverse")
        self.cvbox.add_widget(self._reverse, stretch=0)

        self._message = Widgets.Label('')
        self.cvbox.add_widget(self._message, stretch=0)

    def popup(self, callfn):
        button_list = [('Close', 0), ('Replace', 1), ('Find', 2)]

        def callback(w, rsp):
            if rsp < 0:
                val = 'close'
            else:
                val = button_list[rsp][0].lower()

            if val == 'close':
                self.close(w)

            return callfn(val)

        self._create_widget(button_list, callback)
        self.set_message("Search begins at cursor")

        self.w.show()

    def is_case_sensitive(self):
        return self._case_sensitive.get_state()

    def is_reverse_search(self):
        return self._reverse.get_state()

    def get_search_text(self):
        self.what = self._search_widget.get_text()
        return self.what

    def get_replace_text(self):
        self.replacement = self._replace_widget.get_text()
        return self.replacement

    def set_message(self, text):
        self._message.set_text(text)

    def close(self, widget):
        #self.w.hide()
        widget.destroy()
        self.w = None


class Confirmation(object):

    def __init__(self, title='OBS Confirmation',
                 logger=None, soundfn=None, timefreq=5):
        self.title = title
        self.logger = logger

        self.soundfn = soundfn
        self.timertask = None
        self.interval = timefreq * 1000

    def _create_widget(self, title, iconfile, buttons, callback):
        global dialog_count

        settings = common.view.get_settings()
        embed_dialogs = settings.get('embed_dialogs', False)

        if not embed_dialogs:
            ## self.w = Gtk.Dialog(title=self.title,
            ##                     flags=Gtk.DialogFlags.DESTROY_WITH_PARENT,
            ##                     buttons=buttons)
            ## #self.w.connect("close", self.close)
            ## self.w.connect("response", callback)
            self.w = MyDialog(title=self.title,
                              flags=0,
                              buttons=buttons,
                              callback=callback)
        else:
            dialog_count += 1
            name = 'Dialog_%d' % dialog_count
            self.w = common.view.create_dialog(name, name,
                                               buttons=buttons,
                                               callback=callback)
            self.w.add_hook('close', lambda w: common.view.lower_page_transient('dialogs'))
            common.view.raise_page_transient('dialogs')
            common.view.dialogs.select(name)

        cvbox = self.w.get_content_area()
        self.cvbox = cvbox
        tw = Widgets.TextView(editable=False)
        tw.set_font("Sans Bold", 14)
        #tw.set_cursor_visible(False)
        #tw.resize(425, -1)
        tw.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        tw.set_left_margin(4)
        tw.set_right_margin(4)
        txtbuf = tw.get_buffer()
        enditer = txtbuf.get_end_iter()
        txtbuf.insert(enditer, title)
        self.tw = tw
        tw.show()

        self.icon = Gtk.Image()
        self.icon.set_from_file(iconfile)
        cvbox.pack_start(self.icon, False, False, 2)
        cvbox.pack_start(tw, False, False, 5)

        self.anim = GdkPixbuf.PixbufAnimation.new_from_file(iconfile)
        self.icon.set_from_animation(self.anim)
        self.icon.show_all()

    def popup(self, title, iconfile, soundfn, buttons, callfn, tag=None):
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

            unregister_dialog(self.tag)
            return callfn(val, button_vals)

        self._create_widget(title, iconfile, tuple(button_list),
                            callback)
        self.tag = tag
        register_dialog(tag, self)

        self.w.show()
        #self.timeraction(soundfn)
        self.timertask = GObject.timeout_add(self.interval,
                                             self.timeraction,
                                             soundfn)

    def close(self, widget):
        #self.w.hide()
        widget.destroy()
        self.w = None
        if self.timertask:
            try:
                GObject.source_remove(self.timertask)
            except Exception:
                pass
        self.timertask = None

    def timeraction(self, soundfn):
        if self.w:
            if soundfn != None:
                # play sound
                soundfn()

                # Schedule next sound event
                self.timertask = GObject.timeout_add(self.interval,
                                                     self.timeraction,
                                                     soundfn)
        else:
            self.timertask = None

class UserInput(Confirmation):

    def __init__(self, title='OBS UserInput', logger=None, soundfn=None):
        super(UserInput, self).__init__(title=title, logger=logger,
                                        soundfn=soundfn)

    def popup(self, title, iconfile, soundfn, itemlist, callfn, tag=None):
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

            unregister_dialog(self.tag)
            self.close(w)
            return callfn(val, button_vals, d)

        self._create_widget(title, iconfile, tuple(button_list),
                            callback)

        tbl = Gtk.Table(rows=len(itemlist), columns=2)
        tbl.set_row_spacings(2)
        tbl.set_col_spacings(2)

        row = 0
        for name, val in itemlist:
            lbl = Gtk.Label(name)
            lbl.set_alignment(1.0, 0.5)
            ent = Gtk.Entry()
            val_s = str(val)
            ent.set_text(val_s)
            resDict[name] = ent

            tbl.attach(lbl, 0, 1, row, row+1, xoptions=Gtk.AttachOptions.FILL)
            tbl.attach(ent, 1, 2, row, row+1,
                       xoptions=Gtk.AttachOptions.EXPAND|Gtk.AttachOptions.FILL)
            row += 1

        tbl.show_all()
        self.cvbox.pack_start(tbl, False, True, 2)

        self.tag = tag
        register_dialog(tag, self)

        self.w.show()
        #self.timeraction(soundfn)
        self.timertask = GObject.timeout_add(self.interval,
                                             self.timeraction,
                                             soundfn)


class Timer(Confirmation):

    def __init__(self, title='OBS Timer', logger=None, soundfn=None):
        super(Timer, self).__init__(title=title, logger=logger,
                                    soundfn=soundfn)
        # override time interval to 1 sec
        self.interval = 1000
        self.soundfn = soundfn
        self.timer = None
        self.timertask = None

        self.fmtstr = '<span foreground="#008800" background="#F7F7F7" font="Sans Bold 120">%s</span>'

        # rgb triplets we use
        ## self.green = Gdk.Color(0.0, 0.5, 0.0)
        ## self.white = Gdk.Color(1.0, 1.0, 1.0)

    def redraw(self):
        s = self.timestr.rjust(5)
        self.area.set_markup(self.fmtstr % (s))

    def popup(self, title, iconfile, soundfn, timer, callfn, tag=None):
        time_sec = timer.duration
        self.soundfn = soundfn
        button_vals = [0]
        # NOTE: numbers here are INDEXES into self.button_vals, not values!
        button_list = [['Close', 0]]

        def callback(w, rsp):
            self.close(w)
            if rsp < 0:
                val = None
            else:
                val = rsp

            unregister_dialog(self.tag)
            return callfn(val, button_vals)

        self._create_widget(title, iconfile, tuple(button_list),
                            callback)

        val = float(time_sec)
        self.duration = val
        self.timestr = str(int(val)).rjust(5)
        timer.data.dialog = self

        self.area = Gtk.Label()
        #self.area.modify_bg(Gtk.StateType.NORMAL, self.white)
        #self.area.modify_fg(Gtk.StateType.NORMAL, self.green)
        self.cvbox.pack_start(self.area, True, True, 2)
        self.area.show()

        self.pbar = Gtk.ProgressBar()
        self.pbar.set_fraction(0.0)
        self.pbar.set_text("0%")
        self.cvbox.pack_start(self.pbar, False, True, 2)
        self.pbar.show()

        self.tag = tag
        register_dialog(tag, self)

        self.w.show()
        # start a second-by-second timer to update the GUIs with the
        # associated timer's value
        self._timer_tick(timer)
        self.redraw()

    def update_timer(self, secs):
        diff = max(0, int(round(secs)))
        #self.logger.debug("timer: %d sec" % diff)
        self.timestr = str(diff).rjust(5)
        if self.w:
            self.redraw()
        if diff > 0:
            frac = 1.0 - diff/self.duration
            self.pbar.set_fraction(frac)
            self.pbar.set_text("%d%%" % int(frac*100))
        else:
            self.timertask = None
            self.pbar.set_fraction(1.0)
            self.pbar.set_text("100%")
            self.timerstr = '0'
            self.redraw()

            # Play sound
            self.soundfn()

            self.close(self.w)

    def _timer_tick(self, timer):
        secs = timer.time_left()
        try:
            timer.data.obsinfo.update_timer(secs)
        except Exception as e:
            pass
        try:
            timer.data.dialog.update_timer(secs)
        except Exception:
            pass

        if secs > 0:
            GObject.timeout_add(1000, self._timer_tick, timer)


class ComboBox(Confirmation):

    def __init__(self, title='OBS ComboBox', logger=None, soundfn=None):
        super(ComboBox, self).__init__(title=title, logger=logger,
                                        soundfn=soundfn)
        self.selectedValue = None

    def popup(self, title, iconfile, soundfn, itemlist, callfn, tag=None):
        button_vals = [1, 0]
        # NOTE: numbers here are INDEXES into self.button_vals, not values!
        button_list = [['OK', 0], ['Cancel', 1]]

        def callback(w, rsp):
            if rsp < 0:
                val = None
            else:
                val = rsp

            d = {'selected': self.selectedValue}

            unregister_dialog(self.tag)
            self.close(w)
            return callfn(val, button_vals, d)

        self._create_widget(title, iconfile, tuple(button_list),
                            callback)

        combobox = Gtk.ComboBoxText()

        for item in itemlist:
            combobox.append_text(item)
        combobox.connect('changed', self.changed_cb)
        combobox.set_active(0)
        self.selectedValue = itemlist[0]
        if len(itemlist) > 20:
            combobox.set_wrap_width(int(len(itemlist)/20))

        combobox.show()
        self.cvbox.pack_start(combobox, False, True, 2)

        self.tag = tag
        register_dialog(tag, self)

        self.w.show()
        #self.timeraction(soundfn)
        self.timertask = GObject.timeout_add(self.interval,
                                             self.timeraction,
                                             soundfn)

    def changed_cb(self, combobox):
        model = combobox.get_model()
        index = combobox.get_active()
        if index:
            self.selectedValue = model[index][0]
        return

#END
