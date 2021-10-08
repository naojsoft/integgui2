#
# TablePage.py -- an integgui2 page that shows a table
# 
# Eric Jeschke (eric@naoj.org)
#
import sys
import os.path

from gi.repository import Gtk
from gi.repository import GdkPixbuf

from ginga.misc import Bunch

from . import Page

thisDir = os.path.split(sys.modules[__name__].__file__)[0]
icondir = os.path.abspath(os.path.join(thisDir, "..", "icons"))


class TablePage(Page.ButtonPage):

    def __init__(self, frame, name, title):

        super(TablePage, self).__init__(frame, name, title)

        self.columns = []
        self.index = {}

        sw = Gtk.ScrolledWindow()
        sw.set_border_width(2)
        sw.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        sw.show()
        self.sw = sw
        frame.pack_start(sw, True, True, 2)

        # bottom buttons
        btns = Gtk.HButtonBox()
        btns.set_layout(Gtk.ButtonBoxStyle.START)
        btns.set_spacing(5)
        self.btns = btns

        frame.pack_end(btns, False, False, 2)

        menu = self.add_pulldownmenu("Page")

    def set_columns(self, columns):
        self.columns = columns
        self.cell_sort_funcs = []

        # create the TreeView
        treeview = Gtk.TreeView()
        
        # create the TreeViewColumns to display the data
        tvcolumn = [None] * len(self.columns)
        n = 0
        for header, kwd, dtype in self.columns:
            self.cell_sort_funcs.append(self._mksrtfnN(kwd, dtype))
            if dtype == 'icon':
                cell = Gtk.CellRendererPixbuf()
            else:
                cell = Gtk.CellRendererText()
            cell.set_padding(2, 0)
            #header, kwd = self.columns[n]
            tvc = Gtk.TreeViewColumn(header, cell)
            tvc.set_resizable(True)
            tvc.connect('clicked', self.sort_cb, n)
            tvc.set_clickable(True)
            tvcolumn[n] = tvc
            fn_data = self._mkcolfnN(kwd, dtype)
            tvcolumn[n].set_cell_data_func(cell, fn_data)
            treeview.append_column(tvcolumn[n])
            n += 1

        self.listmodel = Gtk.ListStore(object)
        treeview.set_model(self.listmodel)
        self.treeview = treeview
        
        self.sw.add(treeview)
        self.sw.show_all()

    def sort_cb(self, column, idx):
        treeview = column.get_tree_view()
        model = treeview.get_model()
        model.set_sort_column_id(idx, Gtk.SortType.ASCENDING)
        fn = self.cell_sort_funcs[idx]
        model.set_sort_func(idx, fn)
        return True

    def _mkcolfnN(self, kwd, dtype):
        def make_text(column, cell, model, iter):
            bnch = model.get_value(iter, 0)
            #cell.set_property('text', bnch[kwd])
            cell.set_property('markup', bnch[kwd])

        def make_pb(column, cell, model, iter):
            bnch = model.get_value(iter, 0)
            filename = bnch[kwd]
            filepath = os.path.join(icondir, filename)
            #pb = self.treeview.render_icon(stock,
            #                               Gtk.IconSize.MENU, None)
            width = 16
            height = width
            pb = GdkPixbuf.Pixbuf.new_from_file_at_size(filepath,
                                                        width, height)
            cell.set_property('pixbuf', pb)

        if dtype == 'icon':
            return make_pb
        else:
            return make_text

    def _mksrtfnN(self, key, dtype):
        def _cmp(x,y):
            return (x > y) - (x < y)

        def fn_str(model, iter1, iter2):
            bnch1 = model.get_value(iter1, 0)
            bnch2 = model.get_value(iter2, 0)
            val1, val2 = bnch1[key], bnch2[key]
            val1 = val1.lower()
            val2 = val2.lower()
            res = _cmp(val1, val2)
            return res

        def fn_num(model, iter1, iter2):
            bnch1 = model.get_value(iter1, 0)
            bnch2 = model.get_value(iter2, 0)
            val1, val2 = bnch1[key], bnch2[key]
            res = _cmp(val1, val2)
            return res

        def fn_nop(model, iter1, iter2):
            return 0

        if dtype == 'text':
            return fn_str
        elif dtype == 'number':
            return fn_num
        else:
            return fn_nop
        
        return fn

    def update_table(self, key, info):
        self.logger.debug("update table info=%s" % str(info))
        self.treeview.set_fixed_height_mode(False)
        with self.lock:
            try:
                bnch = self.index[key]
                bnch.update(info)

            except KeyError:
                bnch = Bunch.Bunch(info)
                self.index[key] = bnch
                self.listmodel.append([bnch])

            self.treeview.set_fixed_height_mode(True)
            # this forces a refresh of the widget
            #self.treeview.columns_autosize()
            self.treeview.queue_draw()

    def clear(self):
        # Delete all current items
        self.listmodel = Gtk.ListStore(object)
        self.treeview.set_model(self.listmodel)
        self.index = {}

#END
