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
        self.filew.add_callback("close", self.close)
        self.filew.add_callback("activated", self.file_ok_sel)

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
        w.delete()


class MyDialog(Widgets.Dialog):
    def __init__(self, title=None, flags=None, buttons=None,
                 callback=None):

        super().__init__(title=title, flags=flags, buttons=buttons)
        if callback:
            self.add_callback("activated", callback)


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
        self._search_widget = Widgets.TextEntry()
        if self.what:
            self._search_widget.set_text(self.what)
        self.cvbox.add_widget(self._search_widget, stretch=0)

        lbl = Widgets.Label('Replacement string:')
        self.cvbox.add_widget(lbl, stretch=0)
        self._replace_widget = Widgets.TextEntry()
        if self.replacement:
            self._replace_widget.set_text(self.replacement)
        self.cvbox.add_widget(self._replace_widget, stretch=0)

        self._case_sensitive = Widgets.CheckBox("Case sensitive")
        self._case_sensitive.set_state(True)
        self._case_sensitive.set_enabled(False)
        self.cvbox.add_widget(self._case_sensitive, stretch=0)

        self._reverse = Widgets.CheckBox("Reverse")
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
        widget.delete()
        self.w = None


class Confirmation(object):

    def __init__(self, title='OBS Confirmation',
                 logger=None, soundfn=None, timefreq=5):
        self.title = title
        self.logger = logger

        self.soundfn = soundfn
        # repeating sound timer (a ginga timer); interval is in seconds
        self.timer = None
        self.interval = timefreq

    def _create_widget(self, title, iconfile, buttons, callback):
        global dialog_count

        settings = common.view.get_settings()
        embed_dialogs = settings.get('embed_dialogs', False)

        if not embed_dialogs:
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
            self.w.add_callback('close', lambda w: common.view.lower_page_transient('dialogs'))
            common.view.raise_page_transient('dialogs')
            common.view.dialogs.select(name)

        cvbox = self.w.get_content_area()
        self.cvbox = cvbox
        cvbox.set_spacing(4)

        # Optional attention icon; degrade gracefully if it can't be loaded.
        self.icon = None
        if iconfile:
            try:
                icon = Widgets.Image()
                icon.load_file(iconfile)
                cvbox.add_widget(icon, stretch=0)
                self.icon = icon
            except Exception as e:
                if self.logger is not None:
                    self.logger.warning("Could not load icon '%s': %s" % (
                        iconfile, str(e)))

        # Message text
        lbl = Widgets.Label(title)
        try:
            lbl.set_font('sans bold', 14)
        except Exception:
            pass
        cvbox.add_widget(lbl, stretch=0)
        self.tw = lbl

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
        self._start_repeating_sound(soundfn)

    def _start_repeating_sound(self, soundfn):
        self.soundfn = soundfn
        if soundfn is None:
            return
        self.timer = common.view.make_timer()
        self.timer.add_callback('expired', self._sound_tick)
        self.timer.start(self.interval)

    def _sound_tick(self, timer):
        if self.w is not None and self.soundfn is not None:
            # play sound and re-arm
            self.soundfn()
            timer.start(self.interval)

    def close(self, widget):
        #self.w.hide()
        if widget is not None:
            widget.delete()
        self.w = None
        if self.timer is not None:
            try:
                self.timer.stop()
            except Exception:
                pass
            self.timer = None


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
                d[key] = ent.get_text()

            unregister_dialog(self.tag)
            self.close(w)
            return callfn(val, button_vals, d)

        self._create_widget(title, iconfile, tuple(button_list),
                            callback)

        grid = Widgets.GridBox()
        grid.set_row_spacing(2)
        grid.set_column_spacing(2)

        for row, (name, val) in enumerate(itemlist):
            lbl = Widgets.Label(name)
            try:
                lbl.set_halign('right')
            except Exception:
                pass
            ent = Widgets.TextEntry()
            ent.set_text(str(val))
            resDict[name] = ent

            grid.add_widget(lbl, row, 0, stretch=0)
            grid.add_widget(ent, row, 1, stretch=1)

        self.cvbox.add_widget(grid, stretch=0)

        self.tag = tag
        register_dialog(tag, self)

        self.w.show()
        self._start_repeating_sound(soundfn)


class Timer(Confirmation):

    def __init__(self, title='OBS Timer', logger=None, soundfn=None):
        super(Timer, self).__init__(title=title, logger=logger,
                                    soundfn=soundfn)
        # override time interval to 1 sec
        self.interval = 1
        self.soundfn = soundfn
        # ginga timer used for the per-second display tick
        self.timer = None

    def redraw(self):
        if self.w is not None:
            self.area.set_text(self.timestr.rjust(5))

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

        self.area = Widgets.Label(self.timestr)
        try:
            self.area.set_font('sans bold', 48)
        except Exception:
            pass
        self.cvbox.add_widget(self.area, stretch=1)

        self.pbar = Widgets.ProgressBar()
        self.pbar.set_value(0.0)
        self.cvbox.add_widget(self.pbar, stretch=0)

        self.tag = tag
        register_dialog(tag, self)

        self.w.show()
        # start a second-by-second timer to update the GUI with the
        # associated countdown timer's value
        self._timer_tick(timer)
        self.redraw()

    def update_timer(self, secs):
        diff = max(0, int(round(secs)))
        #self.logger.debug("timer: %d sec" % diff)
        self.timestr = str(diff).rjust(5)
        if self.w:
            self.redraw()
        if diff > 0:
            frac = 1.0 - diff / self.duration
            self.pbar.set_value(frac)
        else:
            self.pbar.set_value(1.0)
            self.timestr = '0'
            self.redraw()

            # Play sound
            if self.soundfn is not None:
                self.soundfn()

            self.close(self.w)

    def _timer_tick(self, timer):
        secs = timer.time_left()
        try:
            timer.data.obsinfo.update_timer(secs)
        except Exception:
            pass
        try:
            timer.data.dialog.update_timer(secs)
        except Exception:
            pass

        if secs > 0 and self.w is not None:
            if self.timer is None:
                self.timer = common.view.make_timer()
                self.timer.add_callback('expired',
                                        lambda t: self._timer_tick(timer))
            self.timer.start(1.0)


class ComboBox(Confirmation):

    def __init__(self, title='OBS ComboBox', logger=None, soundfn=None):
        super(ComboBox, self).__init__(title=title, logger=logger,
                                        soundfn=soundfn)
        self.selectedValue = None
        self.itemlist = []

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

        self.itemlist = list(itemlist)
        combobox = Widgets.ComboBox()
        for item in itemlist:
            combobox.append_text(item)
        combobox.add_callback('activated', self.changed_cb)
        combobox.set_index(0)
        self.selectedValue = itemlist[0]

        self.cvbox.add_widget(combobox, stretch=0)

        self.tag = tag
        register_dialog(tag, self)

        self.w.show()
        self._start_repeating_sound(soundfn)

    def changed_cb(self, widget, index):
        if 0 <= index < len(self.itemlist):
            self.selectedValue = self.itemlist[index]

#END
