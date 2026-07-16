#
# E. Jeschke
#
# Standard library imports
import os
import re, time

from ginga.gw import Widgets

from g2base.remoteObjects import remoteObjects as ro
from ginga.misc import Bunch

from . import common
from . import Page
from . import Workspace
from . import WorkspacePage
from . import Widgets as IGWidgets


class MonitorPage(Page.Page):
    """A lightweight, view-only page holding just a TextSource -- no menubar
    or button frame.  Used for the Monitor's command AST sub-pages."""

    def __init__(self, frame, name, title):
        super().__init__(frame, name, title)

        self.tw = IGWidgets.TextSource(editable=False, wrap='none')
        frame.add_widget(self.tw, stretch=1)


class SkMonitorPage(WorkspacePage.WorkspacePage):

    def __init__(self, frame, name, title):

        # Build the base page, pack a singleton menubar above the
        # sub-notebook, then let Workspace add the notebook below it.
        Page.Page.__init__(self, frame, name, title)

        self.menubar = Widgets.Menubar()
        self._menus = {}
        frame.add_widget(self.menubar, stretch=0)

        Workspace.Workspace.__init__(self, frame, name, title)

        self.pagelist = []
        self.pagelimit = 100
        self.db = {}
        # TODO: this dict is growing indefinitely
        self.track = {}

        # TODO: restrict tab drag-and-drop for this workspace (the GTK
        # set_group_name mechanism has no direct Qt equivalent).
        self.nb.set_tab_position('right')

        # Option variables
        self.save_decode_result = False
        self.show_times = False
        self.track_elapsed = False
        self.track_subcommands = True

        # Page menu: actions on the currently selected command page
        menu = self.add_pulldownmenu("Page")

        item = menu.add_name("Save current as ...")
        item.add_callback("activated", lambda w: self.save_current())

        item = menu.add_name("Close current")
        item.add_callback("activated", lambda w: self.close_current())

        # Options menu
        menu = self.add_pulldownmenu("Option")

        w = menu.add_name("Track Subcommands", checkable=True)
        w.set_state(self.track_subcommands)
        w.add_callback("activated", lambda w, tf: self.toggle_var(tf, 'track_subcommands'))

        w = menu.add_name("Save Decode Result", checkable=True)
        w.set_state(self.save_decode_result)
        w.add_callback("activated", lambda w, tf: self.toggle_var(tf, 'save_decode_result'))
        w = menu.add_name("Show Times", checkable=True)
        w.set_state(self.show_times)
        w.add_callback("activated", lambda w, tf: self.toggle_var(tf, 'show_times'))

        w = menu.add_name("Track Elapsed", checkable=True)
        w.set_state(self.track_elapsed)
        w.add_callback("activated", lambda w, tf: self.toggle_var(tf, 'track_elapsed'))

    def add_pulldownmenu(self, name):
        try:
            return self._menus[name]
        except KeyError:
            pass
        menu = self.menubar.add_name(name)
        self._menus[name] = menu
        return menu

    def get_current_page(self):
        idx = self.nb.get_index()
        if idx < 0:
            return None
        child = self.nb.index_to_widget(idx)
        return getattr(child, 'ig_page', None)

    def save_current(self):
        page = self.get_current_page()
        if page is None:
            common.view.popup_error("No monitor page is selected.")
            return

        homedir = os.path.join(os.environ['HOME'], 'Procedure')
        filename = time.strftime("%Y%m%d-%H%M%S") + '-monitor.txt'
        text = page.tw.get_text()

        def _save(filepath):
            try:
                with open(filepath, 'w') as out_f:
                    out_f.write(text)
            except Exception as e:
                common.view.popup_error("Cannot write '%s': %s" % (
                    filepath, str(e)))

        common.view.popup_save("Save monitor page", _save,
                               homedir, filename=filename)

    def close_current(self):
        page = self.get_current_page()
        if page is not None:
            self.delpage(page.name)

    def toggle_var(self, tf, key):
        self.__dict__[key] = tf

    def insert_ast(self, tw, text):
        # tw is a TextSource widget.  Text is inserted at the end and tagged
        # with the current tag stack; each AST node gets its own tag (its
        # serial number) so its whole subtree can be recolored later.
        all_tags = set([])

        def insert(text, tags):
            try:
                idx_div = text.index("<div ")

            except ValueError:
                tw.append_text(text, tags=list(tags), autoscroll=False)
                return

            match = re.match(r'^\<div\sclass=([^\>]+)\>', text[idx_div:],
                             re.MULTILINE | re.DOTALL)
            if not match:
                tw.append_text('ERROR 1: %s' % text, tags=list(tags),
                               autoscroll=False)
                return

            num = int(match.group(1))
            regex = r'^(.*)\<div\sclass=%d\>(.+)\</div\sclass=%d\>(.*)$' % (
                num, num)
            #print(regex)
            match = re.match(regex, text, re.MULTILINE | re.DOTALL)
            if not match:
                tw.append_text('ERROR 2: %s' % text, tags=list(tags),
                               autoscroll=False)
                return

            tw.append_text(match.group(1), tags=list(tags), autoscroll=False)

            serial_num = '%d' % num
            tw.create_tag(serial_num, foreground="black")
            all_tags.add(serial_num)
            newtags = [serial_num] + list(tags)
            insert(match.group(2), newtags)

            insert(match.group(3), tags)

        # Create tags that will be used
        tw.create_tag('code', foreground="black")

        insert(text, ['code'])
        #print("all tags=%s" % str(all_tags))

    def delpage(self, name):
        with self.lock:
            try:
                super().delpage(name)
            except Exception as e:
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

            page = super().addpage(name, title, MonitorPage)

            self.pagelist.append(name)

            #self.nb.set_tab_reorderable(page.frame, False)
            #self.nb.set_tab_detachable(page.frame, False)

            self.insert_ast(page.tw, text)

            #self.select(name)
            return page

    def change_text(self, page, tagname, key):
        tagname = str(tagname)
        tw = page.tw
        if not tw.has_tag(tagname):
            raise common.TagError("Tag not found: '%s'" % (tagname,))

        # Recolor the node's tag by redefining it with the status colors.
        attrs = dict(common.monitor_tags[key])
        tw.create_tag(tagname, **attrs)

        # Scroll the view to this region
        region = tw.get_tag_region(tagname)
        if region is not None:
            tw.scroll_to_ref(region[0])

    def replace_text(self, page, tagname, textstr,
                     start_offset=0):
        #print("replacing '%s' on %s" % (textstr, tagname))
        tagname = str(tagname)
        tw = page.tw
        start, end = common.get_region(tw, tagname)
        if start_offset:
            start.set_offset(start.get_offset() + start_offset)
        tw.delete_range(start, end)
        tw.insert_text(start, textstr, tags=[tagname])

        # Scroll the view to this area
        tw.scroll_to_ref(start)

    def insert_line(self, page, tagname, newtag, level, textstr):
        tagname = str(tagname)
        tw = page.tw
        start, end = common.get_region(tw, tagname)
        end2 = end.copy()
        end2.to_line_end()
        if end.get_line() != end2.get_line():
            end2 = end.copy()
        tw.create_tag(newtag, foreground="black")
        prefix = '\n' + ('  ' * level) + ' '
        tw.insert_text(end2, prefix, tags=['code'])
        tw.insert_text(end2, textstr, tags=[newtag])
        tw.insert_text(end2, ' ', tags=['code'])

    def append_error(self, page, tagname, textstr):
        tagname = str(tagname)
        tw = page.tw
        start, end = common.get_region(tw, tagname)
        tw.insert_text(end, textstr, tags=[tagname])

        self.change_text(page, tagname, 'error')

    def update_time(self, page, tagname, vals, time_s):

        if not self.show_times:
            return

        tagname = str(tagname)
        tw = page.tw
        start, end = common.get_region(tw, tagname)

        if 'time_added' in vals:
            length = vals['time_added']
            end2 = start.copy()
            end2.set_offset(start.get_offset() + length)
            tw.delete_range(start, end2)

        vals['time_added'] = len(time_s)
        tw.insert_text(start, time_s, tags=[tagname])

    def update_page(self, bnch):

        info = bnch.info
        page = info.page
        vals = bnch.state
        #print("update_page: vals = %s" % str(vals))
        tagname = bnch.tag

        cmd_str = None
        if 'cmd_str' in vals:
            cmd_str = vals['cmd_str']
            cmd_repn = vals.get('cmd_repn', cmd_str)

            # Only update this string if it has changed
            if 'inserted' not in vals or (vals['inserted'] != cmd_repn):
                offset = vals.get('time_added', 0)
                # Replace the decode string with the actual parameters
                self.replace_text(page, tagname, cmd_repn,
                                  start_offset=offset)
                vals['inserted'] = cmd_repn

        if 'task_error' in vals:
            self.append_error(page, tagname, '\n ==> ' + vals['task_error'])

            # audible warnings
            if 'audible' not in vals:
                vals['audible'] = True
                # Only play an audible error if this was not a cancel
                if 'task_code' in vals and (vals['task_code'] != 3):
                    common.controller.audible_warn(cmd_str, vals)

        elif 'task_end' in vals:
            if 'task_start' in vals:
                if self.track_elapsed and 'asttime' in info:
                    elapsed = vals['task_start'] - info.asttime
                else:
                    elapsed = vals['task_end'] - vals['task_start']
                self.update_time(page, tagname, vals, '[ F %9.3f s ]: ' % (
                    elapsed))
            else:
                self.update_time(page, tagname, vals, '[TE %s]: ' % (
                    self.time2str(vals['task_end'])))
            self.change_text(page, tagname, 'task_end')

        elif 'end_time' in vals:
            self.update_time(page, tagname, vals, '[EN %s]: ' % (
                self.time2str(vals['end_time'])))
            self.change_text(page, tagname, 'end_time')

        elif 'ack_time' in vals:
            self.update_time(page, tagname, vals, '[AB %s]: ' % (
                self.time2str(vals['ack_time'])))
            self.change_text(page, tagname, 'ack_time')

        elif 'cmd_time' in vals:
            self.update_time(page, tagname, vals, '[CD %s]: ' % (
                self.time2str(vals['cmd_time'])))
            self.change_text(page, tagname, 'cmd_time')

        elif 'task_start' in vals:
            self.update_time(page, tagname, vals, '[TS %s]: ' % (
                self.time2str(vals['task_start'])))
            self.change_text(page, tagname, 'task_start')

        else:
            #self.change_text(page, tagname, 'code')
            pass

    def time2str(self, time_cmd):
        time_int = int(time_cmd)
        time_str = time.strftime("%H:%M:%S", time.localtime(float(time_int)))
        time_sfx = ('%.3f' % (time_cmd - time_int)).split('.')[1]
        title = time_str + ',' + time_sfx
        return title

    def process_ast(self, ast_id, vals):
        #print(ast_id, vals)
        name = str(ast_id)

        with self.lock:
            try:
                info = self.db[name]
                page = info.page
            except KeyError:
                # this ast_id is not received/set up yet
                #info = Bunch.Bunch(nodes={}, page=None)
                info = Bunch.Bunch(page=None, pageid=ast_id)
                self.db[name] = info
                page = None

            if 'ast_buf' in vals:
                ast_str = ro.binary_decode(vals['ast_buf'])
                ast_str = ro.uncompress(ast_str)
                ast_str = ast_str.decode('ascii')
                # Due to an unfortunate way in which we have to search for
                # tags in common.get_region()
                if not ast_str.endswith('\n'):
                    ast_str = ast_str + '\n'
                #print("BUF!"); print(ast_str)

                # Get the time of the command to construct the tab title
                title = self.time2str(vals['ast_time'])
                info.asttime = vals['ast_time']

                # TODO: what if this page has already been deleted?
                if self.save_decode_result:
                    self.addpage(name + '.decode', title, ast_str)

                page = self.addpage(name, title, ast_str)
                info.page = page

            elif 'ast_track' in vals:
                path = vals['ast_track']

                # GLOBAL VAR READ
                curvals = common.controller.getvals(path)
                if isinstance(curvals, dict):
                    vals.update(curvals)

                # Make an entry for this ast node, if there isn't one already
                tagname = '%d' % vals['ast_num']
                # ?? necessary to have "nodes" table?
                #state = info.nodes.setdefault(tagname, vals)
                state = vals.copy()

                try:
                    bnch = self.track[path]
                    bnch.state.update(state)
                except KeyError:
                    bnch = Bunch.Bunch(state=state, info=info)
                    self.track[path] = bnch

                bnch.setvals(info=info, tag=tagname, level=0, count=0)

                # It's possible in some cases that the ast_track could
                # arrive before the page is added or set up
                if not page:
                    return

                # Replace the decode string with the actual parameters
                # ?? Has string really changed at this point??
                #self.replace_text(page, tagname, vals['ast_str'])

                self.update_page(bnch)

    def process_subcommand(self, parent_path, subpath, vals):

        with self.lock:
            # Don't do anything if we are not tracking subcommands
            if not self.track_subcommands:
                return

            try:
                # Get parent track record
                p_bnch = self.track[parent_path]
            except KeyError:
                # parent command is not received/set up yet
                return

            # Have we already set this up?
            if subpath in self.track:
                return

            page = p_bnch.info.page
            if not page:
                return

            # Collect any state that has built up for this path
            state = {}
            curvals = common.controller.getvals(subpath)
            if isinstance(curvals, dict):
                state.update(curvals)
            #print("What we know is: %s" % str(state))

            # Figure out the text tag of the last subcommand under this
            # command based on the count
            lasttag = p_bnch.tag
            if p_bnch.count > 0:
                lasttag = '%s_%d' % (lasttag, p_bnch.count)
            p_bnch.count += 1
            count = p_bnch.count
            level = p_bnch.level + 1
            # make a new text tag for the subcommand
            tagname = '%s_%d' % (p_bnch.tag, count)
            cmd_str = 'SUBCOMMAND'

            # Insert a new line for the subcommand
            #print("inserting new line: lasttag=%s" % (lasttag))
            self.insert_line(page, lasttag, tagname, level, cmd_str)

            bnch = Bunch.Bunch(info=p_bnch.info, state=state, tag=tagname,
                               level=level, count=count)
            self.track.setdefault(subpath, bnch)

            self.update_page(bnch)

    def process_task(self, path, vals):
        #print("process_task: ", path, vals)

        with self.lock:
            try:
                bnch = self.track[path]

            except KeyError:
                state = Bunch.Bunch(vals)
                info = Bunch.Bunch(page=None)
                bnch = Bunch.Bunch(state=state, info=info)
                self.track[path] = bnch
                # this page is not received/set up yet
                #print("Page for '%s' not set up yet!" % (path))
                return

            #print(path, vals)
            bnch.state.update(vals)

            if bnch.info.page:
                self.update_page(bnch)
