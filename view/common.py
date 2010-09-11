#
# common.py -- common module for IntegGUI view
#
#[ Eric Jeschke (eric@naoj.org) --
#  Last edit: Fri Sep 10 16:26:07 HST 2010
#]
import gtk

import Bunch

color_blue = '#cae1ff'     # pale blue
color_green = '#c1ffc1'     # pale green
color_yellow = '#fafad2'     # cream
#color_white = 'whitesmoke'
color_white = 'white'

color_bg = 'light grey'

# Gtk color objects used to set widgets dynamically
launcher_colors = Bunch.Bunch(error = gtk.gdk.color_parse('salmon'),
                              done = gtk.gdk.color_parse('skyblue'),
                              normal = gtk.gdk.color_parse('#dcdad5'),
                              executing =  gtk.gdk.color_parse('palegreen'),

                              #execbtn = gtk.gdk.color_parse('royalblue'),
                              #execbtn = gtk.gdk.color_parse('steelblue1'),
                              execbtn = gtk.gdk.color_parse('#82a8db'),
                              cancelbtn = gtk.gdk.color_parse('palevioletred'),
                              killbtn = gtk.gdk.color_parse('salmon'),

                              badtags = gtk.gdk.color_parse('red1'))

# Colors for embedded terminals
terminal_colors = Bunch.Bunch(fg=gtk.gdk.color_parse('black'),
                              bg=gtk.gdk.color_parse('white'),
                              )

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
    ('selected', Bunch.Bunch(background='pink1')),
    ('cursor', Bunch.Bunch(background='#bf94e3')),
    ]

execution_tags = [
    ('scheduled', Bunch.Bunch(background='lightyellow2')),
    ('executing', Bunch.Bunch(background='palegreen')),
    ('done',     Bunch.Bunch(foreground='blue2')),
    ('error',   Bunch.Bunch(foreground='red')),
    ]

# colors used in the SkMonitorPage
monitor_tags = Bunch.Bunch(
    code=Bunch.Bunch(foreground='black'),
    task_start=Bunch.Bunch(foreground='black', background='palegreen'),
    cmd_time=Bunch.Bunch(foreground='brown', background='palegreen'),
    ack_time=Bunch.Bunch(foreground='green4', background='palegreen'),
    end_time=Bunch.Bunch(foreground='blue1', background='palegreen'),
    task_end=Bunch.Bunch(foreground='blue2', background='white'),
    error=Bunch.Bunch(foreground='red', background='lightyellow')
    )

# Define sounds used in IntegGUI
sound = Bunch.Bunch(success_executer='doorbell.au',
                    #success_executer='beep-09.au',
                    success_launcher='beep-02.au',
                    #success_launcher='LAUNCHER_COMPLETE.au',
                    tm_kill='photon-torpedo.au',
                    tm_ready='tos-computer-03.au',
                    #fail_executer='splat.au',
                    failure_executer='hit-02.au',
                    failure_launcher='dishes-break-01.au',
                    break_executer='beep-04.au',
                    #tags_toggle='tos-turboliftdoor.au',
                    tags_toggle='beep-07.au',
                    pause_toggle='beep-05.au',
                    bad_keystroke='beep-07.au',
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
    
def update_line(buf, row, text, tags=None):
    """Update a line of the text widget _tw_, defined by _row_,
    with the value _val_.
    """
    start = buf.get_start_iter()
    start.set_line(row)
    if start.get_line() == row:
        end = start.copy()
        end.forward_to_line_end()
    
        buf.delete(start, end)
    else:
        # append some rows so we can go to the correct row
        end = buf.get_end_iter()
        while end.get_line() <= row:
            buf.insert(end, '\n')
            end = buf.get_end_iter()

    if len(text) == 0:
        text = ' '

    res = start.set_line(row)
    if start.get_line() != row:
        print "Could not set line to %d !" % row

    if not tags:
        buf.insert(start, text)
    else:
        buf.insert_with_tags_by_name(start, text, *tags)

def change_text(page, tagname, **kwdargs):
    tag = page.tagtbl.lookup(tagname)
    if not tag:
        raise TagError("Tag not found: '%s'" % tagname)

    for key, val in kwdargs.items():
        tag.set_property(key,val)

    # Scroll the view to this area
    start, end = get_region(page.buf, tagname)
    page.tw.scroll_to_iter(start, 0.1)


def get_region(txtbuf, tagname):
    """Returns a (start, end) pair of Gtk text buffer iterators
    associated with this tag.
    """
    # Painfully inefficient and error-prone way to locate a tagged
    # region.  Seems gtk text buffers have tags, but no good way to
    # manipulate text associated with them efficiently.

    # Get the tag table associated with this text buffer
    tagtbl = txtbuf.get_tag_table()
    # Look up the tag
    tag = tagtbl.lookup(tagname)

    # Get text iters at beginning and end of buffer
    start, end = txtbuf.get_bounds()

    # Now search forward from beginning for first location of this
    # tag, and backwards from the end
    result = start.forward_to_tag_toggle(tag)
    if not result:
        raise TagError("Tag not found: '%s'" % tagname)
    result = end.backward_to_tag_toggle(tag)
    if not result:
        raise TagError("Tag not found: '%s'" % tagname)

    return (start, end)


def get_region_lines(txtbuf, tagname):
    start, end = get_region(txtbuf, tagname)

    if not start.starts_line():
        frow = start.get_line()
        start.set_line(frow)
    if not end.ends_line():
        end.forward_to_line_end()
    
    return (start, end)


def replace_text(page, tagname, textstr):
    txtbuf = page.buf
    start, end = get_region(txtbuf, tagname)
    txtbuf.delete(start, end)
    txtbuf.insert_with_tags_by_name(start, textstr, tagname)

    # Scroll the view to this area
    page.tw.scroll_to_iter(start, 0.1)


def clear_tags_region(buf, tags, start, end):
    for tag in tags:
        buf.remove_tag_by_name(tag, start, end)

def clear_tags(buf, tags):
    start, end = buf.get_bounds()
    for tag in tags:
        buf.remove_tag_by_name(tag, start, end)

def get_tv(widget):
    txtbuf = widget.get_buffer()
    startiter, enditer = txtbuf.get_bounds()
    text = txtbuf.get_text(startiter, enditer)
    return text

def append_tv(widget, text):
    txtbuf = widget.get_buffer()
    enditer = txtbuf.get_end_iter()
    txtbuf.place_cursor(enditer)
    txtbuf.insert_at_cursor(text)
    startiter = txtbuf.get_start_iter()
    txtbuf.place_cursor(startiter)
    enditer = txtbuf.get_end_iter()
    widget.scroll_to_iter(enditer, False, 0, 0)

def clear_tv(widget):
    txtbuf = widget.get_buffer()
    startiter = txtbuf.get_start_iter()
    enditer = txtbuf.get_end_iter()
    txtbuf.delete(startiter, enditer)

def clear_selection(widget):
    txtbuf = widget.get_buffer()
    insmark = txtbuf.get_insert()
    if insmark != None:
        insiter = txtbuf.get_iter_at_mark(insmark)
        txtbuf.select_range(insiter, insiter)
    else:
        try:
            first, last = txtbuf.get_selection_bounds()
            txtbuf.select_range(first, first)
        except ValueError:
            return
        

class TagError(Exception):
    pass

class SelectionError(Exception):
    pass

#END
