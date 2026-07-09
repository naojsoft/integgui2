#
# Widgets.py -- integgui2's tag-aware text widget
#
# E. Jeschke
#
# The numbered, tag-aware text widget and its toolkit-neutral buffer model
# now live in ginga:
#
#   ginga.gw.text_model  -- TextModel + TextBufferRef (backend-neutral)
#   ginga.qtw.QtHelp     -- QTextSource (Qt render) + key helpers
#   ginga.qtw.Widgets    -- the TextSource widget wrapper
#
# This module re-exports that widget with integgui2's default monospace
# font.
#
from ginga.gw.Widgets import TextSource as _TextSource


class TextSource(_TextSource):
    """integgui2 TextSource defaulting to a fixed-width font.

    Code, tabular, and log content all rely on monospaced alignment;
    DejaVu Sans Mono matches the font the GTK version used (via the system
    default monospace).  Pages that want a different font override it.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.set_font('DejaVu Sans Mono', 10)
