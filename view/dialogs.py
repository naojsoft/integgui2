# 
#[ Eric Jeschke (eric@naoj.org) --
#  Last edit: Tue May 18 10:19:44 HST 2010
#]

import gtk

class FileSelection(object):
    
    # Get the selected filename and print it to the console
    def file_ok_sel(self, w, rsp):
        self.close(w)
        if rsp == 0:
            return
        
        filepath = self.filew.get_filename()
        self.callfn(filepath)

    def __init__(self):
        # Create a new file selection widget
        self.filew = gtk.FileChooserDialog(title="Select a file")
        self.filew.connect("destroy", self.close)
        self.filew.add_buttons(gtk.STOCK_OPEN, 1, gtk.STOCK_CANCEL, 0)
        self.filew.set_default_response(1)
        
        # Connect the ok_button to file_ok_sel method
        #self.filew.ok_button.connect("clicked", self.file_ok_sel)
        self.filew.connect("response", self.file_ok_sel)
    
        # Connect the cancel_button to destroy the widget
        #self.filew.cancel_button.connect("clicked", self.close)
    
    def popup(self, title, callfn, initialdir=None,
              filename=None):
        self.callfn = callfn
        self.filew.set_title(title)
        if initialdir:
            self.filew.set_current_folder(initialdir)

        if filename:
            self.filew.set_filename(filename)

        self.filew.show()

    def close(self, widget):
        self.filew.hide()


      
#END
