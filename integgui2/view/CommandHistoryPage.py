#
# E. Jeschke
#

from ginga.gw import Widgets
from ginga.misc import Bunch

from . import Page


class CommandHistoryPage(Page.TablePage):

    def __init__(self, frame, name, title):

        super().__init__(frame, name, title)

        # columns to be shown in the table
        column_info = [dict(col_hdr="Start Time", col_key='start_time'),
                       dict(col_hdr="End Time", col_key='end_time'),
                       dict(col_hdr="Elapsed", col_key='elapsed'),
                       dict(col_hdr="Result", col_key='result'),
                       dict(col_hdr="Source", col_key='source'),
                       dict(col_hdr="Command", col_key='cmd_str'),
                       ]
        self.set_column_info(column_info, sort_idx=0, nesting=1)

        menu = self.add_pulldownmenu("Page")

        # For line coloring
        self.colortbl = {
            'OK': Bunch.Bunch(foreground='black'),
            'CN': Bunch.Bunch(foreground='darkyellow'),
            'NG': Bunch.Bunch(foreground='orangered'),
        }

    def update_command(self, cmdinfo):
        self.logger.debug("update command: %s" % str(cmdinfo))

        with self.lock:
            self.update_internal(cmdinfo)

            try:
                bnch = self.colortbl[cmdinfo.result]
            except Exception as e:
                self.logger.warning("Bad result in cmdinfo: %s" % (str(e)))
                bnch = self.colortbl['A']

            # TODO: update bg and or fg of row
