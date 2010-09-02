# 
#[ Eric Jeschke (eric@naoj.org) --
#  Last edit: Wed Sep  1 20:21:09 HST 2010
#]

# remove once we're certified on python 2.6
from __future__ import with_statement

# Standard library imports
import sys
import re, time
import threading
import traceback

# Special library imports
import gtk

import Bunch
import remoteObjects as ro
import common
import Page


class SkMonitorPage(Page.Page):

    def __init__(self, frame, name, title):

        super(SkMonitorPage, self).__init__(frame, name, title)

        self.nb = gtk.Notebook()
        self.nb.set_tab_pos(gtk.POS_TOP)
        self.nb.set_scrollable(True)
        self.nb.set_show_tabs(True)
        self.nb.set_show_border(True)
        #self.nb.set_size_request(1000, 700)
        self.nb.show()

        frame.pack_start(self.nb, expand=True, fill=True,
                         padding=2)

        # Holds my pages
        self.pages = {}
        self.pagelist = []
        self.pagelimit = 10

        self.track = {}
        self.lock = threading.RLock()


    def insert_ast(self, tw, text):

        buf = tw.get_buffer()
        all_tags = set([])

        def insert(text, tags):

            loc = buf.get_end_iter()
            #linenum = loc.get_line()
            try:
                foo = text.index("<div ")

            except ValueError:
                buf.insert_with_tags_by_name(loc, text, *tags)
                return

            match = re.match(r'^\<div\sclass=([^\>]+)\>', text[foo:],
                             re.MULTILINE | re.DOTALL)
            if not match:
                buf.insert_with_tags_by_name(loc, 'ERROR 1: %s' % text, *tags)
                return

            num = int(match.group(1))
            regex = r'^(.*)\<div\sclass=%d\>(.+)\</div\sclass=%d\>(.*)$' % (
                num, num)
            #print regex
            match = re.match(regex, text, re.MULTILINE | re.DOTALL)
            if not match:
                buf.insert_with_tags_by_name(loc, 'ERROR 2: %s' % text, *tags)
                return

            buf.insert_with_tags_by_name(loc, match.group(1), *tags)

            serial_num = '%d' % num
            buf.create_tag(serial_num, foreground="black")
            newtags = [serial_num]
            all_tags.add(serial_num)
            newtags.extend(tags)
            insert(match.group(2), newtags)

            insert(match.group(3), tags)

        # Create tags that will be used
        buf.create_tag('code', foreground="black")
        
        insert(text, ['code'])
        #tw.tag_raise('code')
        #print "all tags=%s" % str(all_tags)

    def astIdtoTitle(self, ast_id):
        page = self.pages[ast_id]
        return page.title
        
    def delpage(self, ast_id):
        with self.lock:
            i = self.pagelist.index(ast_id)
            self.nb.remove_page(i)

            del self.pages[ast_id]
            self.pagelist.remove(ast_id)

    def addpage(self, ast_id, title, text):

        with self.lock:
            # Make room for new pages
            while len(self.pagelist) >= self.pagelimit:
                oldast_id = self.pagelist[0]
                self.delpage(oldast_id)
                
            scrolled_window = gtk.ScrolledWindow()
            scrolled_window.set_border_width(2)

            scrolled_window.set_policy(gtk.POLICY_AUTOMATIC,
                                       gtk.POLICY_AUTOMATIC)

            tw = gtk.TextView(buffer=None)
            scrolled_window.add(tw)
            tw.show()
            scrolled_window.show()

            tw.set_editable(False)
            tw.set_wrap_mode(gtk.WRAP_NONE)
            tw.set_left_margin(4)
            tw.set_right_margin(4)

            label = gtk.Label(title)
            label.show()

            self.nb.append_page(scrolled_window, label)

            self.insert_ast(tw, text)

            txtbuf = tw.get_buffer()
            tagtbl = txtbuf.get_tag_table()
            try:
                page = self.pages[ast_id]
                page.tw = tw
                page.buf = txtbuf
                page.tagtbl = tagtbl
                page.title = title
            except KeyError:
                self.pages[ast_id] = Bunch.Bunch(tw=tw, title=title,
                                                 buf=txtbuf, tagtbl=tagtbl)

            self.pagelist.append(ast_id)

            self.setpage(ast_id)

    def setpage(self, name):
        # Because %$%(*)&^! gtk notebook widget doesn't associate names
        # with pages
        i = self.pagelist.index(name)
        self.nb.set_current_page(i)

        
    def change_text(self, page, tagname, key):
        tagname = str(tagname)
        tag = page.tagtbl.lookup(tagname)
        if not tag:
            raise TagError("Tag not found: '%s'" % tagname)

        bnch = common.monitor_tags[key]

        for key, val in bnch.items():
            tag.set_property(key, val)
            
        #page.tw.tag_raise(ast_num)
        # Scroll the view to this area
        start, end = self.get_region(page.buf, tagname)
        page.tw.scroll_to_iter(start, 0.1)


    def get_region(self, txtbuf, tagname):
        """Returns a (start, end) pair of Gtk text buffer iterators
        associated with this tag.
        """
        # Painfully inefficient and error-prone way to locate a tagged
        # region.  Seems gtk text buffers have tags, but no good way to
        # manipulate text associated with them efficiently.

        tagname = str(tagname)

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


    def replace_text(self, page, tagname, textstr):
        tagname = str(tagname)
        txtbuf = page.buf
        start, end = self.get_region(txtbuf, tagname)
        txtbuf.delete(start, end)
        txtbuf.insert_with_tags_by_name(start, textstr, tagname)

        # Scroll the view to this area
        page.tw.scroll_to_iter(start, 0.1)


    def append_error(self, page, tagname, textstr):
        tagname = str(tagname)
        txtbuf = page.buf
        start, end = self.get_region(txtbuf, tagname)
        txtbuf.insert_with_tags_by_name(end, textstr, tagname)

        self.change_text(page, tagname, 'error')


    def update_time(self, page, tagname, vals, time_s):

        if not common.view.show_times:
            return

        tagname = str(tagname)
        txtbuf = page.buf
        start, end = self.get_region(txtbuf, tagname)

        if vals.has_key('time_added'):
            length = vals['time_added']
            end = start.copy()
            end.forward_chars(length)
            txtbuf.delete(start, end)
            
        vals['time_added'] = len(time_s)
        txtbuf.insert_with_tags_by_name(start, time_s, tagname)
        

    def update_page(self, bnch):

        page = bnch.page
        vals = bnch.state
        #print "vals = %s" % str(vals)
        ast_num = vals['ast_num']

        cmd_str = None
        if vals.has_key('cmd_str'):
            cmd_str = vals['cmd_str']

            if not vals.has_key('inserted'):
                # Replace the decode string with the actual parameters
                self.replace_text(page, ast_num, cmd_str)
                vals['inserted'] = True
                try:
                    del vals['time_added']
                except KeyError:
                    pass

        if vals.has_key('task_error'):
            self.append_error(page, ast_num, '\n ==> ' + vals['task_error'])
            
            # audible warnings
            common.controller.audible_warn(cmd_str, vals)

        elif vals.has_key('task_end'):
            if vals.has_key('task_start'):
                if common.view.track_elapsed and bnch.page.has_key('asttime'):
                    elapsed = vals['task_start'] - bnch.page.asttime
                else:
                    elapsed = vals['task_end'] - vals['task_start']
                self.update_time(page, ast_num, vals, '[ F %9.3f s ]: ' % (
                        elapsed))
            else:
                self.update_time(page, ast_num, vals, '[TE %s]: ' % (
                        self.time2str(vals['task_end'])))
            self.change_text(page, ast_num, 'task_end')
                
        elif vals.has_key('end_time'):
            self.update_time(page, ast_num, vals, '[EN %s]: ' % (
                    self.time2str(vals['end_time'])))
            self.change_text(page, ast_num, 'end_time')
                
        elif vals.has_key('ack_time'):
            self.update_time(page, ast_num, vals, '[AB %s]: ' % (
                    self.time2str(vals['ack_time'])))
            self.change_text(page, ast_num, 'ack_time')

        elif vals.has_key('cmd_time'):
            self.update_time(page, ast_num, vals, '[CD %s]: ' % (
                    self.time2str(vals['cmd_time'])))
            self.change_text(page, ast_num, 'cmd_time')

        elif vals.has_key('task_start'):
            self.update_time(page, ast_num, vals, '[TS %s]: ' % (
                    self.time2str(vals['task_start'])))
            self.change_text(page, ast_num, 'task_start')

        else:
            #self.change_text(page, ast_num, 'code')
            pass

                
    def time2str(self, time_cmd):
        time_int = int(time_cmd)
        time_str = time.strftime("%H:%M:%S", time.localtime(float(time_int)))
        time_sfx = ('%.3f' % (time_cmd - time_int)).split('.')[1]
        title = time_str + ',' + time_sfx
        return title
            
    def process_ast(self, ast_id, vals):
        #print ast_id, vals

        with self.lock:
            try:
                page = self.pages[ast_id]
            except KeyError:
                # this page is not received/set up yet
                page = Bunch.Bunch(vals)
                page.nodes = {}
                self.pages[ast_id] = page

            if vals.has_key('ast_buf'):
                ast_str = ro.binary_decode(vals['ast_buf'])
                # Get the time of the command to construct the tab title
                title = self.time2str(vals['ast_time'])
                page.asttime = vals['ast_time']

                # TODO: what if this page has already been deleted?
                # GLOBAL VAR READ
                if common.view.save_decode_result:
                    self.addpage(ast_id + '.decode', title, ast_str)

                self.addpage(ast_id, title, ast_str)

            elif vals.has_key('ast_track'):
                path = vals['ast_track']
                
                # GLOBAL VAR READ
                curvals = common.controller.getvals(path)
                if isinstance(curvals, dict):
                    vals.update(curvals)
               
                # Make an entry for this ast node, if there isn't one already
                ast_num = '%d' % vals['ast_num']
                state = page.nodes.setdefault(ast_num, vals)

                bnch = Bunch.Bunch(page=page, state=state)
                self.track.setdefault(vals['ast_track'], bnch)

                # It's possible in some cases that the ast_track could
                # arrive before the page is added or set up
                if not hasattr(page, 'buf'):
                    return

                # Replace the decode string with the actual parameters
                # ?? Has string really changed at this point??
                self.replace_text(page, ast_num, vals['ast_str'])

                self.update_page(bnch)
                

    def process_task(self, path, vals):
        #print path, vals

        with self.lock:
            try:
                bnch = self.track[path]
            except KeyError:
                # this page is not received/set up yet
                return

            #print path, vals
            bnch.state.update(vals)

            self.update_page(bnch)
            

    def process_ast_err(self, ast_id, vals):
        try:
            self.process_ast(ast_id, vals)
        except Exception, e:
            self.logger.error("MONITOR ERROR: %s" % str(e))
            try:
                (type, value, tb) = sys.exc_info()
                print "Traceback:\n%s" % \
                                  "".join(traceback.format_tb(tb))
                self.logger.error("Traceback:\n%s" % \
                                  "".join(traceback.format_tb(tb)))

            except Exception, e:
                self.logger.error("Traceback information unavailable.")
            
    def process_task_err(self, path, vals):
        try:
            self.process_task(path, vals)
        except Exception, e:
            self.logger.error("MONITOR ERROR: %s" % str(e))
            try:
                (type, value, tb) = sys.exc_info()
                print "Traceback:\n%s" % \
                                  "".join(traceback.format_tb(tb))
                self.logger.error("Traceback:\n%s" % \
                                  "".join(traceback.format_tb(tb)))

            except Exception, e:
                self.logger.error("Traceback information unavailable.")
            
        
#END
