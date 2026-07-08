#
# E. Jeschke
#

from ginga.misc import Bunch
from ginga.gw import Widgets

from . import common
from . import Page

class OptionsPage(Page.ButtonPage):

    def __init__(self, frame, name, title):

        super(OptionsPage, self).__init__(frame, name, title)

        scrolled_window = Widgets.ScrollArea()

        vbox = Widgets.VBox()
        vbox.set_spacing(2)
        self.w = Bunch.Bunch()

        settings = common.view.get_settings()

        def _mk_fn(key):
            return lambda w, tf: self.toggle_setting(tf, key)

        for title, key in (("Audible Errors", 'audible_errors'),
                           ("Suppress 'Confirm Execute' popups",
                            'suppress_confirm_exec'),
                           ("Embed dialogs", 'embed_dialogs'),
                           ("Wrap Lines in OPE Pages", 'wrap_lines'),
                           ("Number Lines in OPE Pages", 'show_line_numbers'),
                           ("Clear info on Config", 'clear_obs_info')):
            w = Widgets.CheckBox(title)
            self.w[key] = w
            w.set_state(settings[key])
            w.add_callback("activated", _mk_fn(key))
            vbox.add_widget(w, stretch=0)

        # spacer
        vbox.add_widget(Widgets.Label(''), stretch=1)

        lbl = Widgets.Label('Settings:')
        ent = Widgets.TextEntry()
        ent.set_text('')
        self.w.settingname = ent
        btn1 = Widgets.Button('Load')
        btn1.add_callback('activated', lambda w: self.load_settings())
        btn2 = Widgets.Button('Nop')
        self.w.btn_save = btn2
        btn2.add_callback('activated', lambda w: self.save_settings())

        hbox = Widgets.HBox()
        hbox.add_widget(lbl, stretch=0)
        hbox.add_widget(ent, stretch=0)
        hbox.add_widget(btn1, stretch=0)
        vbox.add_widget(hbox, stretch=0)
        hbox = Widgets.HBox()
        hbox.add_widget(btn2, stretch=0)
        vbox.add_widget(hbox, stretch=0)

        scrolled_window.set_widget(vbox)

        self.content.add_widget(scrolled_window, stretch=1)

    def toggle_setting(self, tf, key):
        # the checkbox 'activated' callback passes the new boolean state
        settings = common.view.get_settings()
        settings.set(**{key: bool(tf)})

    def load_settings(self):
        # turn name into something reasonable without spaces
        iname = self.w.settingname.get_text()
        name = iname.strip().replace(' ', '_')
        if len(name) == 0:
            return

        # create new settings if they don't exist and copy default
        # settings into them
        default = common.view.prefs.get_settings('default')
        settings = common.view.prefs.create_category(name)
        default.copy_settings(settings)

        # load any saved settings
        common.view.settings = settings
        settings.load(onError='warn')

        # update GUI
        d = settings.get_dict()
        for key, value in d.items():
            if isinstance(value, bool) and key in self.w:
                self.w[key].set_state(value)

        self.w.btn_save.set_text("Save '%s'" % (iname))

        return settings

    def save_settings(self):
        common.view.settings.save()
