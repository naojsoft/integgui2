#
# E. Jeschke
#

import time

from ginga.gw import Widgets, Viewers

from . import common
from . import Page


class ObsInfoPage(Page.ButtonPage):

    def __init__(self, frame, name, title):

        super().__init__(frame, name, title)

        self.logger = common.view.logger

        # where we store updates
        self.obsdict = {}
        for key in ('OBSINFO1', 'OBSINFO2', 'OBSINFO3', 'OBSINFO4', 'OBSINFO5',
                    'TIMER', 'PROP-ID'):
            self.obsdict[key] = ''

        # rgb triplets we use
        self.black = (0.0, 0.0, 0.0)
        self.blue  = (0.0, 0.0, 1.0)
        self.green = (0.0, 0.5, 0.0)
        self.white = (1.0, 1.0, 1.0)
        self.orange = (0.824, 0.412, 0.1176)

        zi = Viewers.CanvasView(logger=self.logger)
        #zi.set_desired_size(self._wd, self._ht)
        zi.scale_to(1.0, 1.0)
        zi.set_bg(*self.white)
        zi.show_pan_mark(False)
        self._viewer = zi

        bd = zi.get_bindings()
        bd.enable(pan=False, zoom=False, flip=False, rotate=False)

        iw = Viewers.GingaScrolledViewerWidget(zi)
        iw.scroll_bars(horizontal='off', vertical='off')
        #iw.resize(self._wd, self._ht)
        self.content.add_widget(iw, stretch=1)

        # create drawing area
        self.canvas = zi.get_canvas()
        self.dc = self.canvas.get_draw_classes()

        self.items = {
            'prop-id': self.dc.Text(300, 20, text='', font="Sans;normal;bold",
                                    fontsize=18, color=self.black,
                                    coord='window'),
            'timer': self.dc.Text(550, 270, text='', font="Sans;normal;bold",
                                  fontsize=150, color=self.orange,
                                  coord='window'),
            'obsinfo1': self.dc.Text(10, 75, text='', font="Roboto;italic;bold",
                                     fontsize=48, color=self.blue,
                                     coord='window'),
            'obsinfo2': self.dc.Text(250, 120, text='',
                                     font="Roboto;italic;bold",
                                     fontsize=42, color=self.green,
                                     coord='window'),
            'obsinfo3': self.dc.Text(10, 160, text='',
                                     font="Roboto;italic;bold",
                                     fontsize=24, color=self.black,
                                     coord='window'),
            'obsinfo4': self.dc.Text(250, 190, text='',
                                     font="Roboto;italic;bold",
                                     fontsize=24, color=self.black,
                                     coord='window'),
            'obsinfo5': self.dc.Text(500, 160, text='',
                                     font="Roboto;italic;bold",
                                     fontsize=24, color=self.black,
                                     coord='window'),
            }
        for item in self.items.values():
            self.canvas.add(item, redraw=True)

        menu = self.add_pulldownmenu("Page")

        # Add items to the menu
        item = menu.add_name("Cancel Timer")
        item.add_callback("activated", lambda w: self.cancel_timer())

        #self.add_close()
        item = menu.add_name("Close")
        # currently disabled
        item.set_enabled(False)
        item.add_callback("activated", lambda w: self.close())

    def draw(self):
        for name in ['prop-id', 'timer', 'obsinfo1', 'obsinfo2', 'obsinfo3',
                     'obsinfo4', 'obsinfo5']:
            self.items[name].text = self.obsdict[name.upper()]

        self._viewer.redraw(whence=3)

    def update_obsinfo(self, obsdict):

        self.logger.debug("obsinfo update: %s" % str(obsdict))
        self.obsdict.update(obsdict)

        if 'TIMER_SEC' in obsdict:
            self.set_timer(obsdict['TIMER_SEC'])

        self.draw()

    def cancel_timer(self):
        self.obsdict['TIMER'] = ''
        self.draw()

    def set_timer(self, val):
        self.logger.debug("val = %s" % str(val))
        with common.view.lock:
            timer = common.view._obs_timer
        if timer is None:
            self.cancel_timer()
            return
        timer.data.obsinfo = self
        self.update_timer(float(val))

    def update_timer(self, secs):
        diff = max(0, int(round(secs)))
        self.logger.debug("timer: %d sec" % diff)
        if diff == 0:
            self.obsdict['TIMER'] = ''
        else:
            self.obsdict['TIMER'] = str(diff).rjust(5)

        self.draw()
