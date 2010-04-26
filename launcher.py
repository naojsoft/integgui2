# 
#[ Eric Jeschke (eric@naoj.org) --
#  Last edit: Wed Apr 21 14:21:56 HST 2010
#]

# remove once we're certified on python 2.6
from __future__ import with_statement

import re
import Tkinter

import Bunch


regex_label = re.compile(r'^\s*LABEL\s+"([^"]+)"')
regex_cmd = re.compile(r'^\s*CMD\s+(.+)$')
regex_param = re.compile(r'^\s*(\w+)\s+(LIST|INPUT|SELECT)\s*(.+)$')


class Launcher(object):
    
    def __init__(self, frame, name, title):
        self.frame = frame
        self.params = Bunch.Bunch()
        self.row = 1
        self.col = 1
        self.btn_width = 20

        self.btn_exec = Tkinter.Button(frame, text=title,
                                       relief='raised',
                                       activebackground="#089D20",
                                       activeforeground="#FFFF00",
                                       width=self.btn_width)
        self.btn_exec.grid(row=1, column=0, padx=1, sticky='ew')
        

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
                                        var=tclvar)

    def add_list(self, name, optionList, label):
        
        lbl = Tkinter.Label(self.frame, text=label, relief='flat')
        lbl.grid(row=self.row-1, column=self.col, padx=1, sticky='ew')
        tclvar = Tkinter.StringVar(self.frame)
        optionsDict = {}
        options = []
        for name, val in optionList:
            optionsDict[name] = val
            options.append(name)
        tclvar.set(options[0])
        menu = Tkinter.OptionMenu(self.frame, tclvar, *options)
        menu.grid(row=self.row, column=self.col, padx=1, sticky='ew')
        self.col += 1

        name = name.lower()

        self.params[name] = Bunch.Bunch(widget=menu, 
                                        var=tclvar,
                                        optionsDict=optionsDict)

    def add_radio(self, name, optionList, label):
        
        lbl = Tkinter.Label(self.frame, text=label, relief='flat')
        lbl.grid(row=self.row-1, column=self.col, padx=1, sticky='ew')
        tclvar = Tkinter.StringVar(self.frame)
        tclvar.set(optionList[0][1])
        for name, val in optionList:
            b = Tkinter.Radiobutton(self.frame, text=name, 
                                    variable=tclvar, value=str(val),
                                    relief='flat')
            b.grid(row=self.row, column=self.col, padx=1, sticky='ew')
            self.col += 1

        name = name.lower()

        self.params[name] = Bunch.Bunch(widget=b, 
                                        var=tclvar)

    def getcmd(self):
        res = self.cmdstr
        for key, bnch in self.params.items():
            val = str(bnch.var.get())
            # Need to worry about order here?  I think so.
            res = res.replace('$%s' % key, val)

        return res


class LauncherList(object):
    
    def __init__(self, frame, name, title):
        self.llist = []
        self.ldict = {}
        self.count = 0
        self.frame = frame
        self.parser = CommandParser(['=', ','])

    def addLauncher(self, name, title):
        frame = Tkinter.Frame(self.frame, padx=2, pady=2)
        #frame.pack(side=Tkinter.TOP, fill='x', expand=False)
        frame.grid(row=self.count, column=0, sticky='w')
        self.count += 1
        
        launcher = Launcher(frame, name, title)
        
        self.llist.append(launcher)
        self.ldict[name.lower()] = launcher
        
        return launcher

    def getLauncher(self, name):
        return self.ldict[name.lower()]

    def loadLauncher(self, buf):

        lines = buf.split('\n')

        launcher = None

        for line in lines:
            line = line.strip()
            
            if line.startswith('#') or len(line) == 0:
                continue

            if line.startswith('<>') and (launcher != None):
                launcher.add_break()
                continue

            match = regex_label.match(line)
            if match:
                title = match.group(1)
                launcher = self.addLauncher(title, title)
                continue

            match = regex_param.match(line)
            if match:
                name, wtype, argstr = match.groups()
                name = name.lower()
                
                if wtype == 'INPUT':
                    args = self.parser.parse(argstr)
                    assert(len(args) >= 2)
                    tok = args[0]
                    assert(tok.tag == 'item')
                    width = int(tok.vals[0])

                    tok = args[1]
                    assert(tok.tag == 'item')
                    defVal = tok.vals[0]
                    
                    if len(args) == 3:
                        tok = args[2]
                        assert(tok.tag == 'item')
                        label = tok.vals[0]
                    else:
                        label = ''

                    launcher.add_input(name, width, defVal, label)
                    
                elif wtype == 'SELECT':
                    args = self.parser.parse(argstr)

                    optionList = []
                    for tok in args:
                        if tok.tag == 'asn':
                            optionList.append(tok.vals)
                        elif tok.tag == 'item':
                            optionList.append([tok.vals[0], tok.vals[0]])

                    launcher.add_radio(name, optionList, '')

                elif wtype == 'LIST':
                    args = self.parser.parse(argstr)

                    optionList = []
                    for tok in args:
                        if tok.tag == 'asn':
                            optionList.append(tok.vals)
                        elif tok.tag == 'item':
                            optionList.append([tok.vals[0], tok.vals[0]])

                    launcher.add_list(name, optionList, '')

