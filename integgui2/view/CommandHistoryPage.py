#
# E. Jeschke
#
import os, time

from ginga.misc import Bunch

from . import LogPage
from . import common


header = "Start     End       Elapsed   Res  Queue     Command"

# Format string used to render a command-history line.  The info dict comes
# from controller.log_history (t_start, t_end, t_elapsed, queue, result,
# cmdstr).
format_str = "%(t_start)-8.8s  %(t_end)-8.8s  %(t_elapsed)8.8s  %(result)-3.3s  %(queue)-8.8s  %(cmdstr)s"

# result code -> color attributes
history_tags = [
    ('OK', Bunch.Bunch(foreground='black')),
    ('CN', Bunch.Bunch(foreground='orange3')),
    ('NG', Bunch.Bunch(foreground='red', background='lightyellow')),
    ]


class CommandHistoryPage(LogPage.NotePage):

    def __init__(self, frame, name, title):

        super(CommandHistoryPage, self).__init__(frame, name, title)

        self.header = header
        self.format_str = format_str

        menu = self.add_pulldownmenu("Page")
        item = menu.add_name("Save history ...")
        item.add_callback("activated", lambda w: self.save_history())

        # For line coloring: result code -> tag name (same as the code)
        self.colortbl = {}
        for status, bnch in history_tags:
            self.addtag(status, **dict(bnch))
            self.colortbl[status] = status

        self.clear()

    def update_command(self, info):
        self.logger.debug("update command: %s" % str(info))

        with self.lock:
            text = self.format_str % info

            tag = self.colortbl.get(info.get('result'), 'OK')
            self.append(text + '\n', [tag])

    def clear(self):
        super(CommandHistoryPage, self).clear()

        # Re-create the header
        self.append(self.header + '\n', [])

    def save_history(self):
        homedir = os.path.join(os.environ['HOME'], 'Procedure')
        filename = time.strftime("%Y%m%d-history") + '.txt'

        common.view.popup_save("Save command history", self._savefile,
                               homedir, filename=filename)

#END
