#
# E. Jeschke
#
import os
import threading
from collections import OrderedDict

from ginga.misc import Bunch, Callback
from ginga.gw import Widgets

from . import common

# constants
LEFT  = 'left'
RIGHT = 'right'


class Page(Callback.Callbacks):

    def __init__(self, frame, name, title):
        Callback.Callbacks.__init__(self)
        #super().__init__()

        self.frame = frame
        self.name = name
        self.title = title

        self.closed = False

        # every page has a lock
        self.lock = threading.RLock()

        self.enable_callback('close')

    def close(self):
        self.make_callback('close')

        # parent attribute is assigned by parent
        self.parent.delpage(self.name)

        self.closed = True

    def setLabel(self, name):
        # tablbl attribute is added by parent workspace
        # NOTE: this doesn't really change the name of the page, as known
        # by the parent, just the appearance of the tab
        #self.widget.set_title(name)
        pass

    def add_hook(self, name, cbfn, args=None, kwdargs=None):
        # for backward compatibility with "hooks" system
        if args is None:
            args = []
        if kwdargs is None:
            kwdargs = {}
        self.add_callback(name, cbfn, *args, **kwdargs)


class ButtonPage(Page):

    def __init__(self, frame, name, title):
        Page.__init__(self, frame, name, title)
        #super().__init__(frame, name, title)

        self.add_menubar()

        # content area (no margin -- content sits flush to the frame; pages
        # that want an inset add their own)
        self.content = Widgets.VBox()
        self.content.set_border_width(0)
        self.content.set_spacing(0)
        frame.add_widget(self.content, stretch=1)

        # bottom buttons
        self.btnframe = Widgets.HBox()

        btns = Widgets.ButtonBox()
        btns.set_spacing(5)
        self.leftbtns = btns

        self.btnframe.add_widget(self.leftbtns, stretch=0)

        # stretcher
        self.btnframe.add_widget(Widgets.Label(''), stretch=1)

        btns = Widgets.ButtonBox()
        btns.set_spacing(5)
        self.rightbtns = btns

        self.btnframe.add_widget(self.rightbtns, stretch=0)

        frame.add_widget(self.btnframe, stretch=0)

    def _get_side(self, side):
        if side == LEFT:
            return self.leftbtns
        elif side == RIGHT:
            return self.rightbtns
        return None

    def add_close(self, side=RIGHT):
        self.btn_close = Widgets.Button("Close")
        self.btn_close.add_callback("activated", lambda w: self.close())
        w = self._get_side(side)
        w.add_widget(self.btn_close, stretch=0)

    def add_menubar(self):
        self.menubar = Widgets.Menubar()
        self._menus = {}
        self.frame.add_widget(self.menubar, stretch=0)
        return self.menubar

    def add_pulldownmenu(self, name):
        if not self.menubar:
            self.add_menubar()
        try:
            # Look for existing menu with this name
            menu = self._menus[name]
            return menu
        except KeyError:
            pass
        # No such menu, so go ahead and create it
        menu = self.menubar.add_name(name)
        self._menus[name] = menu
        return menu

    def add_menu(self, side=RIGHT):
        self.btn_menu = Widgets.Button("Menu")
        self.menu = Widgets.Menu()
        self.btn_menu.add_callback("activated", self.popup_menu)
        w = self._get_side(side)
        w.add_widget(self.btn_menu, stretch=0)

    def popup_menu(self, w):
        self.menu.popup(widget=self.btn_menu)
        return True


class CommandPage(ButtonPage):
    """Mixin class adding methods for kill, cancel, pause, etc.
    """

    def __init__(self, frame, name, title):
        self.paused = False
        # *** subclass should define self.tm_queueName ***

        ButtonPage.__init__(self, frame, name, title)
        #super().__init__(frame, name, title)

    def cancel(self):
        #controller = self.parent.get_controller()
        controller = common.controller
        controller.tm_cancel(self.tm_queueName)
        self.reset_pause()

    def pause(self):
        self.btn_pause.set_text("Resume")
        self.paused = True
        #controller = self.parent.get_controller()
        controller = common.controller
        controller.tm_pause(self.tm_queueName)

    def resume(self):
        self.reset_pause()
        #controller = self.parent.get_controller()
        controller = common.controller
        controller.tm_resume(self.tm_queueName)

    def toggle_pause(self, w):
        #print("toggle pause!")
        common.controller.playSound(common.sound.pause_toggle)
        if self.paused:
            self.resume()
        else:
            self.pause()

        return True

    def reset_pause(self):
        self.btn_pause.set_text("Pause")
        self.paused = False

    def reset(self):
        self.reset_pause()


