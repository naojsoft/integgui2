#
# HandsetPage.py -- implements an Integgui2 handset
#
# E. Jeschke
#
import sys, os

from ginga.gw import Widgets
from ginga.misc import Bunch

import yaml

from . import common
from . import Page
from . import CommandObject

thisDir = os.path.split(sys.modules[__name__].__file__)[0]
icondir = os.path.abspath(os.path.join(thisDir, "..", "icons"))

compass_template = """
  %(n)s
%(e)s + %(w)s
  %(s)s
"""

class HandsetError(Exception):
    pass

class HandsetPage(Page.CommandPage):

    def __init__(self, frame, name, title):

        super(HandsetPage, self).__init__(frame, name, title)

        self.queueName = 'launcher'
        self.tm_queueName = 'launcher'
        self.paused = False

        scrolled_window = Widgets.ScrollArea()

        lw = Widgets.FixedLayout()
        lw.resize(420, 340)
        scrolled_window.set_widget(lw)

        self.content.add_widget(scrolled_window, stretch=1)

        self.lw = lw

        self.btn_cancel = Widgets.Button("Cancel")
        self.btn_cancel.add_callback("activated", lambda w: self.cancel())
        common.modify_bg(self.btn_cancel,
                         common.launcher_colors['cancelbtn'])
        self.leftbtns.add_widget(self.btn_cancel)

        ## menu = self.add_menu()
        ## self.add_close()

        menu = self.add_pulldownmenu("Page")

        # Add items to the menu
        item = menu.add_name("Reset")
        item.add_callback("activated", lambda w: self.reset())

        #self.add_close(side=Page.LEFT)
        #self.add_close()
        item = menu.add_name("Close")
        item.add_callback("activated", lambda w: self.close())

        self.build_handset()


    def _make_compass(self, n, s, e, w):
        txt = compass_template % {'n': n, 's': s, 'e': e, 'w': w }
        lbl = Widgets.Label(txt)
        lbl.set_font('DejaVu Sans Mono', 11)
        return lbl

    def _make_button(self, name):
        # make xpm image from inline data
        try:
            icon_file = icons[name]
            img = Widgets.Button(iconpath=icon_file)
        except Exception as e:
            img = Widgets.Button(name)

        return img

    def build_handset(self):
        self.arrow_stepval = 1.0

        widgets = {}

        # Place arrow buttons
        off_xv = 220
        off_yh = 150

        btns = widgets.setdefault('buttons', {})
        for x, y, name, axis, mult in ((off_xv, off_yh-140, 'up3', 0, 10),
                                       (off_xv, off_yh-100, 'up2', 0, 3),
                                       (off_xv, off_yh-60, 'up1', 0, 1),
                                       (off_xv-170, off_yh, 'left3', 1, 10),
                                       (off_xv-130, off_yh, 'left2', 1, 3),
                                       (off_xv-90, off_yh, 'left1', 1, 1),
                                       (off_xv+80, off_yh, 'right1', 1, -1),
                                       (off_xv+120, off_yh, 'right2', 1, -3),
                                       (off_xv+160, off_yh, 'right3', 1, -10),
                                       (off_xv, off_yh+60, 'down1', 0, -1),
                                       (off_xv, off_yh+100, 'down2', 0, -3),
                                       (off_xv, off_yh+140, 'down3', 0, -10),
                                 ):
            btn = self._make_button(name)
            btn.add_callback('activated', self.arrowMove, axis, mult)
            btns[name] = btn
            self.lw.add_widget(btn, x, y)

        # Place entries
        ents = widgets.setdefault('entries', {})
        for x, y, width, name in ((off_xv-35, off_yh+5, 10, 'mainstep'),):
            ent = Widgets.TextEntry()
            #ent.set_alignment(1.0)
            ent.set_text("0")
            ent.resize(85, 20)
            ents[name] = ent
            self.lw.add_widget(ent, x, y)

        # Place spin buttons
        for x, y, name in ((20, 250, 'lspin'), (120, 250, 'rspin')):
            ent = Widgets.SpinBox(dtype=float)
            #ent.set_alignment(1.0)
            # this seems to force size
            ent.set_limits(-1000, 1000, 1)
            ents[name] = ent
            self.lw.add_widget(ent, x, y)

        # Place labels
        lbls = widgets.setdefault('labels', {})
        for x, y, txt, name in ((off_xv+45, 210+5, 'x1', 'x1'), (off_xv+45, 250+5, 'x3', 'x3'),
                                (off_xv+45, 290+5, 'x10', 'x10'),
                                (off_xv, off_yh-18, 'Step', 'mainstep'),
                                (off_xv-5, off_yh+35, 'arcsec', 'mainunit'),
                                (20, 30, 'Mode', 'mode'),
                                (20, 232, '+N/-S', 'lstep'),
                                (120, 232, '+E/-W', 'rstep'),
                                (20, 275, 'arcsec', 'lstepunit'),
                                (120, 275, 'arcsec', 'rstepunit')):
            lbl = Widgets.Label(txt)
            lbls[name] = lbl
            self.lw.add_widget(lbl, x, y)

        # Compass
        lbl = self._make_compass('N', 'S', 'E', 'W')
        lbls['compass'] = lbl
        self.lw.add_widget(lbl, off_xv+80, off_yh-120)

        # Place buttons
        btns = widgets['buttons']
        btn = Widgets.Button('Move')
        #btn.set_size(10, -1)
        btn.add_callback('activated', self.execute)
        btns['move'] = btn
        self.lw.add_widget(btn, 20, 300)

        # Mode drop-down
        cbox = Widgets.ComboBox()
        cbox.add_callback('activated', self.changeMode)
        btns['mode'] = cbox
        self.lw.add_widget(cbox, 20, 50)

        self.widgets = widgets

    def reset(self):
        # Reset button backgrounds
        for name in ('left1', 'left2', 'left3', 'up1', 'up2', 'up3',
                     'right1', 'right2', 'right3', 'down1', 'down2',
                     'down3', 'move'):
            btn = self.widgets['buttons'][name]
            common.modify_bg(btn, common.launcher_colors['normal'])

    def addModes(self, modes):
        cbox = self.widgets['buttons']['mode']

        # remove old labels
        cbox.clear()

        # add new labels
        self.modes = []
        for d in modes:
            assert isinstance(d, dict) and 'label' in d, \
                   HandsetError("Malformed handset mode: expected key 'modes': %s" % (
                str(d)))
            name = d['label']
            cbox.append_text(name)
            self.modes.append(d)

        cbox.set_index(0)

    def changeMode(self, w, i):
        # Combobox widget gives us an index
        assert i < len(self.modes), Exception("No modes loaded!")

        self.loadMode(self.modes[i])
        return True

    # Example of a mode ################
    ## label: "Default"
    ## stepvalue: 1.0
    ## arrows:
    ##     cmd: MOVETELESCOPE OBE_ID=COMMON OBE_MODE=HANDSET OFFSET_MODE=RELATIVE_ARROW
    ##     dec: [ DELTA_DEC, arcsec, "N", "S", 0 ]
    ##     ra : [  DELTA_RA, arcsec, "E", "W", 0 ]
    ## button:
    ##     cmd: MOVETELESCOPE OBE_ID=COMMON OBE_MODE=HANDSET OFFSET_MODE=RELATIVE
    ##     dec: [ DELTA_DEC, arcsec, "+N", "-S", 0.0 ]
    ##     ra : [  DELTA_RA, arcsec, "+E", "-W", 0.0 ]
    ##
    def loadMode(self, d):
        self.reset()
        self.logger.info("Loading handset mode '%s'" % d['label'])

        try:
            for key in ('arrows', 'button'):
                assert key in d, \
                       HandsetError("Malformed handset mode: expected key '%s': %s" % (
                    key, str(d)))

            # Process arrow info
            info = d['arrows']
            for key in ('cmd', 'dec', 'ra', 'unit', 'step'):
                assert key in info, \
                       HandsetError("Malformed handset mode: expected key '%s': %s" % (
                    key, str(info)))

            for key in ('dec', 'ra'):
                tup = info[key]
                assert isinstance(tup, list) and (len(tup) == 3), \
                       HandsetError("Malformed handset mode: key '%s': %s" % (
                    key, str(tup)))

            self.stepval = info['step']

            # Set central entry widget to step value
            mainstep = self.widgets['entries']['mainstep']
            mainstep.set_text(str(self.stepval))

            # Get number of decimal places in step value
            s = str(self.stepval)
            if not '.' in s:
                numdigits = 0
            else:
                xx, dec = s.split('.')
                numdigits = len(dec)

            # Adjust spin widgets to step value
            lspin = self.widgets['entries']['lspin']
            lspin.set_decimals(numdigits)
            #lspin.set_limits(self.stepval, self.stepval*3)
            rspin = self.widgets['entries']['rspin']
            rspin.set_decimals(numdigits)
            #rspin.set_limits(self.stepval, self.stepval*3)

            (decvar, n, s) = info['dec']
            (ravar,  e, w) = info['ra']

            # save variable info for later use by command
            self.arrow_info = Bunch.Bunch(cmd=info['cmd'],
                                          dec_var=decvar, ra_var=ravar)

            # set main units label
            self.widgets['labels']['mainunit'].set_text(info['unit'])
            # set compass label
            txt = compass_template % {'n': n, 's': s, 'e': e, 'w': w }
            self.widgets['labels']['compass'].set_text(txt)

            info = d['button']
            for key in ('cmd', 'dec', 'ra'):
                assert key in info, \
                       HandsetError("Malformed handset mode: expected key '%s': %s" % (
                    key, str(info)))

            for key in ('dec', 'ra'):
                tup = info[key]
                assert isinstance(tup, list) and (len(tup) == 5), \
                       HandsetError("Malformed handset mode: key '%s': %s" % (
                    key, str(tup)))

            (decvar, decunit, n, s, decval) = info['dec']
            (ravar,  raunit, e, w, raval) = info['ra']

            self.widgets['labels']['lstep'].set_text('%s/%s' % (n, s))
            self.widgets['labels']['rstep'].set_text('%s/%s' % (e, w))
            self.widgets['labels']['lstepunit'].set_text(decunit)
            self.widgets['labels']['rstepunit'].set_text(raunit)
            lspin.set_value(decval)
            rspin.set_value(raval)

            # save variable info for later use by command
            self.button_info = Bunch.Bunch(cmd=info['cmd'],
                                           dec_var=decvar, ra_var=ravar)

        except Exception as e:
            self.logger.error("error loading handset: %s" % (str(e)))
            raise e

    def load(self, buf):
        d = yaml.safe_load(buf)

        assert isinstance(d, dict) and 'modes' in d, \
               HandsetError("Malformed handset def: expected key 'modes': %s" % (
            str(d)))

        self.addModes(d['modes'])

        if 'tabname' in d:
            self.setLabel(d['tabname'])


    def arrowMove(self, w, axis, mult):
        """Callback when an arrow button is pressed.
        """
        info = self.arrow_info
        stepval = self.widgets['entries']['mainstep'].get_text()
        try:
            stepval = float(stepval)
        except Exception as e:
            common.view.popup_error("Bad step value '%s': %s" % (
                    stepval, str(e)))
            return

        self.logger.debug("Move by arrow: axis=%d mult=%f" % (axis, mult))
        val = stepval * mult
        if axis == 0:
            var = info.dec_var
        else:
            var = info.ra_var

        cmdstr = "%s %s=%s" % (info.cmd, var, val)
        self.logger.info("Move by arrow: %s" % (cmdstr))

        try:
            # tag the text so we can manipulate it later
            cmdObj = HandsetCommandObject('hs%d', self.queueName,
                                      self.logger, w, cmdstr)

            common.controller.execOne(cmdObj, 'launcher')
        except Exception as e:
            common.view.popup_error(str(e))


    def execute(self, w):
        """Callback when the 'Move' button is pressed.
        """
        lspin = self.widgets['entries']['lspin']
        rspin = self.widgets['entries']['rspin']

        decoff = lspin.get_value()
        raoff = rspin.get_value()

        info = self.button_info
        cmdstr = "%s %s=%s %s=%s" % (info.cmd, info.dec_var, decoff,
                                     info.ra_var, raoff)
        self.logger.info("Move by button: %s" % (cmdstr))

        try:
            # tag the text so we can manipulate it later
            cmdObj = HandsetCommandObject('hs%d', self.queueName,
                                      self.logger, w, cmdstr)

            common.controller.execOne(cmdObj, 'launcher')
        except Exception as e:
            common.view.popup_error(str(e))


class HandsetCommandObject(CommandObject.CommandObject):

    def __init__(self, format, queueName, logger, widget, cmdstr):
        self.widget = widget
        self.cmdstr = cmdstr

        super(HandsetCommandObject, self).__init__(format, queueName, logger)

    def get_preview(self):
        return self.get_cmdstr()

    def get_cmdstr(self):
        return self.cmdstr

    def _show_state(self, state):
        if state == 'queued':
            state = 'normal'

        common.modify_bg(self.widget, common.launcher_colors[state])

    def mark_status(self, txttag):
        # This MAY be called from a non-gui thread
        common.gui_do(self._show_state, txttag)


##### Icon data #####

icons = {name: os.path.join(icondir, name + '.png')
         for name in ['left1', 'left2', 'left3', 'right1', 'right2', 'right3',
                      'up1', 'up2', 'up3', 'down1', 'down2', 'down3']}
#END
