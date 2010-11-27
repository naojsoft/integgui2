# 
#[ Eric Jeschke (eric@naoj.org) --
#  Last edit: Fri Nov 26 14:33:26 HST 2010
#]

import gtk

# NOTE [1]:
#   There seems to be a bug in the gtk.FileChooserDialog() where if the
# directory contents are changing while the dialog is open it will sometimes
# crash the program.  For this reason I changed the class to create the
# widget each time it is needed and destroy it afterwards
#
    
class FileSelection(object):
    
    # Get the selected filename and print it to the console
    def file_ok_sel(self, w, rsp):
        filepath = w.get_filename()
        self.close(w)
        if rsp == 0:
            return
        
        self.callfn(filepath)

    def __init__(self, action=gtk.FILE_CHOOSER_ACTION_OPEN):
        self.action = action

    def _create_widget(self, action):
        # Create a new file selection widget
        self.filew = gtk.FileChooserDialog(title="Select a file",
                                           action=action)
        # See NOTE [1]
        #self.filew.connect("destroy", self.close)
        if action == gtk.FILE_CHOOSER_ACTION_SAVE:
            self.filew.add_buttons(gtk.STOCK_SAVE, 1, gtk.STOCK_CANCEL, 0)
        else:
            self.filew.add_buttons(gtk.STOCK_OPEN, 1, gtk.STOCK_CANCEL, 0)
        self.filew.set_default_response(1)
        
        # Connect the ok_button to file_ok_sel method
        #self.filew.ok_button.connect("clicked", self.file_ok_sel)
        self.filew.connect("response", self.file_ok_sel)
    
        # Connect the cancel_button to destroy the widget
        #self.filew.cancel_button.connect("clicked", self.close)
    
    def popup(self, title, callfn, initialdir=None,
              filename=None):
        # See NOTE [1]
        self._create_widget(self.action)
        
        self.callfn = callfn
        self.filew.set_title(title)
        if initialdir:
            self.filew.set_current_folder(initialdir)

        if filename:
            #self.filew.set_filename(filename)
            self.filew.set_current_name(filename)

        self.filew.show()

    def close(self, widget):
        # See NOTE [1]
        #self.filew.hide()
        self.filew.destroy()
        self.filew = None


      
#END
