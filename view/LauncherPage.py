#
# Eric Jeschke (eric@naoj.org)
#
from __future__ import absolute_import
import threading
import yaml
import functools

from gi.repository import Gtk

from ginga.misc import Bunch

from . import common
from . import Page
from . import CommandObject

# Default width of the main launcher buttons
default_width = 150

class LauncherError(Exception):
    pass

class Launcher(object):

    def __init__(self, frame, name, title, execfn):
        self.frame = frame
        self.params = Bunch.Bunch()
        self.paramList = []
        self.row = 1
        self.col = 1
        self.max_col = self.col
        self.btn_width = 20
        self.execfn = execfn

        self.table = Gtk.Table(rows=2, columns=2)
        self.table.set_name('launcher')
        self.table.show()

        self.btn_exec = Gtk.Button(title)
        self.btn_exec.set_size_request(default_width, -1)
        self.btn_exec.connect("clicked", lambda w: self.execute())
        self.btn_exec.show()

        self.table.attach(self.btn_exec, 0, 1, 1, 2,
                          xoptions=Gtk.AttachOptions.FILL, yoptions=Gtk.AttachOptions.FILL,
                          xpadding=1, ypadding=1)

        frame.pack_start(self.table, False, True, 0)


    def addParam(self, name):
        self.paramList.append(name)
        key = functools.cmp_to_key(lambda x, y: len(y) - len(x))
        # sort parameter list so longer strings are substituted first
        self.paramList.sort(key=key)

    def add_cmd(self, cmdstr):
        self.cmdstr = cmdstr

    def add_break(self):
        self.row += 2
        self.col = 1
        self.table.resize(self.row+1, self.max_col+1)

    def bump_col(self):
        self.col += 1
        self.max_col = max(self.col, self.max_col)
        self.table.resize(self.row+1, self.max_col+1)

    def add_input(self, name, width, defVal, label):

        lbl = Gtk.Label(label)
        lbl.show()
        self.table.attach(lbl, self.col, self.col+1, self.row-1, self.row,
                          xoptions=Gtk.AttachOptions.FILL, yoptions=Gtk.AttachOptions.FILL,
                          xpadding=1, ypadding=1)
        field = Gtk.Entry()
        field.set_width_chars(width)
        field.set_text(str(defVal))
        field.show()
        self.table.attach(field, self.col, self.col+1, self.row, self.row+1,
                          xoptions=Gtk.AttachOptions.FILL, yoptions=Gtk.AttachOptions.FILL,
                          xpadding=1, ypadding=1)
        self.bump_col()

        name = name.lower()
        self.params[name] = Bunch.Bunch(widget=field,
                                        get_fn=self.get_entry)
        self.addParam(name)


    def add_list(self, name, optionList, label):

        lbl = Gtk.Label(label)
        self.table.attach(lbl, self.col, self.col+1, self.row-1, self.row,
                          xoptions=Gtk.AttachOptions.FILL, yoptions=Gtk.AttachOptions.FILL,
                          xpadding=1, ypadding=1)
        lbl.show()
        combobox = Gtk.ComboBoxText()
        options = []
        index = 0
        for opt, val in optionList:
            options.append(val)
            combobox.insert_text(index, opt)
            index += 1
        combobox.set_active(0)
        combobox.show()
        self.table.attach(combobox, self.col, self.col+1, self.row, self.row+1,
                          xoptions=Gtk.AttachOptions.FILL, yoptions=Gtk.AttachOptions.FILL,
                          xpadding=1, ypadding=1)
        self.bump_col()

        name = name.lower()
        self.params[name] = Bunch.Bunch(widget=combobox,
                                        get_fn=self.get_list,
                                        options=options)
        self.addParam(name)


    def add_radio(self, name, optionList, label):

        lbl = Gtk.Label(label)
        self.table.attach(lbl, self.col, self.col+1, self.row-1, self.row,
                          xoptions=Gtk.AttachOptions.FILL, yoptions=Gtk.AttachOptions.FILL,
                          xpadding=1, ypadding=1)
        lbl.show()

        btn = None
        options = []
        for opt, val in optionList:
            btn = Gtk.RadioButton(group=btn, label=opt)
            self.table.attach(btn, self.col, self.col+1, self.row, self.row+1,
                              xoptions=Gtk.AttachOptions.FILL, yoptions=Gtk.AttachOptions.FILL,
                              xpadding=1, ypadding=1)
            options.append((btn, val))
            self.bump_col()
            btn.show()

        name = name.lower()
        self.params[name] = Bunch.Bunch(get_fn=self.get_radio,
                                        options=options)
        self.addParam(name)

    def get_entry(self, bnch):
        return bnch.widget.get_text()

    def get_list(self, bnch):
        index = bnch.widget.get_active()
        try:
            return bnch.options[index]
        except IndexError:
            return None

    def get_radio(self, bnch):
        for widget, val in bnch.options:
            if widget.get_active():
                return val
        return None

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
        self.vbox = Gtk.VBox(spacing=2)
        frame.pack_start(self.vbox, True, True, 0)

    def addSeparator(self):
        separator = Gtk.HSeparator()
        separator.show()
        self.vbox.pack_start(separator, False, True, 0)
        self.count += 1

    def addLauncher(self, name, title):
        frame = Gtk.VBox()
        frame.show()
        self.vbox.pack_start(frame, False, True, 0)
        self.count += 1

        launcher = Launcher(frame, name, title, self.execfn)

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

    def addFromDefs(self, ast):
        assert ast.tag == 'launchers'

        for ast in ast.items:
            if ast.tag == 'sep':
                self.addSeparator()

            else:
                self.addLauncherFromDef(ast)

    def _validate_elt(self, elt):
        if isinstance(elt, list) and len(elt) == 2:
            return elt

        elt_s = str(elt)
        if not '=' in elt_s:
            return [elt_s, elt_s]
        else:
            return elt_s.split('=')

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
                        lbl = ''
                        if len(param) > 3:
                            lbl = param[3]

                        launcher.add_radio(var, vallst, lbl)

                    elif p_type == 'list':
                        vallst = [self._validate_elt(e) for e in param[2]]
                        lbl = ''
                        if len(param) > 3:
                            lbl = param[3]

                        launcher.add_list(var, vallst, lbl)

                else:
                    # don't know what we are looking at
                    continue


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

        scrolled_window = Gtk.ScrolledWindow()
        scrolled_window.set_border_width(2)

        scrolled_window.set_policy(Gtk.PolicyType.AUTOMATIC,
                                   Gtk.PolicyType.AUTOMATIC)
        frame.pack_start(scrolled_window, True, True, 0)

        scrolled_window.show()

        self.fw = Gtk.VBox()
        scrolled_window.add_with_viewport(self.fw)

        self.llist = LauncherList(self.fw, name, title,
                                  self.execute)

        self.btn_cancel = Gtk.Button("Cancel")
        self.btn_cancel.connect("clicked", lambda w: self.cancel())
        common.modify_bg(self.btn_cancel,
                         common.launcher_colors['cancelbtn'])
        self.btn_cancel.show()
        self.leftbtns.pack_start(self.btn_cancel, False, False, 4)

        self.btn_pause = Gtk.Button("Pause")
        self.btn_pause.connect("clicked", self.toggle_pause)
        self.btn_pause.show()
        self.leftbtns.pack_start(self.btn_pause, False, False, 0)

        menu = self.add_pulldownmenu("Page")

        # Add items to the menu
        item = Gtk.MenuItem(label="Reset")
        menu.append(item)
        item.connect_object ("activate", lambda w: self.reset(),
                             "menu.Reset")
        item.show()

        #self.add_close(side=Page.LEFT)
        #self.add_close()
        item = Gtk.MenuItem(label="Close")
        menu.append(item)
        item.connect_object ("activate", lambda w: self.close(),
                             "menu.Close")
        item.show()

        scrolled_window.show_all()


    def load(self, buf):
        ymldef = yaml.load(buf)
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


#END
