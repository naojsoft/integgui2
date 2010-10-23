# 
#[ Eric Jeschke (eric@naoj.org) --
#  Last edit: Fri Oct 22 15:36:57 HST 2010
#]
import sys
import glob
import os, re
import gtk

import common
import Page, CodePage


class DirectoryPage(CodePage.CodePage):

    def __init__(self, frame, name, title):
        super(DirectoryPage, self).__init__(frame, name, title)

        self.listing = []
        self.pattern = '*'
        self.clickfn = None

        self.cursor = 0
        self.moving_cursor = False

        self.tw.set_editable(False)
        #self.tw.connect("button-press-event", self.jump_tag)
        self.buf.create_tag('cursor', background="skyblue1")
        self.buf.connect("mark-set", self.show_cursor)

        # keyboard shortcuts
        self.tw.connect("key-press-event", self.keypress)

        # add some bottom buttons
        ## self.btn_exec = gtk.Button("Exec")
        ## self.btn_exec.connect("clicked", lambda w: self.execute())
        ## self.btn_exec.modify_bg(gtk.STATE_NORMAL,
        ##                         common.launcher_colors['execbtn'])
        ## self.btn_exec.show()
        ## self.leftbtns.pack_end(self.btn_exec)

    def regist_clickfn(fn):
        """Register a function to be called on the files when you click them."""
        self.clickfn = fn

    def process_listing(self, listing):
        def strippath(path):
            dirname, filename = os.path.split(path)
            return filename
        buf = '\n'.join(map(strippath, listing))
        return buf
        
    def listdir(self, dirpath, pattern):
        listing = glob.glob(os.path.join(dirpath, pattern))
        listing.sort()
        self.listing = listing
        buf = self.process_listing(listing)
        return buf
        
    def load(self, dirpath, pattern):
        buf = self.listdir(dirpath, pattern)
        self.dirpath = dirpath
        self.pattern = pattern
        super(DirectoryPage, self).load(dirpath, buf)
        self._redraw()

    def reload(self):
        buf = self.listdir(self.dirpath, self.pattern)
        self.loadbuf(buf)
        self._redraw()

    def color(self):
        try:
            self.tags = common.decorative_tags + common.execution_tags

            # Remove everything from the tag buffer
            start, end = self.tagbuf.get_bounds()
            self.tagbuf.delete(start, end)

            # Get the text from the code buffer
            start, end = self.buf.get_bounds()
            buf = self.buf.get_text(start, end)

            # compute the variable dictionary
            include_dirs = common.view.include_dirs
            self.varDict = ope.get_vars_ope(buf, include_dirs)

            badrefs = set([])
            badtags = []
            self.tagidx = {}

            tagtbl = self.buf.get_tag_table()

            # remove decorative tags
            for tag, bnch in common.decorative_tags:
                gtktag = tagtbl.lookup(tag)
                try:
                    if gtktag:
                        self.buf.remove_tag_by_name(tag, start, end)
                except:
                    # tag may not exist--that's ok
                    pass

            # add tags back in
            for tag, bnch in self.tags:
                properties = {}
                properties.update(bnch)
                try:
                    self.buf.create_tag(tag, **properties)
                except:
                    # tag may already exist--that's ok
                    pass
                try:
                    self.tagbuf.create_tag(tag, **properties)
                except:
                    # tag may already exist--that's ok
                    pass

            def addbadtag(lineno, line, tags):
                # Add this line and a tag to the tags buffer
                tend = self.tagbuf.get_end_iter()
                taglineno = tend.get_line()
    ##             self.tagbuf.insert_with_tags_by_name(tend, line+'\n',
    ##                                                  *(tags + [tag]))
                self.tagbuf.insert_with_tags_by_name(tend, line+'\n', *tags)
                # make an entry in the tags index
                self.tagidx[taglineno] = lineno

            def addtags(lineno, line, tags):
                # apply desired tags to entire line in main text buffer
                start.set_line(lineno)
                end.set_line(lineno)
                end.forward_to_line_end()

                for tag in tags:
                    self.buf.apply_tag_by_name(tag, start, end)

                addbadtag(lineno, line, tags)

            def addvarrefs(lineno, line):
                # apply desired tags to varrefs in this line in main text buffer

                offset = 0
                match = regex_varref.match(line)
                while match:
                    pfx, varref, sfx = match.groups()
                    varref = varref.upper()
                    start.set_line(lineno)
                    offset += len(pfx)
                    start.forward_chars(offset)
                    end.set_line(lineno)
                    offset += len(varref)
                    end.forward_chars(offset)

                    self.buf.apply_tag_by_name('varref', start, end)
                    try:
                        res = self.get_vardef(varref[1:])
                    except Exception, e:
                        self.buf.apply_tag_by_name('badref', start, end)
                        badrefs.add(varref)
                        badtags.append((varref, lineno))

                    match = regex_varref.match(sfx)

            lineno = 0
            for line in buf.split('\n'):
                line = line.strip()
                if line.startswith('###'):
                    addtags(lineno, line, ['comment3'])

                elif line.startswith('##'):
                    addtags(lineno, line, ['comment2'])

                elif line.startswith('#'):
                    addtags(lineno, line, ['comment1'])

                else:
                    addvarrefs(lineno, line)

                lineno += 1

            if len(badrefs) > 0:
                # Add all undefined refs to the tag table
                loc = self.tagbuf.get_end_iter()
                startline = loc.get_line()
                addbadtag(1, "UNDEFINED VARIABLE REFS", ['badref'])
                for varref, lineno in badtags:
                    addbadtag(lineno, "%s: line %d" % (varref, lineno), ['badref'])

                # Scroll tag table to errors
                loc = self.tagbuf.get_end_iter()
                loc.set_line(startline)
                # HACK: I have to defer the scroll operation until the widget
                # is rendered or it does not scroll
                common.view.gui_do(self.tagtw.scroll_to_iter,
                                    loc, 0, True)

                # Set the background of the tags button to indicate error
                self.btn_tags.modify_bg(gtk.STATE_NORMAL,
                                        common.launcher_colors.badtags)
                self.btn_tags.modify_bg(gtk.STATE_ACTIVE,
                                        common.launcher_colors.badtags)

                common.view.popup_error("Undefined variable references: " +
                                        ' '.join(badrefs) +
                                        ". See bottom of tags for details.")
                # open the tag table
                self.showtags()

            else:
                self.btn_tags.modify_bg(gtk.STATE_NORMAL,
                                        common.launcher_colors.normal)
                self.btn_tags.modify_bg(gtk.STATE_ACTIVE,
                                        common.launcher_colors.normal)
        except Exception, e:
            common.view.popup_error("Error coloring buffer: %s" % (
                str(e)))

    def _redraw(self):
        # restore cursor
        end = self.buf.get_end_iter()
        #self.moving_cursor = False
        self.cursor = min(self.cursor, end.get_line())
        loc = self.buf.get_iter_at_line(self.cursor)
        self.buf.place_cursor(loc)

        # Hacky way to get our cursor on screen
        insmark = self.buf.get_insert()
        if insmark != None:
            res = self.tw.scroll_to_mark(insmark, 0, use_align=True)

    def redraw(self):
        common.gui_do(self._redraw)
        
    def show_cursor(self, tbuf, titer, tmark):
        if self.moving_cursor:
            return False
        
        insmark = tbuf.get_insert()
        if insmark != tmark:
            return False

        self.moving_cursor = True
        try:
            # Color the new line nwe
            start, end = tbuf.get_bounds()
            self.buf.remove_tag_by_name('cursor', start, end)

            line = titer.get_line()
            self.cursor = line
            start = tbuf.get_iter_at_line(line)
            end = start.copy()
            end.forward_to_line_end()
            tbuf.apply_tag_by_name('cursor', start, end)

            selmark = tbuf.get_mark('selection_bound')
            seliter = tbuf.get_iter_at_mark(selmark)
            if not seliter.starts_line():
                tbuf.move_mark_by_name('selection_bound', start)
            tbuf.move_mark(insmark, start)

        finally:
            self.moving_cursor = False
        return True
    
    ## def jump_tag(self, w, evt):
    ##     print str(evt)
    ##     widget = self.tw
    ##     try:
    ##         tup = widget.window_to_buffer_coords(gtk.TEXT_WINDOW_TEXT,
    ##                                              evt.x, evt.y)
    ##         #print tup
    ##         buf_x1, buf_y1 = tup
    ##     except Exception, e:
    ##         self.logger.error("Error converting coordinates to line: %s" % (
    ##             str(e)))
    ##         return False
        
    ##     (startiter, coord) = widget.get_line_at_y(buf_y1)
    ##     lineno = startiter.get_line()
    ##     ## enditer = startiter.copy()
    ##     ## enditer.forward_to_line_end()
    ##     ## text = self.buf.get_text(startiter, enditer)
    ##     text = self.listing[lineno]
    ##     self.process_line(text)
       
    ##     return True
            
    def process_entry(self, text, keyname):
        """Subclass should override this to do something interesting when
        a folder link is clicked."""
        self.logger.debug("text is %s, key is '%s'" % (text, keyname))
        if keyname == 'e':
            common.view.gui_do(common.view.load_file, text)
            return True
        
        if keyname == 'i':
            common.view.gui_do(common.view.load_inf, text)
            return True
        
        if (keyname == 'Return') and (self.clickfn):
            common.controller.ctl_do(self.clickfn, text)

        return False
       
        
    def keypress(self, w, event):
        keyname = gtk.gdk.keyval_name(event.keyval)
        if keyname in ('Up', 'Down', 'Shift_L', 'Shift_R',
                       'Alt_L', 'Alt_R', 'Control_L', 'Control_R'):
            # navigation and other
            return False
        if keyname in ('Left', 'Right'):
            # ignore these
            return True
        #print "key pressed --> %s" % keyname

        if event.state & gtk.gdk.CONTROL_MASK:
            if keyname == 'r':
                self.reload()
                return True
            
            elif keyname == 'q':
                common.view.raise_queue()
                return True
        
            elif keyname == 'h':
                common.view.raise_handset()
                return True

        else:
            try:
                text = self.listing[self.cursor]
            except IndexError:
                return False
            
            return self.process_entry(text, keyname)
            
        return False
    

#END
