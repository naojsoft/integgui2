# 
#[ Eric Jeschke (eric@naoj.org) --
#  Last edit: Tue May 18 17:16:48 HST 2010
#]

import gtk

import Bunch
import common
import Page

# Default width of the main launcher buttons
default_width = 150


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

        self.table = gtk.Table(rows=2, columns=2)
        self.table.set_name('launcher')
        self.table.show()

        self.btn_exec = gtk.Button(title)
        self.btn_exec.set_size_request(default_width, -1)
        self.btn_exec.connect("clicked", lambda w: self.execute())
        self.btn_exec.show()

        self.table.attach(self.btn_exec, 0, 1, 1, 2,
                          xoptions=gtk.FILL, yoptions=gtk.FILL,
                          xpadding=1, ypadding=1)

        frame.pack_start(self.table, expand=False, fill=True)
        

    def addParam(self, name):
        self.paramList.append(name)
        # sort parameter list so longer strings are substituted first
        self.paramList.sort(lambda x,y: len(y) - len(x))

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
        
        lbl = gtk.Label(label)
        lbl.show()
        self.table.attach(lbl, self.col, self.col+1, self.row-1, self.row,
                          xoptions=gtk.FILL, yoptions=gtk.FILL,
                          xpadding=1, ypadding=1)
        field = gtk.Entry(max=width)
        field.set_text(str(defVal))
        field.show()
        self.table.attach(field, self.col, self.col+1, self.row, self.row+1,
                          xoptions=gtk.FILL, yoptions=gtk.FILL,
                          xpadding=1, ypadding=1)
        self.bump_col()

        name = name.lower()
        self.params[name] = Bunch.Bunch(widget=field,
                                        get=self.get_entry)
        self.addParam(name)


    def add_list(self, name, optionList, label):
        
        lbl = gtk.Label(label)
        self.table.attach(lbl, self.col, self.col+1, self.row-1, self.row,
                          xoptions=gtk.FILL, yoptions=gtk.FILL,
                          xpadding=1, ypadding=1)
        lbl.show()
        combobox = gtk.combo_box_new_text()
        options = []
        index = 0
        for opt, val in optionList:
            options.append(val)
            combobox.insert_text(index, opt)
            index += 1
        combobox.set_active(0)
        combobox.show()
        self.table.attach(combobox, self.col, self.col+1, self.row, self.row+1,
                          xoptions=gtk.FILL, yoptions=gtk.FILL,
                          xpadding=1, ypadding=1)
        self.bump_col()

        name = name.lower()
        self.params[name] = Bunch.Bunch(widget=combobox, 
                                        get=self.get_list,
                                        options=options)
        self.addParam(name)


    def add_radio(self, name, optionList, label):
        
        lbl = gtk.Label(label)
        self.table.attach(lbl, self.col, self.col+1, self.row-1, self.row,
                          xoptions=gtk.FILL, yoptions=gtk.FILL,
                          xpadding=1, ypadding=1)
        lbl.show()
        
        btn = None
        options = []
        for opt, val in optionList:
            btn = gtk.RadioButton(group=btn, label=opt)
            self.table.attach(btn, self.col, self.col+1, self.row, self.row+1,
                              xoptions=gtk.FILL, yoptions=gtk.FILL,
                              xpadding=1, ypadding=1)
            options.append((btn, val))
            self.bump_col()
            btn.show()

        name = name.lower()
        self.params[name] = Bunch.Bunch(get=self.get_radio,
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
                val = str(bnch.get(bnch))
                cmdstr = cmdstr.replace(dvar, val)

        return cmdstr

    def execute(self):
        cmdstr = self.getcmd()
        self.execfn(cmdstr)


class LauncherList(object):
    
    def __init__(self, frame, name, title, execfn):
        self.llist = []
        self.ldict = {}
        self.count = 0
        self.frame = frame
        self.execfn = execfn
        self.vbox = gtk.VBox(spacing=2)
        frame.pack_start(self.vbox, expand=True, fill=True)

    def addSeparator(self):
        separator = gtk.HSeparator()
        separator.show()
        self.vbox.pack_start(separator, expand=False, fill=True)
        self.count += 1

    def addLauncher(self, name, title):
        frame = gtk.VBox()
        frame.show()
        self.vbox.pack_start(frame, expand=False, fill=True)
        self.count += 1
        
        launcher = Launcher(frame, name, title,
                            lambda cmdstr: self.execute(name, cmdstr))
        
        self.llist.append(launcher)
        self.ldict[name.lower()] = launcher
        
        return launcher

    def getLauncher(self, name):
        return self.ldict[name.lower()]

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


    def execute(self, name, cmdstr):
        self.execfn(cmdstr)


class LauncherPage(Page.ButtonPage):

    def __init__(self, frame, name, title):

        super(LauncherPage, self).__init__(frame, name, title)

        self.queueName = 'launcher'
        self.block = False

        scrolled_window = gtk.ScrolledWindow()
        scrolled_window.set_border_width(2)
        
        scrolled_window.set_policy(gtk.POLICY_AUTOMATIC,
                                   gtk.POLICY_AUTOMATIC)
        frame.pack_start(scrolled_window, expand=True, fill=True)
        
        scrolled_window.show()

        self.fw = gtk.VBox()
        scrolled_window.add_with_viewport(self.fw)
        
        self.llist = LauncherList(self.fw, name, title,
                                  self.execute)

        self.btn_cancel = gtk.Button("Cancel")
        self.btn_cancel.connect("clicked", lambda w: self.cancel())
        self.btn_cancel.show()
        self.leftbtns.pack_start(self.btn_cancel, padding=4)

        self.btn_pause = gtk.ToggleButton("Pause")
        self.btn_pause.connect("toggled", self.toggle_pause)
        self.btn_pause.show()
        self.leftbtns.pack_start(self.btn_pause)

        self.add_close(side=Page.LEFT)

        scrolled_window.show_all()


    def load(self, buf):
        self.llist.loadLauncher(buf)

    def addFromDefs(self, ast):
        self.llist.addFromDefs(ast)

    def execute(self, cmdstr):
        """This is called when a launcher button is pressed."""
        common.view.execute_launcher(cmdstr)

    def close(self):
        super(LauncherPage, self).close()

    def cancel(self):
        #controller = self.parent.get_controller()
        controller = common.controller
        controller.tm_cancel(self.queueName)
        self.block = True
        self.btn_pause.set_active(False)
        self.block = False

    def pause(self):
        if self.block:
            return
        #controller = self.parent.get_controller()
        controller = common.controller
        controller.tm_pause(self.queueName)

    def resume(self):
        if self.block:
            return
        #controller = self.parent.get_controller()
        controller = common.controller
        controller.tm_resume(self.queueName)

    def toggle_pause(self, w):
        if w.get_active():
            self.pause()
            self.btn_pause.set_label("Resume")
        else:
            self.resume()
            self.btn_pause.set_label("Pause")

        return True


#END