class TablePage(ButtonPage):
    """Subclass for pages primarily showing a table."""

    def __init__(self, frame, name, title):

        super().__init__(frame, name, title)

        self.table = Widgets.TreeView(auto_expand=True, sortable=True,
                                      use_alt_row_color=False)

        self.sort_hdr = None
        self.sort_kwd = None

        # columns to be shown in the table
        self.rpt_columns = []
        self.col_widths = []
        self.column_info = []
        self.rpt_dict = OrderedDict({})
        # For row coloring
        self.colortbl = {}

        self.content.add_widget(self.table, stretch=1)

    def set_column_info(self, spec_lst, sort_idx=0, nesting=1):
        self.column_info = spec_lst
        self.sort_kwd = spec_lst[0]['col_key']
        self.sort_hdr = spec_lst[0]['col_hdr']
        self.rpt_columns = []
        self.col_widths = []
        for dct in spec_lst:
            self.rpt_columns.append((dct['col_hdr'], dct['col_key']))
            self.col_widths.append(dct.get('col_width', None))

        tv = self.table
        tv.setup_table(self.rpt_columns, nesting, self.sort_kwd)

        # set any specified column widths
        tv.set_optimal_column_widths()
        for i, wd in enumerate(self.col_widths):
            if wd is None:
                continue
            tv.set_column_width(i, wd)

    def update_internal(self, dct):
        self.rpt_dict.update(dct)

    def refresh(self, dct, expand_new=False):
        self.table.update_tree(self.rpt_dict, expand_new=expand_new)

    def color_row(self, key, fg='black', bg=None):
        self.colortbl[key] = dict(fg=fg, bg=bg)
        #self.table.set_path_background()
        self.table.highlight_path(path, True, font_color=fg)

    def clear(self):
        self.colortbl = dict()
        self.rpt_dict = OrderedDict({})
        self.table.clear()


class TextPage(Page):
    """Mixin class adding methods for text manipulation.
    """

    ## def __init__(self, frame, name, title):
    ##     super().__init__(frame, name, title)

    def save(self, dirpath=None, filename=None):
        # If we have a filepath associated with this buffer, try to
        # use it, otherwise revert to a save_as()
        if hasattr(self, 'filepath') and self.filepath is not None:
            return self._savefile(self.filepath)

        return self.save_as(self, dirpath=dirpath,
                            filename=filename)


    def _get_save_directory(self):
        if hasattr(self, 'filepath') and self.filepath:
            # Use directory of current file, if one exists
            dirpath, xx = os.path.split(self.filepath)
        else:
            # default directory for saving, if none provided
            dirpath = os.path.join(os.environ['HOME'], 'Procedure')

        return dirpath

    def save_as(self, dirpath=None, filename=None):
        def _save(filepath):
            if hasattr(self, 'filepath') and self.filepath is None:
                self.filepath = filepath
            return self._savefile(filepath, self.tw.get_text())

        if dirpath is None:
            dirpath = self._get_save_directory()

        common.view.popup_save("Save buffer as", _save,
                               dirpath, filename=filename)

    def save_selection_as(self, dirpath=None, filename=None):
        bounds = self.tw.get_selection_bounds()
        if bounds is None:
            return common.view.popup_error("Please make a selection first!")
        first, last = bounds
        text = self.tw.get_text_range(first, last)

        def _save(filepath):
            return self._savefile(filepath, text)

        if dirpath is None:
            dirpath = self._get_save_directory()

        common.view.popup_save("Save selection as", _save,
                               dirpath, filename=filename)

    def _savefile(self, filepath, buf):
        """Save buffer to (filepath).  If the file exists, confirm whether
        to overwrite it.
        """
        def _save(res):
            if res != 'yes':
                return

            try:
                with open(filepath, 'w') as out_f:
                    out_f.write(buf)
                #self.statusMsg("{} saved.".format(filepath))

            except Exception as e:
                return common.view.popup_error("Cannot write '%s': %s" % (
                        filepath, str(e)))

        if os.path.exists(filepath):
            common.view.popup_confirm("Confirm overwrite",
                                      "File '%s' exists.\nOK to Overwrite ?" % (
                filepath), _save)
        else:
            _save('yes')

    def select_all(self):
        common.select_all(self.tw)

    def select_clear(self):
        common.clear_selection(self.tw)

    def get_end_lineno(self):
        return common.get_end_lineno(self.tw)

    def scroll_to_lineno(self, lineno):
        return common.scroll_to_lineno(self.tw, lineno)

    def scroll_to_end(self):
        return common.scroll_to_end(self.tw)

    def focus_in(self, *args):
        return common.focus_in(self.tw)

#END
