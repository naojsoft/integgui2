#
# Russell Kackley (rkackley@naoj.org)
#
import os, glob

from gi.repository import Gtk

from g2base import myproc

from . import common
from . import CodePage
from . import TSCTrackPage
import cfg.g2soss as g2soss

import astro.jplHorizonsIF as jplHorizonsIF
import astro.TSCTrackFile as TSCTrackFile

class EphemPage(CodePage.CodePage):

    def __init__(self, frame, name, title):

        super(EphemPage, self).__init__(frame, name, title)

        # add some bottom buttons
        self.btn_convertToTSC = Gtk.Button("Convert to TSC format")
        self.btn_convertToTSC.connect("clicked", lambda w: self.convertToTSCcb())
        self.btn_convertToTSC.show()
        self.leftbtns.pack_end(self.btn_convertToTSC, False, False, 0)

        ## Don't create or show the "Convert and Copy to TSC" button.
        ## self.btn_copyTSC = Gtk.Button("Convert and Copy to TSC")
        ## self.btn_copyTSC.connect("clicked", lambda w: self.copyTSCcb())
        ## self.btn_copyTSC.show()
        ## self.leftbtns.pack_end(self.btn_copyTSC, False, False, 0)

        self.tscFilePath = None

    def convertToTSC(self):
        # get text to process from the buffer, which should be
        # ephemeris data output from JPL Horizons
        start, end = self.buf.get_bounds()
        buf = self.buf.get_text(start, end, True)

        # Parse the input buffer to create the JPLHorizonsEphem
        # object.
        jplHorizonsEphem = jplHorizonsIF.JPLHorizonsEphem(buf, self.logger)

        # Make the TSC file path from the filename from which the
        # buffer was filled.
        tscdir, tscfile = os.path.split(self.filepath)
        tscpfx, tscext = os.path.splitext(tscfile)
        self.tscFilePath = os.path.join(tscdir, '%s.tsc' % tscpfx)

        # Write out the tracking coordinates to the TSC file and then
        # read that file back into a text string.
        TSCTrackFile.writeTSCTrackFile(self.tscFilePath, jplHorizonsEphem.trackInfo, self.logger)
        with open(self.tscFilePath, 'r') as f:
            output = f.read()

        # Load the converted tracking coordinates into a new page.
        common.view.open_generic(common.view.exws, output, self.tscFilePath,
                                 TSCTrackPage.TSCTrackPage)

    def convertToTSCcb(self):
        # Convert the input buffer to TSC format and display the
        # results in a new page
        try:
            self.convertToTSC()
        except Exception as e:
            return common.view.popup_error("Cannot convert input to TSC format: %s" % (
                str(e)))

    def copyTSCcb(self):
        # Convert the input buffer to TSC format, display the results
        # in a new page, and copy the TSC-format file to the TSC
        # computer.
        try:
            self.convertToTSC()
        except Exception as e:
            return common.view.popup_error("Cannot convert input to TSC format: %s" % (
                    str(e)))

        # Check the format of the file and popup a warning box if a
        # problem is detected.
        try:
            TSCTrackFile.checkTSCFileFormat(self.tscFilePath, self.logger)
        except TSCTrackFile.TSCFileFormatError as e:
            common.view.popup_error("Warning: File %s has incorrect format for TSC: %s" % (self.filepath, str(e)))

        # Get the filename part of tscFilePath and then copy the file
        # to the TSC computer.
        tscFilename = os.path.basename(self.tscFilePath)
        try:
            tscPath = TSCTrackFile.copyToTSC(self.tscFilePath, tscFilename, self.logger)
            common.view.popup_info('TSC ephemerides', '%s copied to %s' % (self.tscFilePath, tscPath))
        except Exception as e:
            return common.view.popup_error("Cannot copy file to TSC: %s" % (
                str(e)))
#END
