#
# E. Jeschke
#
import threading
import yaml
import functools
import decimal

from gi.repository import Gtk

from ginga.gw import Widgets

from ginga.misc import Bunch
from ginga.gtk3w import GtkHelp

from . import common
from . import Page
from . import CommandObject

# Default width of the main launcher buttons
default_width = 150

class LauncherError(Exception):
    pass

class Launcher(object):

    def __init__(self, llist, name, title, execfn):
        self.llist = llist
        self.params = Bunch.Bunch()
        self.paramList = []
        self.execfn = execfn

        self.btn_exec = Widgets.Button(title)
        self.btn_exec.get_widget().set_size_request(default_width, -1)
        self.btn_exec.add_callback("activated", lambda w: self.execute())

        self.llist.table.add_widget(self.btn_exec, self.llist.row, 0)


    def addParam(self, name):
        self.paramList.append(name)
        key = functools.cmp_to_key(lambda x, y: len(y) - len(x))
        # sort parameter list so longer strings are substituted first
        self.paramList.sort(key=key)

    def add_cmd(self, cmdstr):
        self.cmdstr = cmdstr

    def add_break(self):
        self.llist.row += 2
        self.llist.col = 1
        self.llist.table.resize_grid(self.llist.row+1, self.llist.max_col+1)

    def bump_col(self):
        self.llist.col += 1
        self.llist.max_col = max(self.llist.col, self.llist.max_col)
        self.llist.table.resize_grid(self.llist.row+1, self.llist.max_col+1)

    def add_input(self, name, width, defVal, label):

        lbl = Widgets.Label(label)
        self.llist.table.add_widget(lbl, self.llist.row-1, self.llist.col)
        field = Widgets.TextEntry()
        field.set_length(width)
        field.set_text(str(defVal))
        self.llist.table.add_widget(field, self.llist.row, self.llist.col)
        self.bump_col()

        name = name.lower()
        self.params[name] = Bunch.Bunch(widget=field,
                                        get_fn=self.get_entry)
        self.addParam(name)

    def add_checkbox(self, name, checkbox_label, checkbox_dict, width, height,
                     label):

        lbl = Widgets.Label(label)
        self.llist.table.add_widget(lbl, self.llist.row-1, self.llist.col)

        checkbox = Widgets.CheckBox(checkbox_label)
        checkbox.resize(width, height)

        self.llist.table.add_widget(checkbox, self.llist.row, self.llist.col)

        self.bump_col()

        name = name.lower()
        self.params[name] = Bunch.Bunch(widget=checkbox,
                                        get_fn=self.get_checkbox,
                                        dict=checkbox_dict)
        self.addParam(name)

    def add_toggle(self, name, toggle_label, toggle_dict, width, height, label):

        lbl = Widgets.Label(label)
        self.llist.table.add_widget(lbl, self.llist.row-1, self.llist.col)

        toggle = Widgets.ToggleButton(toggle_label)
        toggle.resize(width, height)

        self.llist.table.add_widget(toggle, self.llist.row, self.llist.col)
        self.bump_col()

        name = name.lower()
        self.params[name] = Bunch.Bunch(widget=toggle,
                                        get_fn=self.get_toggle,
                                        dict=toggle_dict)
        self.addParam(name)

    def add_switch(self, name, switch_dict, width, height, label):

        lbl = Widgets.Label(label)
        self.llist.table.add_widget(lbl, self.llist.row-1, self.llist.col)

        #switch = Gtk.Switch()
        switch = Widgets.ToggleButton("[---]")
        switch.set_state(False)
        switch.resize(width, height)

        self.llist.table.add_widget(switch, self.llist.row, self.llist.col)
        self.bump_col()

        name = name.lower()
        self.params[name] = Bunch.Bunch(widget=switch,
                                        get_fn=self.get_switch,
                                        dict=switch_dict)
        self.addParam(name)


    def add_scale(self, name, value, lower, upper, step, width, height, label):

        lbl = Widgets.Label(label)
        self.llist.table.add_widget(lbl, self.llist.row-1, self.llist.col)

        scale = Widgets.Slider(orientation='horizontal', dtype=type(value))
        scale.set_limits(lower, upper, incr_value=step)
        scale.set_value(value)
        scale.resize(width, height)

        self.llist.table.add_widget(scale, self.llist.row, self.llist.col)

        self.bump_col()

        name = name.lower()
        self.params[name] = Bunch.Bunch(widget=scale,
                                        get_fn=self.get_scale)
        self.addParam(name)

    def add_spin(self, name, value, lower, upper, step, width, height, label):

        lbl = Widgets.Label(label)
        self.llist.table.add_widget(lbl, self.llist.row-1, self.llist.col)

        d = decimal.Decimal(str(step))
        d = d.as_tuple().exponent * -1

        spinbutton = Widgets.SpinBox(dtype=type(value))
        spinbutton.set_limits(lower, upper, incr_value=step)
        spinbutton.set_value(value)
        spinbutton.set_decimals(d)
        spinbutton.resize(width, height)

        self.llist.table.add_widget(spinbutton, self.llist.row, self.llist.col)
        self.bump_col()

        name = name.lower()
        self.params[name] = Bunch.Bunch(widget=spinbutton,
                                        get_fn=self.get_spin)
        self.addParam(name)

    def add_combobox(self, name, combobox_list,  width, height, label):

        lbl = Widgets.Label(label)
        self.llist.table.add_widget(lbl, self.llist.row-1, self.llist.col)

        combobox = Widgets.ComboBox(editable=True)
        for cl in combobox_list:
            combobox.append_text(str(cl))
        combobox.resize(width, height)

        self.llist.table.add_widget(combobox, self.llist.row, self.llist.col)
        self.bump_col()

        name = name.lower()
        self.params[name] = Bunch.Bunch(widget=combobox,
                                        get_fn=self.get_combobox)
        self.addParam(name)

    def add_list(self, name, optionList, label):

        lbl = Widgets.Label(label)
        self.llist.table.add_widget(lbl, self.llist.row-1, self.llist.col)

        combobox = Widgets.ComboBox()
        options = []
        for opt, val in optionList:
            options.append(val)
            combobox.append_text(opt)
        combobox.set_index(0)
        self.llist.table.add_widget(combobox, self.llist.row, self.llist.col)
        self.bump_col()

        name = name.lower()
        self.params[name] = Bunch.Bunch(widget=combobox,
                                        get_fn=self.get_list,
                                        options=options)
        self.addParam(name)

    def add_radio(self, name, optionList, label):

        lbl = Widgets.Label(label)
        self.llist.table.add_widget(lbl, self.llist.row-1, self.llist.col)

        group = None
        options = []
        for opt, val in optionList:
            btn = Widgets.RadioButton(opt, group=group)
            if group is None:
                group = btn
            self.llist.table.add_widget(btn, self.llist.row, self.llist.col)
            options.append((btn, val))
            self.bump_col()

        name = name.lower()
        self.params[name] = Bunch.Bunch(get_fn=self.get_radio,
                                        options=options)
        self.addParam(name)

    def add_dial_select(self, name, optionList, width, height, label):

        lbl = Widgets.Label(label)
        self.llist.table.add_widget(lbl, self.llist.row-1, self.llist.col)

        dial = Widgets.Dial()
        dial.resize(width, height)
        self.llist.table.add_widget(dial, self.llist.row, self.llist.col)
        self.bump_col()
        dial.show()

        # TODO: do some calculation to determine the best angle start and
        # separation
        ang_sep_deg = 220.0 / len(optionList)
        ang_deg = 220.0
        setup = []
        for lbl, val in optionList:
            setup.append((lbl, val, ang_deg))
            ang_deg -= ang_sep_deg

        dial.set_labels(setup)
        dial.label_style = 1
        dial.set_index(0)

        name = name.lower()
        self.params[name] = Bunch.Bunch(widget=dial, get_fn=self.get_dial)
        self.addParam(name)

    def add_dial_value(self, name, value, lower, upper, step, width, height,
                       label):

        lbl = Widgets.Label(label)
        self.llist.table.add_widget(lbl, self.llist.row-1, self.llist.col)

        dial = Widgets.Dial(dtype=type(value))
        dial.resize(width, height)
        self.llist.table.add_widget(dial, self.llist.row, self.llist.col)
        self.bump_col()
        dial.set_limits(lower, upper, incr_valuestep)
        dial.set_value(value)

        name = name.lower()
        self.params[name] = Bunch.Bunch(widget=dial, get_fn=self.get_dial)
        self.addParam(name)

    def get_combobox(self, bnch):

        value = bnch.widget.get_text()
        return value

    def get_checkbox(self, bnch):
        active =  bnch.widget.get_state()
        checkbox = bnch.dict.get(active)
        return checkbox

    def get_toggle(self, bnch):
        active =  bnch.widget.get_state()
        toggle = bnch.dict.get(active)
        return toggle

    def get_switch(self, bnch):
        active =  bnch.widget.get_state()
        switch = bnch.dict.get(active)
        return switch

    def get_spin(self, bnch):
        return bnch.widget.get_value()

    def get_scale(self, bnch):
        return bnch.widget.get_value()

    def get_entry(self, bnch):
        return bnch.widget.get_text()

    def get_list(self, bnch):
        index = bnch.widget.get_index()
        try:
            return bnch.options[index]
        except IndexError:
            return None

    def get_radio(self, bnch):
        for widget, val in bnch.options:
            if widget.get_state():
                return val
        return None

    def get_dial(self, bnch):
        return bnch.widget.get_value()

    def getcmd(self):
        cmdstr = self.cmdstr

        for var in self.paramList:
            dvar = '$%s' % var.upper()
            if dvar in cmdstr:
                bnch = self.params[var]
                val = str(bnch.get_fn(bnch))
                cmdstr = cmdstr.replace(dvar, val)

        return cmdstr

    def execute(self):
        cmdstr = self.getcmd()
        self.execfn(cmdstr, self)

    def show_state(self, state):
        if state == 'queued':
            state = 'normal'

        common.modify_bg(self.btn_exec,
                         common.launcher_colors[state])

    def reset(self):
        common.modify_bg(self.btn_exec,
                         common.launcher_colors['normal'])