class CommandParserError(Exception):
    pass


class CommandParser(object):
    """This class provides methods for tokenizing and parsing SOSS-style
    commands; e.g.
       EXEC SUBSYS COMMAND PARAM1=VAL1 PARAM2=VAL2 ...
    """

    def __init__(self, terminators):
        self.whitespace = (' ', '\t', '\n')
        self.quotes = ('"', "'")
        self.terminators = terminators

    def initialize(self):
        self.start_quote = None
        self.chars = []             # Character buffer
        self.tokens = []            # Token buffer


    def _make_token(self):
        # Make a token by concatenating all characters in the char buffer.
        token = ''.join(self.chars)
        self.tokens.append(token)
        # Clear char buffer
        self.chars = []
            

    def tokenize(self, cmdstr):
        """Tokenizes a command string by lexing it into tokens.
        """
        self.initialize()
        
        charlst = list(cmdstr)
        self.tokens = []
        self.start_quote = None
        self.chars = []

        while len(charlst) > 0:
            c = charlst.pop(0)

            # process double quotes
            if c in self.quotes:
                # if we are not building a quoted string, then turn on quote
                # flag and continue scanning
                if not self.start_quote:
                    self.start_quote = c
                    continue
                elif self.start_quote != c:
                    self.chars.append(c)
                    continue
                else:
                    # end of quoted string; make token
                    self._make_token()
                    self.start_quote = None
                    continue

            # process white space
            elif c in self.whitespace:
                if self.start_quote:
                    self.chars.append(c)
                    continue
                else:
                    if len(self.chars) > 0:
                        self._make_token()
                    continue

            # process white space
            elif c in self.terminators:
                if self.start_quote:
                    self.chars.append(c)
                    continue
                else:
                    # Terminate existing token
                    if len(self.chars) > 0:
                        self._make_token()
                    # Make token from terminator
                    self.chars = [c]
                    self._make_token()
                    continue
                    
            # "normal" char
            else:
                self.chars.append(c)
                continue

        if len(self.chars) > 0:
            self._make_token()

        if self.start_quote:
            raise CommandParserError("Unterminated quotation: '%s'" % cmdstr)

        return self.tokens

    def parse(self, cmdstr):
        tokens = self.tokenize(cmdstr)

        res = []
        while len(tokens) > 0:
            token1 = tokens.pop(0)
            
            if (len(tokens) > 0) and (tokens[0] == '='):
                token2 = tokens.pop(0)
                res.append(Bunch.Bunch(tag='asn', vals=[token1, token2]))

            else:
                res.append(Bunch.Bunch(tag='item', vals=[token1]))

    def parse2(self, tokens):
        res = []
        while len(tokens) > 0:
            token1 = tokens.pop(0)
            
            if (len(tokens) > 0) and (tokens[0] == ','):
                res.append(token1)
                tokens.pop(0)

        return res


#END
            

