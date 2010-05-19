# 
#[ Eric Jeschke (eric@naoj.org) --
#  Last edit: Fri May 14 14:25:18 HST 2010
#]

# remove once we're certified on python 2.6
from __future__ import with_statement

import threading

import remoteObjects as ro
import Bunch

# Headers we show
headers = [ 'DATE-OBS', 'UT-STR', 'EXPTIME', 'OBS-MOD',
           'OBJECT', 'FILTERS', 'MEMO' ]


class IntegGUINotify(object):

    def __init__(self, gui, fitsdir):
        self.gui = gui
        self.fitsdir = fitsdir
        # Dict used to flag processed files so they are not repeated
        self.framecache = {}
        self.framelist = []
        self.needsort = False
        self.lock = threading.RLock()

    def get_memo(self, frameid, frameinfo):
        # Try to read a memo for this frame
        frameinfo['MEMO'] = '[N/A]'
        if self.fitsdir:
            try:
                #memodir = './IntegObsNote.workdir'
                memodir = self.fitsdir
                memofile = memodir + '/' + frameid + '.memo'
                memo_f = open(memofile, 'r')

                memo = memo_f.read().strip()
                frameinfo['MEMO'] = memo

                memo_f.close()

            except IOError:
                pass


    def update_framelist(self):
        with self.lock:
            return self.gui.update_frames(self.framelist)

    def output_line(self, frameinfo):
        self.gui.update_frame(frameinfo)


    def _getframe(self, frameid, **kwdargs):
        """Called when the _frameid_ is first seen."""

        with self.lock:
            if self.framecache.has_key(frameid):
                d = self.framecache[frameid]
                d.update(kwdargs)
                return d

            # Create a new entry
            d = Bunch.Bunch(frameid=frameid,
                            status='A')

            for key in headers:
                d[key] = ""
            d.update(kwdargs)

            self.framecache[frameid] = d
            try:
                lastid = self.framelist[-1]
                if frameid < lastid:
                    self.needsort = True
            except IndexError:
                # First frame
                pass
            self.framelist.append(d)

            return d


    def frame_allocated(self, frameid, vals):
        """Called when the _frameid_ is allocated."""

        with self.lock:
            # Create a new entry
            d = self._getframe(frameid)

            self.output_line(d)
            return ro.OK

    def transfer_started(self, frameid, vals):
        """Called when the _frameid_ transfer from the OBCP has been
        initiated."""

        with self.lock:
            d = self._getframe(frameid)
            if d.status == 'A':
                d.status = 'X'

            self.output_line(d)
            return ro.OK

    def fits_info(self, frameid, frameinfo, vals):
        """Called when the _frameid_ transfer from the OBCP has
        finished.  _frameinfo_ is some information about the frame."""

        with self.lock:
            d = self._getframe(frameid, **frameinfo)

            # Is there a memo attached to this file?
            self.get_memo(frameid, d)

            if d.status != 'RS':
                d.status = 'R'

            self.output_line(d)
            return ro.OK


    def in_stars(self, frameid, vals):
        """Called when the _frameid_ is registered in STARS."""

        with self.lock:
            d = self._getframe(frameid)
            d.status = 'RS'

            self.output_line(d)
            return ro.OK

    
# END
