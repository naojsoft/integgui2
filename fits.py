# 
# Eric Jeschke (eric@naoj.org)
#

import threading

import remoteObjects as ro
import remoteObjects.Monitor as Monitor
import Bunch
from astro.frame import Frame

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

    def update_framelist(self):
        with self.lock:
            return self.gui.update_frames(self.framelist)

    def output_line(self, frameinfo):
        #print "output line: %s" % str(frameinfo)
        self.gui.update_frame(frameinfo)

    def clear(self):
        with self.lock:
            self.framecache = {}
            self.framelist = []
            self.update_framelist()
        
    def _getframe(self, frameid, **kwdargs):
        with self.lock:
            if self.framecache.has_key(frameid):
                d = self.framecache[frameid]
                d.update(kwdargs)
                return d

            # Create a new entry
            dct = dict.fromkeys(headers, '')
            dct['frameid'] = frameid
            dct['status'] = 'A'
            
            d = Bunch.Bunch(dct)
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


    def frame_allocated(self, frameid):
        """Called when _frameid_ is allocated.
        """
        with self.lock:
            # Create a new entry
            d = self._getframe(frameid)
            # self.gui adds 'row' item--if not present, update gui
            if not d.has_key('row'):
                self.output_line(d)


    def transfer_started(self, frameid):
        """Called when the _frameid_ transfer from the OBCP has been
        initiated.
        """
        with self.lock:
            d = self._getframe(frameid)
            # if necessary change status and update gui
            if d.status == 'A':
                d.status = 'X'
                self.output_line(d)


    def transfer_done(self, frameid, status):
        """Called when the _frameid_ transfer from the OBCP has
        finished.  status==0 indicates success, error otherwise.
        """
        with self.lock:
            d = self._getframe(frameid)
            # if necessary change status and update gui
            if d.status in ('X', 'A'):
                if status == 0:
                    # received
                    d.status = 'R'
                else:
                    # error
                    d.status = 'E'

                self.output_line(d)


    def fits_info(self, frameid, frameinfo):
        """Called when there is some information about the frame.
        """
        with self.lock:
            #d = self._getframe(frameid, **frameinfo)
            d = self._getframe(frameid)
            if d['OBJECT'] == '':
                d.update(frameinfo)
                self.output_line(d)
            return ro.OK


    def in_stars(self, frameid, status):
        """Called when the _frameid_ has finished a transaction with STARS."""

        with self.lock:
            d = self._getframe(frameid)
            d.status = 'R' + status[0]

            self.output_line(d)
            return ro.OK

    
    def frameSvc_hdlr(self, frameid, vals):
        """Called with information provided by the frame service."""

        if vals.has_key('time_alloc'):
            self.frame_allocated(frameid)


    def INSint_hdlr(self, frameid, vals):
        """Called with information provided by the instrument interface."""
        
        if Monitor.has_keys(vals, ['done', 'time_done', 'status',
                                   'filepath']):
            self.transfer_done(frameid, vals['status'])

        elif vals.has_key('time_start'):
            self.transfer_started(frameid)


    def Archiver_hdlr(self, frameid, vals):
        """Called with information provided by the Archiver."""
        
        # TODO: check vals['PROP-ID'] against propid for this
        # integgui before proceeding
        self.fits_info(frameid, vals)


    def STARSint_hdlr(self, frameid, vals):
        """Called with information provided by the STARS interface."""

        # TODO: integgui shouldn't have to understand this level of
        # the stars protocol
        if Monitor.has_keys(vals, ['done', 'time_done']):
            if Monitor.has_keys(vals, ['errorclass', 'msg']):
                # --> there was an error in the STARS interface
                self.in_stars(frameid, 'E')
            elif (Monitor.has_keys(vals, ['end_result', 'end_status1',
                                       'end_status2']) and
                (vals['end_result'] == 0) and
                (vals['end_status1'] == 0) and
                (vals['end_status2'] == 0)):
                # --> STARS may have the file
                self.in_stars(frameid, 'T')


class HSC_IntegGUINotify(IntegGUINotify):

    def __init__(self, gui, fitsdir):
        super(HSC_IntegGUINotify, self).__init__(gui, fitsdir)

        header = "FrameNo      State  Cnt   Date_Obs     Ut       Exptime  ObsMode         Object          Disperser,Filters    [memo................]"

        # Format string used to pass information to IntegGUI
        format_str = "%(frameid)-12.12s %(status)5.5s  %(count_xfers)03d  %(DATE-OBS)-10.10s %(UT-STR)-8.8s %(EXPTIME)10.10s  %(OBS-MOD)-15.15s %(OBJECT)-15.15s %(FILTERS)-20.20s %(MEMO)-s"

        gui.set_format(header, format_str)

        # Total number of frames in exposure
        self.total_count = dict(SUP=10, HSC=112)

        
    def get_hsc_expid(self, frameid):
        """
        Get HSC exposure id from a individual frame id.
        """
        frame = Frame(frameid)
        if frame.inscode == 'HSC':
            # HSC allocates 200 frameids per exposure and uses around 112
            # of them.  This is too many to track individually, so we convert
            # to a single 'exposure id' and track that.
            frame.number = (frame.number // 200) * 200
            return str(frame)

        elif frame.inscode == 'SUP':
            # SPCAM allocates 10 frameids per exposure.
            frame.number = (frame.number // 10) * 10
            return str(frame)

        else:
            # other instruments: e.g. VGW, etc.
            return frameid
        

    def _getframe(self, frameid, **kwdargs):

        frameid = self.get_hsc_expid(frameid)
        
        with self.lock:
            d = super(HSC_IntegGUINotify, self)._getframe(frameid, **kwdargs)
            if not d.has_key('count_xfers'):
                d.count_xfers = 0
            if not d.has_key('count_stars'):
                d.count_stars = 0
            return d
            

    def transfer_done(self, frameid, status):

        total_count = self.total_count.get(frameid[0:3], 1)
        with self.lock:
            d = self._getframe(frameid)
            if d.status in ('X', 'A'):
                if status == 0:
                    d.count_xfers += 1
                    if d.count_xfers == total_count:
                        d.status = 'R'
                else:
                    d.status = 'E'

            self.output_line(d)


    def in_stars(self, frameid, status):

        total_count = self.total_count.get(frameid[0:3], 1)
        with self.lock:
            d = self._getframe(frameid)
            if total_count == 1:
                # Non-multiple frame case
                d.status = 'R' + status[0]
                self.output_line(d)
            elif status == 'T':
                d.count_stars += 1
                if d.count_stars == total_count:
                    d.status = 'RT'
                    self.output_line(d)
            return ro.OK

    
# END