class LauncherList(object):

    def __init__(self, frame, name, title, execfn):
        self.llist = []
        self.ldict = {}
        self.count = 0
        self.frame = frame
        self.execfn = execfn

        self.row = 1
        self.col = 1
        self.max_col = self.col
        self.btn_width = 20

        self.table = Widgets.GridBox(rows=2, columns=2)
        self.table.set_column_spacing(2)
        self.table.set_row_spacing(2)
        #self.table.set_name('launcher')

        frame.add_widget(self.table, stretch=0)

    def addSeparator(self):
        #separator = Gtk.HSeparator()
        separator = Widgets.Label("--------------------")
        self.table.add_widget(separator, self.row-1, 0)
        self.row += 1
        self.col = 1
        self.table.resize_grid(self.row+1, self.max_col+1)
        self.count += 1

    def addLauncher(self, name, title):
        self.count += 1

        launcher = Launcher(self, name, title, self.execfn)

        self.llist.append(launcher)
        self.ldict[name.lower()] = launcher

        return launcher

    def getLauncher(self, name):
        return self.ldict[name.lower()]

    def getLaunchers(self):
        return list(self.ldict.values())

    def addLauncherFromDef(self, ast):
        assert ast.tag == 'launcher'
        ast_label, ast_body = ast.items

        assert ast_label.tag == 'label'
        name = ast_label.items[0]

        launcher = self.addLauncher(name, name)

        for ast in ast_body.items:
            assert ast.tag in ('cmd', 'list', 'select', 'input', 'break')

            if ast.tag == 'break':
                launcher.add_break()

            elif ast.tag == 'input':
                var, width, val, lbl = ast.items
                width = int(width)
                launcher.add_input(var, width, val, lbl)

            elif ast.tag == 'select':
                var, ast_list, lbl = ast.items
                vallst = []

                if ast_list.tag == 'pure_val_list':
                    for item in ast_list.items:
                        vallst.append((item, item))

                elif ast_list.tag == 'subst_val_list':
                    for item_ast in ast_list.items:
                        assert item_ast.tag == 'value_pair'
                        lhs, rhs = item_ast.items
                        vallst.append((lhs, rhs))

                launcher.add_radio(var, vallst, lbl)

            elif ast.tag == 'list':
                var, ast_list, lbl = ast.items
                vallst = []

                if ast_list.tag == 'pure_val_list':
                    for item in ast_list.items:
                        vallst.append((item, item))

                elif ast_list.tag == 'subst_val_list':
                    for item_ast in ast_list.items:
                        assert item_ast.tag == 'value_pair'
                        lhs, rhs = item_ast.items
                        vallst.append((lhs, rhs))

                launcher.add_list(var, vallst, lbl)

            elif ast.tag == 'cmd':
                cmd, ast_params = ast.items
                cmd_l = [cmd.upper()]

                for item_ast in ast_params.items:
                    assert item_ast.tag == 'param_pair'
                    lhs, rhs = item_ast.items
                    cmd_l.append('%s=%s' % (lhs.upper(), rhs))

                cmdstr = ' '.join(cmd_l)

                launcher.add_cmd(cmdstr)

            else:
                pass

        launcher.add_break()

    def addFromDefs(self, ast):
        assert ast.tag == 'launchers'

        for ast in ast.items:
            if ast.tag == 'sep':
                self.addSeparator()

            else:
                self.addLauncherFromDef(ast)

    def _validate_spin_val(self, val):
        if not isinstance(val, (int, float)):
            val = 0
        return val

    def _validate_elt(self, elt):
        if isinstance(elt, list) and len(elt) == 2:
            return elt

        elt_s = str(elt)
        if not '=' in elt_s:
            return [elt_s, elt_s]
        else:
            return elt_s.split('=')

    def _validate_size(self, size, default_size):
        if len(size) == 0:
            wd, ht = default_size
        elif len(size) == 1:
            wd, ht = int(size[0]), default_size[1]
        else:
            wd, ht = int(size[0]), int(size[1])
        return wd, ht

    def addLauncherFromYAMLdef(self, d):
        assert isinstance(d, dict) and 'label' in d, \
               LauncherError("Malformed launcher def: expected key 'label': %s" % (
            str(d)))
        name = d['label']

        launcher = self.addLauncher(name, name)

        assert 'cmd' in d, \
               LauncherError("Malformed launcher def: expected key 'cmd': %s" % (
            str(d)))
        launcher.add_cmd(d['cmd'])

        if 'params' in d:
            for param in d['params']:
                if param == 'break':
                    launcher.add_break()
                    continue

                if isinstance(param, dict):
                    assert 'type' in param
                    p_type = param['type'].lower()

                    if p_type == 'input':
                        var = param['name']
                        width = param.get('width', 10)
                        val = param.get('value', '')
                        lbl = param.get('label', '')
                        width = int(width)

                        launcher.add_input(var, width, val, lbl)

                    elif p_type == 'select':
                        var = param['name']
                        vallst = [self._validate_elt(e)
                                  for e in param['values']]
                        lbl = param.get('label', '')

                        launcher.add_radio(var, vallst, lbl)

                    elif p_type == 'list':
                        var = param['name']
                        vallst = [self._validate_elt(e)
                                  for e in param['values']]
                        lbl = param.get('label', '')

                        launcher.add_list(var, vallst, lbl)

                elif isinstance(param, list):
                    var = param[0]
                    p_type = param[1].lower()

                    if p_type == 'input':
                        width = 10
                        val = ''
                        lbl = ''
                        if len(param) > 2:
                            width = param[2]
                            width = int(width)
                        if len(param) > 3:
                            val = param[3]
                        if len(param) > 4:
                            lbl = param[4]

                        launcher.add_input(var, width, val, lbl)

                    elif p_type == 'select':
                        vallst = [self._validate_elt(e) for e in param[2]]
                        lbl = param[3] if len(param) > 3 else ''

                        launcher.add_radio(var, vallst, lbl)

                    elif p_type == 'dial_select':
                        vallst = [self._validate_elt(e) for e in param[2]]
                        size = param[3] if len(param) > 3 else []
                        wd, ht = self._validate_size(size, (100, 100))
                        lbl = param[4] if len(param) > 4 else ''

                        launcher.add_dial_select(var, vallst, wd, ht, lbl)

                    elif p_type == 'list':
                        vallst = [self._validate_elt(e) for e in param[2]]
                        lbl = ''
                        if len(param) > 3:
                            lbl = param[3]

                        launcher.add_list(var, vallst, lbl)

                    elif p_type == 'spinbox':
                        value, lower, upper, step = [self._validate_spin_val(val)
                                                     for val in param[2]]
                        size = param[3] if len(param) > 3 else []
                        wd, ht = self._validate_size(size, (10, -1))
                        lbl = param[4] if len(param) > 4 else ''

                        launcher.add_spin(var, value, lower, upper, step,
                                          wd, ht, lbl)

                    elif p_type == 'slider':
                        value, lower, upper, step = [self._validate_spin_val(val)
                                                     for val in param[2]]
                        size = param[3] if len(param) > 3 else []
                        wd, ht = self._validate_size(size, (100, -1))
                        lbl = param[4] if len(param) > 4 else ''

                        launcher.add_scale(var, value, lower, upper, step,
                                           wd, ht, lbl)

                    elif p_type == 'dial_value':
                        value, lower, upper, step = [self._validate_spin_val(val)
                                                     for val in param[2]]
                        size = param[3] if len(param) > 3 else []
                        wd, ht = self._validate_size(size, (100, 100))
                        lbl = param[4] if len(param) > 4 else ''

                        launcher.add_dial_value(var, value, lower, upper, step,
                                                wd, ht, lbl)

                    elif p_type == 'switch':
                        swich_dict = param[2]
                        size = param[3] if len(param) > 3 else []
                        wd, ht = self._validate_size(size, (10, -1))
                        lbl = param[4] if len(param) > 4 else ''

                        launcher.add_switch(var, swich_dict, wd, ht, lbl)

                    elif p_type == 'toggle':
                        tg_lbl = param[2]
                        tg_dict = param[3]
                        size = param[4] if len(param) > 4 else []
                        wd, ht = self._validate_size(size, (10, -1))
                        lbl = param[5] if len(param) > 5 else ''
                        launcher.add_toggle(var, tg_lbl, tg_dict, wd, ht, lbl)

                    elif p_type == 'combobox':
                        combobox_list = param[2]
                        size = param[3] if len(param) > 3 else []
                        wd, ht = self._validate_size(size, (10, -1))
                        lbl = param[4] if len(param) > 4 else ''

                        launcher.add_combobox(var, combobox_list, wd, ht,  lbl)

                    elif p_type == 'checkbox':
                        check_lbl = param[2]
                        check_dict = param[3]
                        size = param[4] if len(param) > 4 else []
                        wd, ht = self._validate_size(size, (10, -1))
                        lbl = param[5] if len(param) > 5 else ''
                        launcher.add_checkbox(var, check_lbl, check_dict,
                                              wd, ht, lbl)

                else:
                    # don't know what we are looking at
                    continue

        launcher.add_break()

    def loadLauncher(self, d):
        for d in d['launchers']:
            if d == 'sep':
                self.addSeparator()

            elif isinstance(d, dict):
                self.addLauncherFromYAMLdef(d)


