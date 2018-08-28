# 
# Eric Jeschke (eric@naoj.org)
#
from __future__ import absolute_import
import os

from gi.repository import Gtk

from g2base import myproc

from . import common
from . import CodePage, OpePage


class InfPage(CodePage.CodePage):

    def __init__(self, frame, name, title):

        super(InfPage, self).__init__(frame, name, title)

        # add some bottom buttons
        self.btn_makeope = Gtk.Button("Make OPE")
        self.btn_makeope.connect("clicked", lambda w: self.makeope('app2ope.pl -'))
        self.btn_makeope.show()
        self.leftbtns.pack_end(self.btn_makeope, False, False, 0)

        self.btn_makedarks = Gtk.Button("Make Darks")
        self.btn_makedarks.connect("clicked", lambda w: self.makeope('mkDARKope.pl -'))
        self.btn_makedarks.show()
        self.leftbtns.pack_end(self.btn_makedarks, False, False, 0)

    def makeope(self, cmdstr):
        # get text to process
        start, end = self.buf.get_bounds()
        buf = self.buf.get_text(start, end, True)

        try:
            proc = myproc.myproc(cmdstr)
            # write input to stdin
            proc.stdin.write(buf)
            proc.stdin.close()

            # This will force a reap
            proc.status()
            output = proc.output()
            #print output

            # make ope file path
            infdir, inffile = os.path.split(self.filepath)
            infpfx, infext = os.path.splitext(inffile)

            opepath = os.path.join(infdir, '%s.ope' % infpfx)

            common.view.open_generic(common.view.exws, output, opepath,
                                     OpePage.OpePage)

        except Exception as e:
            return common.view.popup_error("Cannot generate ope file: %s" % (
                    str(e)))


#END
