#
# FrameInfoPage.py -- an integgui2 page that shows information about frames
# 
#[ Eric Jeschke (eric@naoj.org) --
#  Last edit: Wed Dec 14 13:27:14 HST 2011
#]

import os, time
import gtk

import TablePage
import common

import Bunch


header = "FrameNo      State   Date_Obs     Ut       Exptime  ObsMode         Object          Disperser,Filters    [memo................]"

frame_tags = [
    ('A', 'normal', Bunch.Bunch(foreground='black', background='white',
                                icon='face-uncertain.svg')),
    ('X', 'transfer', Bunch.Bunch(background='palegreen',
                                icon='face-uncertain.svg')),
    ('R', 'received', Bunch.Bunch(foreground='dark green', background='white',
                                  icon='face-smile.svg')),
    ('RS', 'stars', Bunch.Bunch(foreground='blue2', background='white',
                                icon='face-laugh.svg')),
    ('RT', 'starstrans', Bunch.Bunch(foreground='darkgreen', background='white',
                                     icon='face-cool.svg')),
    ('RE', 'starserror', Bunch.Bunch(foreground='orange', background='white')),
    ('E', 'error', Bunch.Bunch(foreground='red', background='lightyellow',
                               icon='face-angry.svg')),
    ]

## frame_colors = {
##     'A': ('black', 'white'),
##     'X': ('black', 'palegreen'),
##     'R': ('dark green', 'white'),
##     'RS': ('blue2', 'white'),
##     'RT': ('dark green', 'white'),
##     'RE': ('orange', 'white'),
##     'E': ('red', 'white'),
##     }
    
class FrameInfoPage(TablePage.TablePage):

    def __init__(self, frame, name, title):

        super(FrameInfoPage, self).__init__(frame, name, title)

        # For line coloring
        self.colortbl = {}
        for status, tag, bnch in frame_tags:
            self.colortbl[status] = bnch

        columns = [("Name", 'name', 'text'),
                   ("", 'icon', 'icon'),
                   ("State", 'status', 'text'),
                   ("Date Obs", 'DATE-OBS', 'text'),
                   ("UT", 'UT-STR', 'text'),
                   ("Exptime", 'EXPTIME', 'text'),
                   ("ObsMode", 'OBS-MOD', 'text'),
                   ("Object", 'OBJECT', 'text'),
                   ("Disperser,Filters", 'FILTERS', 'text'),
                   ("Memo", 'MEMO', 'text'),
                   ]
        self.set_columns(columns)


    def update_frame(self, frameinfo):
        self.logger.info("UPDATE FRAME: %s" % str(frameinfo))

        frameid = frameinfo.frameid
        with self.lock:
            # set tags according to content of message
            try:
                colors = self.colortbl[frameinfo.status]
            except Exception, e:
                colors = self.colortbl['A']
            frameinfo['icon'] = colors.icon

            #cell.set_property('cell-background', color)
            ## frameinfo['name'] = "<span background='%s' foreground='%s'>%s</span>" % (
            ##     colors.background, colors.foreground, frameid)
            frameinfo['name'] = frameid

            self.update_table(frameid, frameinfo)

        
    def update_frames(self, framelist):

        # Delete all current frames
        self.listmodel = gtk.ListStore(object)
        self.rowidx = 0

        # add frames
        for frameinfo in framelist:
            del frameinfo['row']
            self.update_frame(frameinfo)

        self.treeview.set_model(self.listmodel)


##     def select_frame(self, w, evt):
##         with self.lock:
##             widget = self.tw
##             win = gtk.TEXT_WINDOW_TEXT
##             buf_x1, buf_y1 = widget.window_to_buffer_coords(win, evt.x, evt.y)
##             (startiter, coord) = widget.get_line_at_y(buf_y1)
##             (enditer, coord) = widget.get_line_at_y(buf_y1)
##             enditer.forward_to_line_end()
##             text = self.buf.get_text(startiter, enditer).strip()
##             frameno = text.split()[0]
##             line = startiter.get_line()
##             print "%d: %s" % (line, frameno)

##             # Load into a fits viewer page
##             common.view.load_frame(frameno)

## ##             try:
## ##                 self.image = self.datasrc[line]
## ##                 self.cursor = line
## ##                 self.update_img()
## ##             except IndexError:
## ##                 pass
            
##         return True
        

##     def load_frames(self):
##         if not self.buf.get_has_selection():
##             common.view.popup_error("No selection!")
##             return

##         # Get the range of text selected
##         first, last = self.buf.get_selection_bounds()
##         frow = first.get_line()
##         lrow = last.get_line()

##         # Clear the selection
##         self.buf.move_mark_by_name("insert", first)         
##         self.buf.move_mark_by_name("selection_bound", first)

##         # Break selection into individual lines
##         frames = []

##         for i in xrange(int(lrow)+1-frow):

##             row = frow+i

##             first.set_line(row)
##             last.set_line(row)
##             last.forward_to_line_end()

##             # skip comments and blank lines
##             line = self.buf.get_text(first, last).strip()
##             if len(line) == 0:
##                 continue

##             frameno = line.split()[0]
##             frames.append(frameno, [])

##         #print "Loading frames", frames
##         common.controller.load_frames(frames)

##     def save_journal(self):
##         homedir = os.path.join(os.environ['HOME'], 'Procedure')
##         filename = time.strftime("%Y%m%d-obs") + '.txt'

##         common.view.popup_save("Save frame journal", self._savefile,
##                                homedir, filename=filename)

##     def print_journal(self):
##         pass

#END
