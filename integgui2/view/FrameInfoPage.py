#
# E. Jeschke
#
import os, time

from ginga.misc import Bunch

from . import LogPage
from . import common


header = "FrameNo      State   Date_Obs     Ut       Exptime  ObsMode         Object          Disperser,Filters    [memo................]"

# Format string used to render a frame info line
format_str = "%(frameid)-12.12s %(status)5.5s  %(DATE-OBS)-10.10s %(UT-STR)-8.8s %(EXPTIME)10.10s  %(OBS-MOD)-15.15s %(OBJECT)-15.15s %(FILTERS)-20.20s %(MEMO)-s"

# status code -> (tag name, color attributes)
frame_tags = [
    ('A', 'normal', Bunch.Bunch(foreground='black', background='white')),
    ('X', 'transfer', Bunch.Bunch(background='palegreen')),
    ('R', 'received', Bunch.Bunch(foreground='darkgreen', background='white')),
    ('RS', 'stars', Bunch.Bunch(foreground='blue2', background='white')),
    ('RT', 'starstrans', Bunch.Bunch(foreground='darkgreen', background='white')),
    ('RE', 'starserror', Bunch.Bunch(foreground='orange', background='white')),
    ('E', 'error', Bunch.Bunch(foreground='red', background='lightyellow')),
]


class FrameInfoPage(LogPage.NotePage):

    def __init__(self, frame, name, title):

        super().__init__(frame, name, title)

        self.header = header
        self.format_str = format_str

        menu = self.add_pulldownmenu("Page")
        item = menu.add_name("Save journal ...")
        item.add_callback("activated", lambda w: self.save_journal())

        # clicking a frame line reports/loads the frame
        self.tw.add_callback('line-clicked', self.select_frame)

        # For line coloring: status code -> tag name
        self.colortbl = {}
        for status, tag, bnch in frame_tags:
            self.addtag(tag, **dict(bnch))
            self.colortbl[status] = tag

        self.clear()

    def set_format(self, header, format_str):
        self.header = header
        self.format_str = format_str

    def update_frame(self, frameinfo):
        self.logger.debug("update frame: %s" % str(frameinfo))

        with self.lock:
            text = self.format_str % frameinfo

            # set tags according to the frame's status
            try:
                tags = [self.colortbl[frameinfo.status]]
            except Exception as e:
                self.logger.warning("Bad status in frameinfo: %s" % (str(e)))
                tags = ['normal']

            if 'row' in frameinfo:
                # in-place update of a previously displayed frame
                common.update_line(self.tw, frameinfo.row, text, tags=tags)
            else:
                frameinfo.row = self.tw.get_end_lineno()
                self.append(text + '\n', tags)

    def update_frames(self, framelist):

        framelist = list(framelist)
        with self.lock:
            # clear (re-adds the header) and repopulate
            self.clear()

            row = 1
            for frameinfo in framelist:
                frameinfo.row = row
                row += 1
                self.update_frame(frameinfo)

    def select_frame(self, w, lineno):
        # 'line-clicked' callback: report the frame on the clicked line
        with self.lock:
            start = self.tw.get_ref_line_start(lineno)
            end = self.tw.get_ref_line_end(lineno)
            text = self.tw.get_text_range(start, end).strip()
            if not text:
                return False
            frameno = text.split()[0]
            self.logger.debug("%d: %s" % (lineno, frameno))
            #self._select_frames = [frameno]
        return True

    def load_frames(self):
        bounds = self.tw.get_selection_bounds()
        if bounds is None:
            common.view.popup_error("No selection!")
            return
        first, last = bounds
        frow = first.get_line()
        lrow = last.get_line()

        # Clear the selection
        common.clear_selection(self.tw)

        # Break selection into individual lines
        frames = []
        for i in range(int(lrow) + 1 - frow):
            row = frow + i
            start = self.tw.get_ref_line_start(row)
            end = self.tw.get_ref_line_end(row)
            line = self.tw.get_text_range(start, end).strip()
            if len(line) == 0:
                continue
            frameno = line.split()[0]
            frames.append(frameno)

        common.controller.load_frames(frames)

    def clear(self):
        super().clear()

        # Re-create the header
        self.append(self.header + '\n', [])

    def save_journal(self):
        homedir = os.path.join(os.environ['HOME'], 'Procedure')
        filename = time.strftime("%Y%m%d-obs") + '.txt'

        common.view.popup_save("Save frame journal", self._savefile,
                               homedir, filename=filename)

#END