class LauncherPage(Page.CommandPage):

    def __init__(self, frame, name, title):

        super(LauncherPage, self).__init__(frame, name, title)

        self.queueName = 'launcher'
        self.tm_queueName = 'launcher'

        scrolled_window = Widgets.ScrollArea()
        self.content.add_widget(scrolled_window, stretch=1)

        self.fw = Widgets.VBox()
        scrolled_window.set_widget(self.fw)

        self.llist = LauncherList(self.fw, name, title,
                                  self.execute)

        self.btn_cancel = Widgets.Button("Cancel")
        self.btn_cancel.add_callback("activated", lambda w: self.cancel())
        common.modify_bg(self.btn_cancel,
                         common.launcher_colors['cancelbtn'])
        self.leftbtns.add_widget(self.btn_cancel)

        self.btn_pause = Widgets.Button("Pause")
        self.btn_pause.add_callback("activated", self.toggle_pause)
        self.leftbtns.add_widget(self.btn_pause)

        menu = self.add_pulldownmenu("Page")

        # Add items to the menu
        item = menu.add_name("Reset")
        item.add_callback("activated", lambda w: self.reset())

        #self.add_close(side=Page.LEFT)
        #self.add_close()
        item = menu.add_name("Close")
        item.add_callback("activated", lambda w: self.close())


    def load(self, buf):
        ymldef = yaml.safe_load(buf)
        self.llist.loadLauncher(ymldef)

        if 'tabname' in ymldef:
            self.setLabel(ymldef['tabname'])

    def addFromDefs(self, ast):
        self.llist.addFromDefs(ast)

    def addFromList(self, llist):
        self.llist.addFromDefs(llist)

    def close(self):
        super(LauncherPage, self).close()

    def reset(self):
        for launcher in self.llist.getLaunchers():
            launcher.reset()
        self.reset_pause()

    def execute(self, cmdstr, launcher):
        """This is called when a launcher button is pressed."""
        self.logger.info(cmdstr)

        # tag the text so we can manipulate it later
        cmdObj = LauncherCommandObject('ln%d', self.queueName,
                                       self.logger,
                                       launcher, cmdstr)

        common.controller.execOne(cmdObj, 'launcher')


class LauncherCommandObject(CommandObject.CommandObject):

    def __init__(self, format, queueName, logger, launcher, cmdstr):
        self.launcher = launcher
        self.cmdstr = cmdstr

        super(LauncherCommandObject, self).__init__(format, queueName,
                                                    logger)

    def mark_status(self, txttag):
        # This MAY be called from a non-gui thread
        common.gui_do(self.launcher.show_state, txttag)

    def get_preview(self):
        return self.get_cmdstr()

    def get_cmdstr(self):
        return self.cmdstr
