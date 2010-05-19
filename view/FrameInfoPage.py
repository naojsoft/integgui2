# remove once we're certified on python 2.6
from __future__ import with_statement

import gtk

import Page
import common


header = "FrameNo      State   Date_Obs     Ut       Exptime  ObsMode         Object          Disperser,Filters    [memo................]"

# Format string used to pass information to IntegGUI
format_str = "%(frameid)-12.12s %(status)5.5s  %(DATE-OBS)-10.10s %(UT-STR)-8.8s %(EXPTIME)10.10s  %(OBS-MOD)-15.15s %(OBJECT)-15.15s %(FILTERS)-20.20s %(MEMO)-s\n"


class FrameInfoPage(Page.Page):

    def __init__(self, frame, name, title):

        super(FrameInfoPage, self).__init__(frame, name, title)

        scrolled_window = gtk.ScrolledWindow()
        scrolled_window.set_border_width(2)

        scrolled_window.set_policy(gtk.POLICY_AUTOMATIC,
                                   gtk.POLICY_AUTOMATIC)

        tw = gtk.TextView()
        scrolled_window.add_with_viewport(tw)
        tw.show()
        scrolled_window.show()

        frame.pack_start(scrolled_window, expand=True, fill=True)

        tw.set_editable(False)
        tw.set_wrap_mode(gtk.WRAP_NONE)
        tw.set_left_margin(4)
        tw.set_right_margin(4)

        self.tw = tw
        self.buf = tw.get_buffer()

##         # bottom buttons
##         btns = gtk.HButtonBox()
##         btns.set_layout(gtk.BUTTONBOX_START)
##         btns.set_spacing(5)
##         self.btns = btns

##         self.btn_close = gtk.Button("Close")
##         self.btn_close.connect("clicked", lambda w: self.close())
##         self.btn_close.show()
##         btns.pack_end(self.btn_close, padding=4)

##         frame.pack_end(btns, fill=False, expand=False, padding=2)


    def update_frame(self, frameinfo):
        self.logger.debug("UPDATE FRAME: %s" % str(frameinfo))

        frameid = frameinfo.frameid
        with self.lock:
            text = format_str % frameinfo

            if hasattr(frameinfo, 'row'):
                row = frameinfo.row
                common.update_line(self.buf, row, text)
                #update_line(self.buf, row, text, tags=[frameid])

            else:
                end = self.buf.get_end_iter()
                row = end.get_line()
                #self.buf.create_tag(frameid, foreground="black")
                frameinfo.row = row
                self.buf.insert(end, text)
                #self.buf.insert_with_tags_by_name(end, text, [frameid])

        
    def update_frames(self, framelist):

        # Delete frames text
        start, end = self.buf.get_bounds()
        self.buf.delete(start, end)
        
        # Create header
        self.buf.insert(start, header)

        # add frames
        for frameinfo in framelist:
            self.update_frame(frameinfo)



#END
