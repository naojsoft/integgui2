#
# Eric Jeschke (eric@naoj.org) --
#

import os, time

from gi.repository import Gtk

from . import LogPage
from . import common

from g2base import Bunch


header = "FrameNo      State   Date_Obs     Ut       Exptime  ObsMode         Object          Disperser,Filters    [memo................]"

# Format string used to pass information to IntegGUI
format_str = "%(frameid)-12.12s %(status)5.5s  %(DATE-OBS)-10.10s %(UT-STR)-8.8s %(EXPTIME)10.10s  %(OBS-MOD)-15.15s %(OBJECT)-15.15s %(FILTERS)-20.20s %(MEMO)-s"

frame_tags = [
    ('A', 'normal', Bunch.Bunch(foreground='black', background='white')),
    ('X', 'transfer', Bunch.Bunch(background='palegreen')),
    ('R', 'received', Bunch.Bunch(foreground='dark green', background='white')),
    ('RS', 'stars', Bunch.Bunch(foreground='blue2', background='white')),
    ('RT', 'starstrans', Bunch.Bunch(foreground='darkgreen', background='white')),
    ('RE', 'starserror', Bunch.Bunch(foreground='orange', background='white')),
    ('E', 'error', Bunch.Bunch(foreground='red', background='lightyellow')),
    ]


class FrameInfoPage(LogPage.NotePage):

    def __init__(self, frame, name, title):

        super(FrameInfoPage, self).__init__(frame, name, title)

        self.header = header
        self.format_str = format_str

        # bottom buttons
        btns = Gtk.HButtonBox()
        btns.set_layout(Gtk.ButtonBoxStyle.START)
        btns.set_spacing(5)
        self.btns = btns

#         self.btn_load = Gtk.Button("Load")
#         self.btn_load.connect("clicked", lambda w: self.load_frames())
#         self.btn_load.show()
#         btns.pack_end(self.btn_load, False, False, 4)

        frame.pack_end(btns, False, False, 2)

#        menu = self.add_menu()
#        self.add_close()

        menu = self.add_pulldownmenu("Page")

        # item = Gtk.MenuItem(label="Print")
        # menu.append(item)
        # item.connect_object ("activate", lambda w: self.print_journal(),
        #                      "menu.Print")
        # item.show()

        # For line coloring
        self.colortbl = {}
        for status, tag, bnch in frame_tags:
            properties = {}
            properties.update(bnch)
            self.addtag(tag, **properties)

            self.colortbl[status] = tag

    def set_format(self, header, format_str):
        self.header = header
        self.format_str = format_str

    def update_frame(self, frameinfo):
        self.logger.debug("update frame: %s" % str(frameinfo))

        frameid = frameinfo.frameid
        with self.lock:
            text = self.format_str % frameinfo

            # set tags according to content of message
            try:
                tags = [ self.colortbl[frameinfo.status] ]
            except Exception as e:
                self.logger.warn("Bad status in frameinfo: %s" % (str(e)))
                tags = ['normal']

            #print(tags, frameinfo)
            if 'row' in frameinfo:
                row = frameinfo.row
                #common.update_line(self.buf, row, text)
                common.update_line(self.buf, row, text, tags=tags)

            else:
                end = self.buf.get_end_iter()
                frameinfo.row = end.get_line()

                self.append(text+'\n', tags)


    def update_frames(self, framelist):

        framelist = list(framelist)
        with self.lock:
            # Delete frames text
            start, end = self.buf.get_bounds()
            self.buf.delete(start, end)

            # Create header
            self.append(self.header + '\n', [])
            row = 1

            # add frames
            for frameinfo in framelist:
                frameinfo.row = row
                row += 1
                self.update_frame(frameinfo)


    def select_frame(self, w, evt):
        with self.lock:
            widget = self.tw
            win = Gtk.TextWindowType.TEXT
            buf_x1, buf_y1 = widget.window_to_buffer_coords(win, evt.x, evt.y)
            (startiter, coord) = widget.get_line_at_y(buf_y1)
            (enditer, coord) = widget.get_line_at_y(buf_y1)
            enditer.forward_to_line_end()
            text = self.buf.get_text(startiter, enditer, True).strip()
            frameno = text.split()[0]
            line = startiter.get_line()
            print("%d: %s" % (line, frameno))

            #self._select_frames = [frameno]

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

        for i in range(int(lrow) + 1 - frow):

            row = frow+i

            first.set_line(row)
            last.set_line(row)
            last.forward_to_line_end()

            # skip comments and blank lines
            line = self.buf.get_text(first, last, True).strip()
            if len(line) == 0:
                continue

            frameno = line.split()[0]
            frames.append(frameno, [])

        common.controller.load_frames(frames)

    def clear(self):
        super(FrameInfoPage, self).clear()

        # Create header
        self.append(self.header + '\n', [])

    def save_journal(self):
        homedir = os.path.join(os.environ['HOME'], 'Procedure')
        filename = time.strftime("%Y%m%d-obs") + '.txt'

        common.view.popup_save("Save frame journal", self._savefile,
                               homedir, filename=filename)

    def print_journal(self):
        pass

#END
