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

# Colors used in the OpePage.  These are the syntax-highlighting tags applied
# by OpePage.color(); comments are italicized to match the look the old Qt
# syntax highlighter produced.
decorative_tags = [
    ('comment3', Bunch.Bunch(foreground='indianred', italic=True)),
    ('comment2', Bunch.Bunch(foreground='saddlebrown', italic=True)),
    ('comment1', Bunch.Bunch(foreground='darkgreen', italic=True)),
    ('varref', Bunch.Bunch(foreground='royalblue')),
    ('badref', Bunch.Bunch(foreground='darkorange')),
    ]

# Colors used in the QueuePage
queue_tags = [
    ('normal', Bunch.Bunch(foreground='black')),
    ('comment3', Bunch.Bunch(foreground='indianred')),
    ('comment2', Bunch.Bunch(foreground='saddlebrown')),
    ('comment1', Bunch.Bunch(foreground='darkgreen')),
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
    ('executable', Bunch.Bunch(foreground='darkgreen')),
    ('directory',  Bunch.Bunch(foreground='blue2')),
    ('cursor',  Bunch.Bunch(foreground='yellow', background='darkgreen')),
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


# ------------------------------------------------------------------------
# Text-widget region / selection / scroll helpers.
#
# These are the module-level shims used by page code, expressed in terms of
# the unified TextSource widget API (refs + tag intervals + gutter icons),
# replacing the old GtkTextBuffer iter/mark/tag-table helpers.  The first
# argument is always a TextSource (ginga wrapper) widget.
# ------------------------------------------------------------------------

def get_region(tw, tagname):
    """Return a ``(start_ref, end_ref)`` pair spanning the named tag.

    Mirrors the old GTK ``get_region``: the span runs from the first
    occurrence of the tag to the last.  Raises ``TagError`` if the tag is
    not applied anywhere in the buffer.
    """
    region = tw.get_tag_region(tagname)
    if region is None:
        raise TagError("Tag not found: '%s'" % (tagname,))
    return region


def get_region_lines(tw, tagname):
    """Like ``get_region`` but expanded to whole lines: the start ref is
    moved to the beginning of its line and the end ref to the end of its
    line."""
    start, end = get_region(tw, tagname)
    start.to_line_start()
    end.to_line_end()
    return (start, end)


def clear_tags_region(tw, tags, start_ref, end_ref):
    """Remove each named tag in ``tags`` from the range
    ``[start_ref, end_ref)``."""
    for tag in tags:
        tw.remove_tag(tag, start_ref, end_ref)


def clear_tags(tw, tags):
    """Remove each named tag in ``tags`` from the entire buffer."""
    start, end = tw.get_ref_bounds()
    clear_tags_region(tw, tags, start, end)


def remove_all_marks(tw):
    """Remove all gutter marks/icons (the source-mark replacement)."""
    tw.clear_icons()


def clear_selection(tw):
    """Collapse any selection, leaving the cursor where it is."""
    if tw.has_selection():
        tw.set_cursor(tw.get_cursor())


def select_all(tw):
    """Select the entire buffer."""
    start, end = tw.get_ref_bounds()
    tw.set_selection_range(start, end)


def scroll_to_lineno(tw, lineno):
    """Scroll the widget so that ``lineno`` is visible."""
    return tw.scroll_to_lineno(lineno)


def get_end_lineno(tw):
    """Return the line number of the last line in the buffer."""
    return tw.get_end_lineno()


def update_line(tw, row, text, tags=None):
    """Replace the contents of line ``row`` (0-based) with ``text``,
    optionally applying ``tags``.  If ``row`` is past the last line the
    buffer is first padded with blank lines.
    """
    end_line = tw.get_end_lineno()
    if row > end_line:
        end = tw.get_ref_end()
        tw.insert_text(end, '\n' * (row - end_line))
    start = tw.get_ref_line_start(row)
    stop = tw.get_ref_line_end(row)
    tw.delete_range(start, stop)
    tw.insert_text(start, text, tags=tags)

def modify_bg(widget, color):
    # NOTE: there is a hard-coded hack here to force the background color
    # under hover status, because it seems to get reset if we just change
    # the .button type
    # TODO: hover => turn forestgreen
    widget.set_color(bg=color)
