# 
#[ Eric Jeschke (eric@naoj.org) --
#  Last edit: Tue May 18 13:02:33 HST 2010
#]

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
        scrolled_window.add(tw)
        tw.show()
        scrolled_window.show()

        frame.pack_start(scrolled_window, expand=True, fill=True)

        tw.set_editable(False)
        tw.set_wrap_mode(gtk.WRAP_NONE)
        tw.set_left_margin(4)
        tw.set_right_margin(4)
        #tw.connect("button-press-event", self.select_frame)

        self.tw = tw
        self.buf = tw.get_buffer()

        # bottom buttons
        btns = gtk.HButtonBox()
        btns.set_layout(gtk.BUTTONBOX_START)
        btns.set_spacing(5)
        self.btns = btns

        self.btn_load = gtk.Button("Load")
        self.btn_load.connect("clicked", lambda w: self.load_frames())
        self.btn_load.show()
        btns.pack_end(self.btn_load, padding=4)

##         self.btn_close = gtk.Button("Close")
##         self.btn_close.connect("clicked", lambda w: self.close())
##         self.btn_close.show()
##         btns.pack_end(self.btn_close, padding=4)

        frame.pack_end(btns, fill=False, expand=False, padding=2)


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


    def select_frame(self, w, evt):
        with self.lock:
            widget = self.tw
            win = gtk.TEXT_WINDOW_TEXT
            buf_x1, buf_y1 = widget.window_to_buffer_coords(win, evt.x, evt.y)
            (startiter, coord) = widget.get_line_at_y(buf_y1)
            (enditer, coord) = widget.get_line_at_y(buf_y1)
            enditer.forward_to_line_end()
            text = self.buf.get_text(startiter, enditer).strip()
            frameno = text.split()[0]
            line = startiter.get_line()
            print "%d: %s" % (line, frameno)

            # Load into a fits viewer page
            common.view.load_frame(frameno)

##             try:
##                 self.image = self.datasrc[line]
##                 self.cursor = line
##                 self.update_img()
##             except IndexError:
##                 pass
            
        return True
        

    def load_frames(self):
        if not self.buf.get_has_selection():
            common.view.popup_error("No selection!")
            return

        # Get the range of text selected
        first, last = self.buf.get_selection_bounds()
        frow = first.get_line()
        lrow = last.get_line()

        # Clear the selection
        self.buf.move_mark_by_name("insert", first)         
        self.buf.move_mark_by_name("selection_bound", first)

        # Break selection into individual lines
        frames = []

        for i in xrange(int(lrow)+1-frow):

            row = frow+i

            first.set_line(row)
            last.set_line(row)
            last.forward_to_line_end()

            # skip comments and blank lines
            line = self.buf.get_text(first, last).strip()
            if len(line) == 0:
                continue

            frameno = line.split()[0]
            frames.append(frameno)

        common.view.load_frames(frames)
        
#END
