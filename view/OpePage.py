import os
import gtk

import common
import CodePage


class OpePage(CodePage.CodePage):

    def __init__(self, frame, name, title):

        super(OpePage, self).__init__(frame, name, title)

        self.queueName = 'executer'

        # add some bottom buttons
        self.btn_exec = gtk.Button("Exec")
        self.btn_exec.connect("clicked", lambda w: common.view.execute(self))
        self.btn_exec.show()
        self.btns.pack_end(self.btn_exec)

        self.btn_pause = gtk.Button("Pause")
        self.btn_pause.connect("clicked", lambda w: self.pause())
        self.btn_pause.show()
        self.btns.pack_end(self.btn_pause)

        self.btn_cancel = gtk.Button("Cancel")
        self.btn_cancel.connect("clicked", lambda w: self.cancel())
        self.btn_cancel.show()
        self.btns.pack_end(self.btn_cancel)

        self.btn_kill = gtk.Button("Kill")
        self.btn_kill.connect("clicked", lambda w: self.kill())
        self.btn_kill.show()
        self.btns.pack_end(self.btn_kill)


    def loadbuf(self, buf):

        super(OpePage, self).loadbuf(buf)

        lines = buf.split('\n')
        header = '\n' * len(lines)
##         hw = self.txt.component('rowheader')
##         hw.delete('1.0', 'end')
##         hw.insert('end', header)


    def load(self, filepath, buf):

        super(OpePage, self).load(filepath, buf)

        name, ext = os.path.splitext(self.filepath)
        ext = ext.lower()

        if ext in ('.ope', '.cd'):
            self.color()


    def color(self):

        self.tags = common.decorative_tags + common.execution_tags
        
        start, end = self.buf.get_bounds()
        buf = self.buf.get_text(start, end)

        def addtags(lineno, tags):
            start.set_line(lineno)
            end.set_line(lineno)
            end.forward_to_line_end()

            for tag in tags:
                self.buf.apply_tag_by_name(tag, start, end)

        try:
            for tag, bnch in self.tags:
                properties = {}
                properties.update(bnch)
                self.buf.create_tag(tag, **properties)

        except:
            # in case they've been created already
            pass

        lineno = 0
        for line in buf.split('\n'):
            line = line.strip()
            if line.startswith('###'):
                addtags(lineno, ['comment3'])
        
            elif line.startswith('##'):
                addtags(lineno, ['comment2'])
        
            elif line.startswith('#'):
                addtags(lineno, ['comment1'])

            lineno += 1



    def kill(self):
        #controller = self.parent.get_controller()
        common.controller.tm_restart()

    def cancel(self):
        #controller = self.parent.get_controller()
        common.controller.tm_cancel(self.queueName)

    def pause(self):
        #controller = self.parent.get_controller()
        common.controller.tm_pause(self.queueName)


#END
