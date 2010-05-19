import gtk

import Bunch
import common
import Page


class Launcher(object):
    
    def __init__(self, frame, name, title, execfn):
        self.frame = frame
        self.params = Bunch.Bunch()
        self.paramList = []
        self.row = 1
        self.col = 1
        self.btn_width = 20
        self.execfn = execfn

        self.btn_exec = gtk.Button(title)
        self.btn_exec.connect("clicked", self.execute)
        self.btn_exec.show()
        btns.pack_end(self.btn_exec)

        #self.btn_exec.grid(row=1, column=0, padx=1, sticky='ew')
        

    def addParam(self, name):
        self.paramList.append(name)
        # sort parameter list so longer strings are substituted first
        self.paramList.sort(lambda x,y: len(y) - len(x))

    def add_cmd(self, cmdstr):
        self.cmdstr = cmdstr

    def add_break(self):
        self.row += 2
        self.col = 1

    def add_input(self, name, width, defVal, label):
        
        lbl = Tkinter.Label(self.frame, text=label, relief='flat')
        lbl.grid(row=self.row-1, column=self.col, padx=1, sticky='ew')
        tclvar = Tkinter.StringVar(self.frame)
        tclvar.set(str(defVal))
        field = Tkinter.Entry(self.frame, textvariable=tclvar, width=width)
        field.grid(row=self.row, column=self.col, padx=1, sticky='ew')
        self.col += 1

        name = name.lower()
        self.params[name] = Bunch.Bunch(widget=field,
                                        var=tclvar,
                                        get=self.getvar)
        self.addParam(name)

    def add_list(self, name, optionList, label):
        
        lbl = Tkinter.Label(self.frame, text=label, relief='flat')
        lbl.grid(row=self.row-1, column=self.col, padx=1, sticky='ew')
        tclvar = Tkinter.StringVar(self.frame)
        optionsDict = {}
        options = []
        for opt, val in optionList:
            optionsDict[opt] = val
            options.append(opt)
        tclvar.set(options[0])
        menu = Tkinter.OptionMenu(self.frame, tclvar, *options)
        menu.grid(row=self.row, column=self.col, padx=1, sticky='ew')
        self.col += 1

        name = name.lower()
        self.params[name] = Bunch.Bunch(widget=menu, 
                                        var=tclvar,
                                        get=self.getdict,
                                        optionsDict=optionsDict)
        self.addParam(name)

    def add_radio(self, name, optionList, label):
        
        lbl = Tkinter.Label(self.frame, text=label, relief='flat')
        lbl.grid(row=self.row-1, column=self.col, padx=1, sticky='ew')
        tclvar = Tkinter.StringVar(self.frame)
        tclvar.set(optionList[0][1])
        for opt, val in optionList:
            b = Tkinter.Radiobutton(self.frame, text=opt, 
                                    variable=tclvar, value=str(val),
                                    relief='flat')
            b.grid(row=self.row, column=self.col, padx=1, sticky='ew')
            self.col += 1

        name = name.lower()
        self.params[name] = Bunch.Bunch(widget=b,
                                        get=self.getvar,
                                        var=tclvar)
        self.addParam(name)

    def getvar(self, bnch):
        return bnch.var.get()

    def getdict(self, bnch):
        key = bnch.var.get()
        return bnch.optionsDict[key]

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

    def addSeparator(self):
        separator = gtk.HSeparator()
        separator.grid(row=self.count, column=0, sticky='ew',
                       padx=5, pady=5)
        self.count += 1

    def addLauncher(self, name, title):
        frame = Tkinter.Frame(self.frame, padx=2, pady=2)
        #frame.pack(side=Tkinter.TOP, fill='x', expand=False)
        frame.grid(row=self.count, column=0, sticky='w')
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


class LauncherPage(Page.Page):

    def __init__(self, frame, name, title):

        super(LauncherPage, self).__init__(frame, name, title)

        self.queueName = 'launcher'

        scrolled_window = gtk.ScrolledWindow()
        scrolled_window.set_border_width(2)
        
        scrolled_window.set_policy(gtk.POLICY_AUTOMATIC,
                                   gtk.POLICY_AUTOMATIC)
        frame.pack_start(expand=True, fill=True)
        
        scrolled_window.show()

        self.fw = gtk.VBox()
        scrolled_window.add_with_viewport(self.fw)
        
        self.llist = LauncherList(self.fw, name, title,
                                  self.execute)

        # bottom buttons
        btns = gtk.HButtonBox()
        btns.set_layout(gtk.BUTTONBOX_START)
        btns.set_spacing(5)
        self.btns = btns

        self.btn_close = gtk.Button("Close")
        self.btn_close.connect("clicked", lambda w: self.close())
        self.btn_close.show()
        btns.pack_end(self.btn_close, padding=4)

        self.btn_pause = gtk.Button("Pause")
        self.btn_pause.connect("clicked", lambda w: self.pause())
        self.btn_pause.show()
        btns.pack_end(self.btn_pause, padding=4)

        self.btn_cancel = gtk.Button("Cancel")
        self.btn_cancel.connect("clicked", lambda w: self.cancel())
        self.btn_cancel.show()
        btns.pack_end(self.btn_cancel, padding=4)

        frame.pack_end(btns, fill=False, expand=False, padding=2)

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
        common.controller.tm_cancel(self.queueName)

    def pause(self):
        #controller = self.parent.get_controller()
        common.controller.tm_pause(self.queueName)

#END
