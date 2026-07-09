#
# Russell Kackley (rkackley@naoj.org)
#
# Displays names and status of tracking coordinate files copied to TSC
# computer
#
import os, glob

from ginga.gw import Widgets
from ginga.misc import Bunch

from g2base.remoteObjects import remoteObjects as ro

from . import common
from . import Page

import Gen2.astro.TSCTrackFile as TSCTrackFile


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

        super().__init__(frame, name, title)

        self.okFileCount = 0
        self.filepaths = []
        # nested dir -> filename -> leaf Bunch model for the tree view
        self.tree_dict = {}
        # filepath -> leaf Bunch
        self.tree_filepaths = {}
        self.setStatus(self.STATUS__OK)
        self.cancelFlag = False
        self.callfn = None
        self.logger = None

        # Add a "Page" menu with a Close item
        menu = self.add_pulldownmenu("Page")
        item = menu.add_name("Close")
        item.add_callback("activated", lambda w: self.close())

        # The columns to display in the TreeView:  (header, key)
        self.columns = [('Filename', 'filename'), ('Status', 'status')]

        # create the TreeView that displays the filenames and status.
        # Nesting is 2 (directory node -> file leaf); 'filename' is the
        # leaf key.
        tv = Widgets.TreeView(auto_expand=True, sortable=False,
                              use_alt_row_color=True)
        tv.setup_table(self.columns, 2, 'filename')
        self.treeview = tv
        self.content.add_widget(tv, stretch=1)

        # bottom buttons
        self.btn_startCopy = Widgets.Button("Start Copy")
        self.btn_startCopy.add_callback("activated", lambda w: self.startCopy())
        self.btn_startCopy.set_enabled(False)
        self.leftbtns.add_widget(self.btn_startCopy)

        self.btn_cancelCopy = Widgets.Button("Cancel Copy")
        self.btn_cancelCopy.add_callback("activated",
                                         lambda w: self.cancelCopy())
        self.btn_cancelCopy.set_enabled(False)
        self.leftbtns.add_widget(self.btn_cancelCopy)

    def setup(self, callfn=None, filepaths=None, checkFormat=True,
              logger=ro.nullLogger()):
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
            self.treeview.clear()
            self.tree_dict = {}
            self.tree_filepaths = {}
            self.filepaths = []
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
        # they exist and are formatted correctly to serve as TSC tracking
        # coordinate files. We also update the tree model in this loop.
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

        # If we found one or more files that have the correct format,
        # enable the "Start Copy" button.  Otherwise, disable it.
        self.btn_startCopy.set_enabled(self.okFileCount > 0)

    def startCopy(self):
        # The callback for the "Start Copy" button
        self.setup()
        # Disable the "Start Copy" button and enable the "Cancel Copy" button
        self.btn_startCopy.set_enabled(False)
        self.btn_cancelCopy.set_enabled(True)
        # Set the cancelFlag to False prior to starting the copy operation
        self.cancelFlag = False
        # Run the "copy to TSC" method using gui_do
        common.view.gui_do(self.copyfilestotsc)

    def cancelCopy(self):
        # The callback for the "Cancel Copy" button
        self.cancelFlag = True

    def _status_bg(self, statusCode):
        # Background color for a row based on its status code
        if statusCode in (self.STATUS__FILE_PENDING,
                          self.STATUS__FILE_READY_TO_COPY):
            return 'yellow'
        elif statusCode == self.STATUS__OK:
            return 'green'
        elif statusCode in (self.STATUS__FILE_NOTFOUND_ERROR,
                            self.STATUS__FILE_FORMAT_ERROR,
                            self.STATUS__FILE_COPY_ERROR):
            return 'red'
        return None

    def _refresh_tree(self):
        # Rebuild the tree view from the model and re-apply row colors.
        self.treeview.set_tree(self.tree_dict)
        for key, leaf in self.tree_filepaths.items():
            bg = self._status_bg(leaf.statusCode)
            if bg is None:
                continue
            try:
                self.treeview.set_row_color([os.path.dirname(key),
                                             leaf.filename], bg=bg)
            except Exception:
                pass

    def update_tree(self, key, statusCode, date_time=None):
        # Update the tree model with the supplied key (basically the
        # filepath), statusCode, and date_time.
        self.logger.debug('CopyTSCTrackPage update_tree called key %s statusCode %d' % (key, statusCode))

        filename = os.path.basename(key)
        dirname = os.path.dirname(key)

        if statusCode == self.STATUS__OK:
            status = ' '.join([self.STATUS_INFO[statusCode], str(date_time)])
        else:
            status = self.STATUS_INFO[statusCode]

        if key in self.tree_filepaths:
            leaf = self.tree_filepaths[key]
            leaf.update(dict(status=status, statusCode=statusCode))
        else:
            leaf = Bunch.Bunch(filepath=key, filename=filename,
                               status=status, statusCode=statusCode)
            self.tree_filepaths[key] = leaf

        self.tree_dict.setdefault(dirname, {})[filename] = leaf
        self._refresh_tree()

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
        # Called when the "Copy to TSC" operation is complete: enable the
        # "Start Copy" button and disable the "Cancel Copy" button.
        if self.okFileCount > 0:
            self.btn_startCopy.set_enabled(True)
        self.btn_cancelCopy.set_enabled(False)

    def get_results(self):
        return list(self.tree_filepaths.values())

    def copyfilestotsc(self):
        # Copy all the files in our filepaths attribute to the TSC computer.
        for filepath in self.filepaths:
            # Break out of the loop if the user pressed "Cancel Copy".
            if self.cancelFlag:
                self.logger.info('cancelFlag is %s exiting the iteration on filepaths loop' % self.cancelFlag)
                break
            # If the file is ready to copy, copy it and confirm by getting
            # the date/time of the file from the TSC computer.
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
                # Update the model with the results from copying this file
                self.update_tree(filepath, fileStatus, date_time)

        # We are done copying, so get the results and call the callback
        # function, if we were supplied one.
        self.complete()
        results = self.get_results()
        if self.callfn:
            self.logger.debug('CopyTSCTrackPage copyfilestotsc calling callfn')
            self.callfn(self.status, self.statusMsg, results)
        return results

#END
