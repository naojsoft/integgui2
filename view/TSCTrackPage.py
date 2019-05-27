# 
# Russell Kackley (rkackley@naoj.org)
#
from __future__ import absolute_import
import os, glob

from gi.repository import Gtk

from g2base import myproc

from . import common
from . import CodePage
import cfg.g2soss as g2soss

import astro.TSCTrackFile as TSCTrackFile

class TSCTrackPage(CodePage.CodePage):

    def __init__(self, frame, name, title):

        super(TSCTrackPage, self).__init__(frame, name, title)

        # add a bottom button
        self.btn_copyTSC = Gtk.Button("Copy to TSC")
        self.btn_copyTSC.connect("clicked", lambda w: self.copyTSCcb())
        self.btn_copyTSC.show()
        self.leftbtns.pack_end(self.btn_copyTSC, False, False, 0)

        self.tscFilePath = None

    def copyTSCcb(self):
        # Copy the TSC-format file to the TSC computer.

        # Check the format of the file and popup a warning box if a
        # problem is detected.
        try:
            TSCTrackFile.checkTSCFileFormat(self.filepath, self.logger)
        except TSCTrackFile.TSCFileFormatError as e:
            common.view.popup_error("Warning: File %s has incorrect format for TSC: %s" % (self.filepath, str(e)))

        # Get the filename part of tscFilePath and then copy the file
        # to the TSC computer.
        tscFilename = os.path.basename(self.filepath)
        try:
            tscPath = TSCTrackFile.copyToTSC(self.filepath, tscFilename, self.logger)
            date_time, filename = TSCTrackFile.confirmFileTSC(tscPath, self.logger)
            common.view.popup_info('TSC ephemerides', '%s copied to %s at %s' % (self.filepath, tscPath, date_time))
        except Exception as e:
            return common.view.popup_error("Cannot copy file to TSC: %s" % (
                str(e)))
#END
