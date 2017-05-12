# 
# Eric Jeschke (eric@naoj.org)
#

from __future__ import absolute_import

from gi.repository import Gtk

from ginga.misc import Bunch

from . import common
from . import Page

class OptionsPage(Page.ButtonPage):

    def __init__(self, frame, name, title):

        super(OptionsPage, self).__init__(frame, name, title)

        scrolled_window = Gtk.ScrolledWindow()
        scrolled_window.set_border_width(2)

        scrolled_window.set_policy(Gtk.PolicyType.AUTOMATIC,
                                   Gtk.PolicyType.AUTOMATIC)

        vbox = Gtk.VBox(spacing=2)
        self.w = Bunch.Bunch()
        
        settings = common.view.get_settings()

        lbl = Gtk.Label('Settings:')
        ent = Gtk.Entry()
        ent.set_text('')
        self.w.settingname = ent
        btn1 = Gtk.Button('Load')
        btn1.connect('clicked', lambda w: self.load_settings())
        btn2 = Gtk.Button('Nop')
        self.w.btn_save = btn2
        btn2.connect('clicked', lambda w: self.save_settings())

        hbox = Gtk.HBox()
        hbox.pack_start(lbl, False, False, 0)
        hbox.pack_start(ent, False, False, 0)
        hbox.pack_start(btn1, False, False, 0)
        vbox.pack_start(hbox, False, True, 0)
        hbox = Gtk.HBox()
        hbox.pack_start(btn2, False, False, 0)
        vbox.pack_start(hbox, False, True, 0)

        # spacer
        lbl = Gtk.Label('')
        vbox.pack_start(lbl, False, False, 0)
        
        def _mk_fn(key):
            return lambda w: self.toggle_setting(w, key)
        
        for title, key in (("Audible Errors", 'audible_errors'),
                           ("Suppress 'Confirm Execute' popups",
                            'suppress_confirm_exec'),
                           ("Embed dialogs", 'embed_dialogs'),
                           ("Wrap Lines in OPE Pages", 'wrap_lines'),
                           ("Number Lines in OPE Pages", 'show_line_numbers'),
                           ("Clear info on Config", 'clear_obs_info')):
            w = Gtk.CheckButton(title)
            self.w[key] = w
            w.set_active(settings[key])
            w.connect("toggled", _mk_fn(key))
            vbox.pack_start(w, False, True, 0)

        scrolled_window.add_with_viewport(vbox)

        frame.pack_start(scrolled_window, True, True, 0)
        scrolled_window.show_all()

    def toggle_setting(self, widget, key):
        settings = common.view.get_settings()
        if widget.get_active():
            settings[key] = True
        else:
            settings[key] = False

    def load_settings(self):
        # turn name into something reasonable without spaces
        iname = self.w.settingname.get_text()
        name = iname.strip().replace(' ', '_')
        if len(name) == 0:
            return

        # create new settings if they don't exist and copy default
        # settings into them
        default = common.view.prefs.getSettings('default')
        settings = common.view.prefs.createCategory(name)
        default.copySettings(settings)

        # load any saved settings
        common.view.settings = settings
        settings.load(onError='warn')
        
        # update GUI
        d = settings.getDict()
        for key, value in d.items():
            if isinstance(value, bool) and key in self.w:
                self.w[key].set_active(value)

        self.w.btn_save.set_label("Save '%s'" % (iname))

        return settings

    def save_settings(self):
        common.view.settings.save()

        
#END
