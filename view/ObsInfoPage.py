# 
#[ Eric Jeschke (eric@naoj.org) --
#  Last edit: Tue May 18 10:19:46 HST 2010
#]

# remove once we're certified on python 2.6
from __future__ import with_statement

import gtk

import common
import Page


class ObsInfoPage(Page.Page):

    def __init__(self, frame, name, title):

        super(ObsInfoPage, self).__init__(frame, name, title)

        scrolled_window = gtk.ScrolledWindow()
        scrolled_window.set_border_width(2)

        scrolled_window.set_policy(gtk.POLICY_AUTOMATIC,
                                   gtk.POLICY_AUTOMATIC)

        tw = gtk.TextView()
        scrolled_window.add(tw)
        tw.show()
        scrolled_window.show()

        tw.set_editable(True)
        tw.set_wrap_mode(gtk.WRAP_NONE)
        tw.set_left_margin(4)
        tw.set_right_margin(4)

        frame.pack_start(scrolled_window, expand=True, fill=True)

        self.tw = tw
        self.buf = tw.get_buffer()

        start = self.buf.get_start_iter()
        self.buf.insert(start, ' \n' * 10)

        frame.pack_start(scrolled_window, fill=True, expand=True)


    def update_obsinfo(self, obsdict):

        self.logger.debug("obsinfo update: %s" % str(obsdict))

        if obsdict.has_key('PROP-ID'):
            common.update_line(self.buf, 1, 'Prop-Id: %s' % obsdict['PROP-ID'])
        if obsdict.has_key('TIMER_SEC'):
            self.set_timer(obsdict['TIMER_SEC'])
        
        offset = 2
        for i in xrange(1, 6):
            try:
                val = str(obsdict['OBSINFO%d' % i])
                row = i + offset
                print "updating row=%d val='%s'" % (row, val)
                common.update_line(self.buf, row, val)
            except KeyError:
                continue


    def set_timer(self, val):
        self.logger.debug("val = %s" % str(val))
        val = int(val)
        self.logger.debug("val = %d" % val)
        if val <= 0:
            return
        self.timer_val = val + 1
        self.logger.debug("timer_val = %d" % self.timer_val)
        # READ GLOBAL VAR
        self.timer_interval(view.w.root)


    def timer_interval(self):
        self.logger.debug("timer: %d sec" % self.timer_val)
        self.timer_val -= 1
        common.update_line(self.buf, 2, 'Timer: %s' % str(self.timer_val))
        if self.timer_val > 0:
            gobject.timeout_add(1000, self.timer_interval)
        else:
            # Do something when timer expires?
            pass
        

#END
