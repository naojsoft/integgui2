import gtk

class FileSelection(object):
    
    # Get the selected filename and print it to the console
    def file_ok_sel(self, w):
        filepath = self.filew.get_filename()
        self.close(w)
        self.callfn(filepath)

    def __init__(self):
        # Create a new file selection widget
        self.filew = gtk.FileSelection("Select a file")
        self.filew.connect("destroy", self.close)
        
        # Connect the ok_button to file_ok_sel method
        self.filew.ok_button.connect("clicked", self.file_ok_sel)
    
        # Connect the cancel_button to destroy the widget
        self.filew.cancel_button.connect("clicked", self.close)
    
    def popup(self, title, callfn, initialdir=None,
              filename=None):
        self.callfn = callfn
        self.filew.set_title(title)

        if filename:
            self.filew.set_filename(filename)

        self.filew.show()

    def close(self, widget):
        self.filew.hide()


      
#END
