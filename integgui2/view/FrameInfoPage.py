#
# E. Jeschke
#

from ginga.gw import Widgets
from ginga.misc import Bunch

from . import Page


class FrameInfoPage(Page.TablePage):

    def __init__(self, frame, name, title):

        super().__init__(frame, name, title)

        # columns to be shown in the table
        column_info = [dict(col_hdr="Frame ID", col_key='FRAMEID'),
                       dict(col_hdr="State", col_key='status'),
                       dict(col_hdr="Date Obs", col_key='DATE-OBS'),
                       dict(col_hdr="UT", col_key='UT'),
                       dict(col_hdr="Exp Time", col_key='EXPTIME'),
                       dict(col_hdr="Obs Mode", col_key='OBS-MOD'),
                       dict(col_hdr="Object", col_key='OBJECT'),
                       dict(col_hdr="Filters", col_key='FILTERS'),
                       dict(col_hdr="Memo", col_key='G_MEMO'),
                       ]
        self.set_column_info(column_info, sort_idx=0, nesting=1)

        # menu = self.add_pulldownmenu("Page")

        # For line coloring
        self.colortbl = {
            'A': Bunch.Bunch(foreground='black', background='white'),
            'X': Bunch.Bunch(background='palegreen'),
            'R': Bunch.Bunch(foreground='dark green', background='white'),
            'RS': Bunch.Bunch(foreground='blue2', background='white'),
            'RT': Bunch.Bunch(foreground='darkgreen', background='white'),
            'RE': Bunch.Bunch(foreground='orange', background='white'),
            'E': Bunch.Bunch(foreground='red', background='lightyellow'),
        }

    def update_frame(self, frameinfo):
        self.logger.debug("update frame: %s" % str(frameinfo))

        frameid = frameinfo.frameid
        with self.lock:
            self.update_internal(frameinfo)

            try:
                bnch = self.colortbl[frameinfo.status]
            except Exception as e:
                self.logger.warning("Bad status in frameinfo: %s" % (str(e)))
                bnch = self.colortbl['A']

            # TODO: update bg and or fg of row

    def update_frames(self, framelist):

        framelist = list(framelist)
        with self.lock:
            # add frames
            for frameinfo in framelist:
                self.update_frame(frameinfo)
