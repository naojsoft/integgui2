#
# Russell Kackley (rkackley@naoj.org)
#
# Displays names and status of tracking coordinate files copied to TSC
# computer

from __future__ import absolute_import
import os, glob

from gi.repository import Gtk
from gi.repository import GdkPixbuf
from gi.repository import Pango

from . import common
from . import Page

from g2base.remoteObjects import remoteObjects as ro
from ginga.misc import Bunch

import astro.TSCTrackFile as TSCTrackFile

class CopyTSCTrackPage(Page.ButtonPage):

    STATUS__OK                  = 0
    STATUS__FILE_READY_TO_COPY  = 1
    STATUS__FILE_PENDING        = 2
    STATUS__FILE_NOTFOUND_ERROR = 3
    STATUS__FILE_FORMAT_ERROR   = 4
    STATUS__FILE_COPY_ERROR     = 5
    STATUS_INFO = {
        STATUS__OK:                  'Ok',
        STATUS__FILE_READY_TO_COPY:  'Ready to Copy...',
        STATUS__FILE_PENDING:        'Pending...',
        STATUS__FILE_NOTFOUND_ERROR: 'File Not Found',
        STATUS__FILE_FORMAT_ERROR:   'Format Error',
        STATUS__FILE_COPY_ERROR:     'Copy Error'
        }

    def __init__(self, frame, name, title):

        super(CopyTSCTrackPage, self).__init__(frame, name, title)

        self.okFileCount = 0
        self.filepaths = []
        self.tree_dirs = {}
        self.tree_filepaths = {}
        self.setStatus(self.STATUS__OK)
        self.cancelFlag = False
        self.callfn = None
        self.logger = None

        # Add a "Page" menu
        menu = self.add_pulldownmenu("Page")

        # Add a "Close" item to the "Page" menu to provide a way for
        # the user to close the CopyTSCTrackPage
        item = Gtk.MenuItem(label="Close")
        menu.append(item)
        item.connect_object ("activate", lambda w: self.close(),
                             "menu.Close")
        item.show()

        # Create a Frame with a thin border into which we will place
        # the ScrolledWindow
        self.border = Gtk.Frame()
        self.border.set_shadow_type(Gtk.ShadowType.ETCHED_OUT)
        self.border.set_label_align(0.1, 0.5)

        # Create a ScrolledWindow object into which we will place the
        # TreeView
        sw = Gtk.ScrolledWindow()
        sw.set_border_width(2)
        sw.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        sw.show()
        self.sw = sw

        # The columns to display in the TreeView.
        #                  header       kwd     datatype width
        self.columns = [('Filename', 'filename', 'text', 525),
                        ('Status',   'status',   'text', 50)]

        # create the TreeView which will display the filenames and
        # status info.
        self.treeview = Gtk.TreeView()

        # Create the TreeViewColumns, based on the above column
        # information. At the end of the loop, append the
        # TreeViewColumn to the TreeView widget.
        tvcolumn = []
        for n, colInfo in enumerate(self.columns):
            header, kwd, dtype, width = colInfo
            if dtype == 'icon':
                cell = Gtk.CellRendererPixbuf()
            else:
                cell = Gtk.CellRendererText()
            cell.set_padding(2, 0)
            tvc = Gtk.TreeViewColumn(header, cell)
            tvc.set_resizable(True)
            tvc.set_min_width(width)
            tvcolumn.append(tvc)
            fn_data = self._mkcolfnN(kwd, dtype)
            tvcolumn[n].set_cell_data_func(cell, fn_data)
            self.treeview.append_column(tvcolumn[n])

        # create a TreeStore to use as the data model
        self.treestore = Gtk.TreeStore(object)

        # Set the model for the TreeView widget to the TreeStore we
        # just created.
        self.treeview.set_model(self.treestore)

        # Set some attributes of the TreeView widget
        self.treeview.get_selection().set_mode(Gtk.SELECTION_NONE)
        self.treeview.get_selection().unselect_all()
        self.treeview.show()

        # Put the TreeView widget inside the ScrolledWindow
        self.sw.add(self.treeview)

        # Put the ScrolledWindow/TreeView combination inside the
        # border
        self.border.add(sw)
        self.border.show()

        # Put the border/ScrolledWindow/TreeView combination inside
        # the supplied parent frame.
        frame.pack_start(self.border, True, True, 2)

        # add a bottom button to allow the user to start the copy operation
        self.btn_startCopy = Gtk.Button("Start Copy")
        self.btn_startCopy.connect("clicked", lambda w: self.startCopy())
        self.btn_startCopy.show()
        self.btn_startCopy.set_sensitive(False)
        self.leftbtns.pack_end(self.btn_startCopy, False, False, 0)

        # add a bottom button to allow the user to cancel the copy operation
        self.btn_cancelCopy = Gtk.Button("Cancel Copy")
        self.btn_cancelCopy.connect("clicked", lambda w: self.cancelCopy())
        self.btn_cancelCopy.show()
        self.btn_cancelCopy.set_sensitive(False)
        self.leftbtns.pack_end(self.btn_cancelCopy, False, False, 0)

    def setup(self, callfn=None, filepaths=None, checkFormat=True, logger=ro.nullLogger()):
        # Setup the CopyTSCTrackPage by specifying the completion
        # callback function (optional), the list of file paths to be
        # copied, and the logger (optional)
        if self.logger is None:
            self.logger = logger

        # If callfn was specified, save it here so we can call it at
        # the completion of the "copy files to TSC" operation.
        if callfn:
            self.callfn = callfn

        # Iterate through the supplied filepaths and create a list of
        # them. If any are directory files, descend into the directory
        # and add any files in there to our list.
        if filepaths:
            self.treestore.clear()
            self.filepaths = []
            self.tree_dirs = {}
            self.tree_filepaths = {}
            self.status = self.STATUS__OK
            self.statusMsg = self.STATUS_INFO[self.STATUS__OK]
            for filepath in filepaths:
                if os.path.isdir(filepath):
                    allFiles = glob.glob(os.path.join(filepath, '*'))
                    for file in allFiles:
                        if not os.path.isdir(file):
                            self.filepaths.append(file)
                else:
                    self.filepaths.append(filepath)

        # Iterate through all the files in our list and make sure that
        # they exist and that they are formatted correctly to serve as
        # TSC tracking coordinate files. We also update our TreeStore
        # model in this loop to set the filenames and status of each
        # file.
        self.okFileCount = 0
        for filepath in self.filepaths:
            if os.path.exists(filepath):
                fileStatus = self.STATUS__FILE_READY_TO_COPY
                if checkFormat:
                    try:
                        TSCTrackFile.checkTSCFileFormat(filepath, self.logger)
                        self.okFileCount += 1
                    except TSCTrackFile.TSCFileFormatError as e:
                        self.logger.error('file %s format is incorrect (%s)' % (filepath, str(e)))
                        fileStatus = self.STATUS__FILE_FORMAT_ERROR
                        self.setStatus(fileStatus)
            else:
                self.logger.error('file %s does not exist' % filepath)
                fileStatus = self.STATUS__FILE_NOTFOUND_ERROR
                self.setStatus(fileStatus)

            self.logger.debug('CopyTSCTrackPage setup calling update_tree with filepath %s fileStatus %d' % (filepath, fileStatus))
            self.update_tree(filepath, fileStatus)

        # Set the TreeView to show all the rows as "expanded"
        self.treeview.expand_all()

        # If we found one or more files that have the correct format,
        # enable the "Start Copy" button. Otherwise, disable it
        # because it won't be able to do anything.
        if self.okFileCount > 0:
            self.btn_startCopy.set_sensitive(True)
        else:
            self.btn_startCopy.set_sensitive(False)

    def startCopy(self):
        # The callback for the "Start Copy" button
        self.setup()
        # Disable the "Start Copy" button and enable the "Cancel Copy"
        # button
        self.btn_startCopy.set_sensitive(False)
        self.btn_cancelCopy.set_sensitive(True)
        # Set the cancelFlag to False prior to starting the copy
        # operation
        self.cancelFlag = False
        # Run the "copy to TSC" method in a separate thread so that we
        # don't tie up the GUI thread during the copy.
        common.controller.ctl_do(self.copyfilestotsc)

    def cancelCopy(self):
        # The callback for the "Cancel Copy" button
        self.cancelFlag = True

    def _mkcolfnN(self, kwd, dtype):
        # Callback function that specifies how to display a cell in
        # the TreeView
        def make_text(column, cell, model, iter):
            # For cells with text in them
            bnch = model.get_value(iter, 0)
            cell.set_property('markup', bnch[kwd])
            cell.set_property('ellipsize', Pango.ELLIPSIZE_MIDDLE)
            if kwd == 'status':
                if bnch.statusCode in (self.STATUS__FILE_PENDING, self.STATUS__FILE_READY_TO_COPY):
                    backgrd = 'yellow'
                elif bnch.statusCode == self.STATUS__OK:
                    backgrd = 'green'
                elif bnch.statusCode in (self.STATUS__FILE_NOTFOUND_ERROR, self.STATUS__FILE_FORMAT_ERROR, self.STATUS__FILE_COPY_ERROR):
                    backgrd = 'red'
                else:
                    backgrd = 'white'
                cell.set_property('background', backgrd)

        def make_pb(column, cell, model, iter):
            # For cells with icons in them
            bnch = model.get_value(iter, 0)
            filename = bnch[kwd]
            filepath = os.path.join(icondir, filename)
            width = 16
            height = width
            pb = GdkPixbuf.Pixbuf.new_from_file_at_size(filepath,
                                                        width, height)
            cell.set_property('pixbuf', pb)

        if dtype == 'icon':
            return make_pb
        else:
            return make_text

    def update_tree(self, key, statusCode, date_time=None):
        # Update the TreeStore with the supplied key, statusCode, and
        # date_time. Note that the key is basically the filepath.
        self.logger.debug('CopyTSCTrackPage update_tree called key %s statusCode %d'%(key, statusCode))
        # Create a dictionary with the supplied filepath, the
        # extracted filename, and the supplied status code.
        info = {'filepath': key, 'filename': os.path.basename(key), 'statusCode': statusCode}
        # Add the 'status' key to info. The 'status' value depends on
        # whether statusCode is STATUS__OK or something else. For
        # STATUS__OK, we append the supplied date_time to the
        # STATUS_INFO value.
        if statusCode == self.STATUS__OK:
            info['status'] = ' '.join([self.STATUS_INFO[statusCode], str(date_time)])
        else:
            info['status'] = self.STATUS_INFO[statusCode]

        dirname = os.path.dirname(key)
        if dirname in self.tree_dirs:
            piter = self.tree_dirs[dirname]['iter']
        else:
            bnch = Bunch.Bunch({'filepath': key, 'filename': dirname, 'statusCode': None, 'status': None})
            piter = self.treestore.append(None, [bnch])
            self.tree_dirs[dirname] = {'iter': piter, 'info': bnch}
        if key in self.tree_filepaths:
            bnch = self.tree_filepaths[key]
            bnch.update(info)
        else:
            bnch = Bunch.Bunch(info)
            self.tree_filepaths[key] = bnch
            self.treestore.append(piter, [bnch])

        # this forces a refresh of the widget
        self.treeview.queue_draw()

    def setStatus(self, status):
        self.status = status
        if self.status == self.STATUS__OK:
            self.statusMsg = None
        elif self.status == self.STATUS__FILE_PENDING:
            self.statusMsg = 'Copy in progress'
        elif self.status == self.STATUS__FILE_NOTFOUND_ERROR:
            self.statusMsg = 'One or more of the specified files does not exist and was not copied'
        elif self.status == self.STATUS__FILE_FORMAT_ERROR:
            self.statusMsg = 'One or more of the specified files has an incorrect format and was not copied'
        elif self.status == self.STATUS__FILE_COPY_ERROR:
            self.statusMsg = 'Unable to copy one or more of the specified files to TSC computer'

    def complete(self):
        # We call this method when the "Copy to TSC" operation is
        # complete. This method just enables the "Start Copy" button
        # and disables the "Cancel Copy" button.
        if self.okFileCount > 0:
            self.btn_startCopy.set_sensitive(True)
        self.btn_cancelCopy.set_sensitive(False)

    def get_results(self):
        results = []
        piter = self.treestore.get_iter_root()
        while piter:
            # The inner loop iterates through all the children of
            # this parent
            child = self.treestore.iter_children(piter)
            while child:
                results.append(self.treestore.get_value(child, 0))
                child = self.treestore.iter_next(child)
            piter = self.treestore.iter_next(piter)
        return results

    def copyfilestotsc(self):
        # Copy all the files that we have in our filepaths attribute
        # to the TSC computer.
        for filepath in self.filepaths:
            # Break out of the loop if the user presses the "Cancel
            # Copy" button.
            if self.cancelFlag:
                self.logger.info('cancelFlag is %s exiting the iteration on filepaths loop' % self.cancelFlag)
                break
            # If the status of the file is STATUS__FILE_READY_TO_COPY,
            # then copy the file to the TSC computer and then confirm
            # that the file was actually copied by getting the
            # date/time attribute of the file from the TSC computer.
            fileStatus = self.tree_filepaths[filepath].statusCode
            if fileStatus == self.STATUS__FILE_READY_TO_COPY:
                tscFilename = os.path.basename(filepath)
                try:
                    tscFullPath = TSCTrackFile.copyToTSC(filepath, tscFilename, self.logger)
                    date_time, filename = TSCTrackFile.confirmFileTSC(tscFullPath, self.logger)
                    fileStatus = self.STATUS__OK
                except Exception as e:
                    self.logger.error('Error copying file %s: %s' % (filepath, str(e)))
                    fileStatus = self.STATUS__FILE_COPY_ERROR
                    self.setStatus(fileStatus)
                    date_time = None
                # Update our TreeStore (data model) with the results
                # from copying this file to the TSC computer
                self.update_tree(filepath, fileStatus, date_time)

        # We are done copying, so get the results and call the
        # callback function, if we were supplied one.
        self.complete()
        results = self.get_results()
        if self.callfn:
            self.logger.debug('CopyTSCTrackPage copyfilestotsc calling callfn')
            self.callfn(self.status, self.statusMsg, results)
        return results
#END
