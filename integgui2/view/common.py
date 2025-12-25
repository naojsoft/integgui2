#
# common.py -- common module for IntegGUI view
#
# E. Jeschke
#
import os.path
import re

from g2base import Bunch

# Top directory to look for stuff
topprocdir = os.path.join(os.environ['HOME'], 'Procedure')

color_blue = '#cae1ff'     # pale blue
color_green = '#c1ffc1'     # pale green
color_yellow = '#fafad2'     # cream
#color_white = 'whitesmoke'
color_white = 'white'

color_bg = 'light grey'

# color objects used to set widgets dynamically
launcher_colors = Bunch.Bunch(error = 'salmon',
                              done = 'skyblue',
                              normal = '#dcdad5',
                              executing =  'palegreen',

                              #execbtn = 'royalblue',
                              #execbtn = 'steelblue1',
                              execbtn = '#82a8db',
                              cancelbtn = 'palevioletred',
                              killbtn = 'salmon',

                              badtags = 'red1')

# Colors for embedded terminals
terminal_colors = Bunch.Bunch(fg='black', bg='white')

# Colors used in the OpePage
decorative_tags = [
    ('comment3', Bunch.Bunch(foreground='indian red')),
    ('comment2', Bunch.Bunch(foreground='saddle brown')),
    ('comment1', Bunch.Bunch(foreground='dark green')),
    ('varref', Bunch.Bunch(foreground='royalblue')),
    ('badref', Bunch.Bunch(foreground='darkorange')),
    ]

# Colors used in the QueuePage
queue_tags = [
    ('normal', Bunch.Bunch(foreground='black')),
    ('comment3', Bunch.Bunch(foreground='indian red')),
    ('comment2', Bunch.Bunch(foreground='saddle brown')),
    ('comment1', Bunch.Bunch(foreground='dark green')),
    ('badref', Bunch.Bunch(foreground='red1')),
    ('selected', Bunch.Bunch(background='pink1')),
    ('cursor', Bunch.Bunch(background='#bf94e3')),
    ]

# Colors used in the OpePage for execution
execution_tags = [
    ('queued', Bunch.Bunch(background='lightyellow2')),
    ('executing', Bunch.Bunch(background='palegreen')),
    ('done',     Bunch.Bunch(foreground='blue2')),
    ('error',   Bunch.Bunch(foreground='red')),
    ]

# Colors used in the LogPage
log_tags = [
    ('error', Bunch.Bunch(foreground='red', background='lightyellow')),
    ('cancel', Bunch.Bunch(foreground='orange3')),
    ('normal', Bunch.Bunch(foreground='black')),
    ]

# If a log message matches one of these regexes, then color it.
# Tags are defined in the log_tags above
error_regexes = [
    (re.compile(r'^.*\|\sE\s\|.*$'), ['error']),
    (re.compile(r'^.*(error|exception).*$', re.I), ['error']),
    ]

# Colors used in the DirectoryPage
directory_tags = [
    ('normal', Bunch.Bunch(foreground='black')),
    ('executable', Bunch.Bunch(foreground='dark green')),
    ('directory',  Bunch.Bunch(foreground='blue2')),
    ('cursor',  Bunch.Bunch(foreground='yellow', background='dark green')),
    ]

# colors used in the SkMonitorPage
monitor_tags = Bunch.Bunch(
    code=Bunch.Bunch(foreground='black'),
    task_start=Bunch.Bunch(foreground='black', background='palegreen'),
    cmd_time=Bunch.Bunch(foreground='brown', background='palegreen'),
    ack_time=Bunch.Bunch(foreground='green4', background='palegreen'),
    end_time=Bunch.Bunch(foreground='blue1', background='white'),
    task_end=Bunch.Bunch(foreground='blue2', background='white'),
    error=Bunch.Bunch(foreground='red', background='lightyellow')
    )

# Define sounds used in IntegGUI
sound = Bunch.Bunch(success_executer='ogg/ocs/doorbell-1.ogg',
                    success_launcher='ogg/ocs/beep-02.ogg',
                    cancel_launcher='ogg/ocs/taskmgr_cancelled.ogg',
                    cancel_executer='ogg/ocs/taskmgr_cancelled.ogg',
                    tm_cancel='ogg/ocs/integgui2_cancel.ogg',
                    tm_kill='ogg/ocs/integgui2_kill.ogg',
                    tm_ready='ogg/ocs/taskmgr_ready.ogg',
                    failure_executer='ogg/ocs/hit-02.ogg',
                    failure_launcher='ogg/ocs/dishes-break-01.ogg',
                    break_executer='ogg/ocs/beep-04.ogg',
                    open_panel='ogg/ocs/beep-05.ogg',
                    close_panel='ogg/ocs/beep-05.ogg',
                    pause_toggle='ogg/ocs/beep-05.ogg',
                    bad_keystroke='ogg/ocs/beep-07.ogg',
                    sound_check='ogg/ocs/IntegGUI2SoundCheckOK.ogg',
                    )

# YUK...MODULE-LEVEL GLOBAL VARIABLES
view = None
controller = None

def set_view(pview):
    global view
    view = pview

def set_controller(pcontroller):
    global controller
    controller = pcontroller

def gui_do(method, *args, **kwdargs):
    return view.gui_do(method, *args, **kwdargs)

def gui_do_res(method, *args, **kwdargs):
    return view.gui_do_res(method, *args, **kwdargs)


class TagError(Exception):
    pass

class SelectionError(Exception):
    pass

def modify_bg(widget, color):
    # NOTE: there is a hard-coded hack here to force the background color
    # under hover status, because it seems to get reset if we just change
    # the .button type
    # TODO: hover => turn forestgreen
    widget.set_color(bg=color)
