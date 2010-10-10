# 
#[ Eric Jeschke (eric@naoj.org) --
#  Last edit: Sat Oct  9 21:18:07 HST 2010
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
import WorkspacePage
from LogPage import NotePage


class SkMonitorPage(WorkspacePage.ButtonWorkspacePage):

    def __init__(self, frame, name, title):

        WorkspacePage.ButtonWorkspacePage.__init__(self, frame, name, title)

        self.pagelist = []
        self.pagelimit = 100
        self.db = {}
        # TODO: this dict is growing indefinitely
        self.track = {}

        # Don't allow DND to this workspace
        self.nb.set_group_id(2)
        self.nb.set_tab_pos(gtk.POS_RIGHT)

        ## menu = self.add_pulldownmenu("Page")

        ## item = gtk.MenuItem(label="Close")
        ## # currently disabled
        ## item.set_sensitive(False)
        ## menu.append(item)
        ## item.connect_object ("activate", lambda w: self.close(),
        ##                      "menu.Close")
        ## item.show()

        # Options menu
        ## menu = self.add_pulldownmenu("Option")
        menu = gtk.Menu()
        item = gtk.MenuItem(label="Option")
        self.wsmenu.append(item)
        item.show()
        item.set_submenu(menu)

        # Option variables
        self.save_decode_result = False
        self.show_times = False
        self.track_elapsed = False

        w = gtk.CheckMenuItem("Save Decode Result")
        w.set_active(False)
        menu.append(w)
        w.show()
        w.connect("activate", lambda w: self.toggle_var(w, 'save_decode_result'))
        w = gtk.CheckMenuItem("Show Times")
        w.set_active(False)
        menu.append(w)
        w.show()
        w.connect("activate", lambda w: self.toggle_var(w, 'show_times'))

        w = gtk.CheckMenuItem("Track Elapsed")
        w.set_active(False)
        menu.append(w)
        w.show()
        w.connect("activate", lambda w: self.toggle_var(w, 'track_elapsed'))


    def toggle_var(self, widget, key):
        if widget.active: 
            self.__dict__[key] = True
        else:
            self.__dict__[key] = False


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

    ## def astIdtoTitle(self, ast_id):
    ##     page = self.pages[ast_id]
    ##     return page.title
        
    def delpage(self, name):
        with self.lock:
            try:
                super(SkMonitorPage, self).delpage(name)
            except Exception, e:
                # may have already been removed
                pass
            try:
                self.pagelist.remove(name)
            except ValueError:
                # may have already been removed
                pass
            try:
                del self.db[name]
            except KeyError:
                # may have already been removed
                pass

    def addpage(self, name, title, text):

        with self.lock:
            # Make room for new pages
            while len(self.pagelist) >= self.pagelimit:
                oldname = self.pagelist.pop(0)
                self.delpage(oldname)

            page = super(SkMonitorPage, self).addpage(name, title, NotePage)

            self.pagelist.append(name)

            self.nb.set_tab_reorderable(page.frame, False)
            self.nb.set_tab_detachable(page.frame, False)

            self.insert_ast(page.tw, text)
            page.tagtbl = page.buf.get_tag_table()

            #self.select(name)
            return page
        
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
        start, end = common.get_region(page.buf, tagname)
        page.tw.scroll_to_iter(start, 0.1)


    def replace_text(self, page, tagname, textstr):
        tagname = str(tagname)
        txtbuf = page.buf
        start, end = common.get_region(txtbuf, tagname)
        txtbuf.delete(start, end)
        txtbuf.insert_with_tags_by_name(start, textstr, tagname)

        # Scroll the view to this area
        page.tw.scroll_to_iter(start, 0.1)


    def append_error(self, page, tagname, textstr):
        tagname = str(tagname)
        txtbuf = page.buf
        start, end = common.get_region(txtbuf, tagname)
        txtbuf.insert_with_tags_by_name(end, textstr, tagname)

        self.change_text(page, tagname, 'error')


    def update_time(self, page, tagname, vals, time_s):

        if not self.show_times:
            return

        tagname = str(tagname)
        txtbuf = page.buf
        start, end = common.get_region(txtbuf, tagname)

        if vals.has_key('time_added'):
            length = vals['time_added']
            end = start.copy()
            end.forward_chars(length)
            txtbuf.delete(start, end)
            
        vals['time_added'] = len(time_s)
        txtbuf.insert_with_tags_by_name(start, time_s, tagname)
        

    def update_page(self, bnch):

        info = bnch.info
        page = info.page
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
            #common.controller.audible_warn(cmd_str, vals)

        elif vals.has_key('task_end'):
            if vals.has_key('task_start'):
                if self.track_elapsed and info.has_key('asttime'):
                    elapsed = vals['task_start'] - info.asttime
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
        name = str(ast_id)
        
        with self.lock:
            try:
                info = self.db[name]
                page = info.page
            except KeyError:
                # this ast_id is not received/set up yet
                info = Bunch.Bunch(nodes={}, page=None)
                # ??for what?
                info.update(vals)
                self.db[name] = info
                page = None

            if vals.has_key('ast_buf'):
                ast_str = ro.binary_decode(vals['ast_buf'])
                # Get the time of the command to construct the tab title
                title = self.time2str(vals['ast_time'])
                info.asttime = vals['ast_time']

                # TODO: what if this page has already been deleted?
                if self.save_decode_result:
                    self.addpage(name + '.decode', title, ast_str)

                page = self.addpage(name, title, ast_str)
                info.page = page

            elif vals.has_key('ast_track'):
                path = vals['ast_track']
                
                # GLOBAL VAR READ
                curvals = common.controller.getvals(path)
                if isinstance(curvals, dict):
                    vals.update(curvals)
               
                # Make an entry for this ast node, if there isn't one already
                ast_num = '%d' % vals['ast_num']
                state = info.nodes.setdefault(ast_num, vals)

                bnch = Bunch.Bunch(info=info, state=state)
                self.track.setdefault(vals['ast_track'], bnch)

                # It's possible in some cases that the ast_track could
                # arrive before the page is added or set up
                if not page:
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

            if bnch.info.page:
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
