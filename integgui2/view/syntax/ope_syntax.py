from qtpy.QtGui import QSyntaxHighlighter, QTextCharFormat, QColor, QFont
from qtpy import QtCore

from ginga import colors

from ..Widgets import mkformat

# Syntax styles for OPE files
OPE_STYLES = {
    'comment1': mkformat(fgcolor='darkgreen', style=['italic']),
    'comment2': mkformat(fgcolor='saddlebrown', style=['italic']),
    'comment3': mkformat(fgcolor='indianred', style=['italic']),
    'varref': mkformat(fgcolor='royalblue'),
    'badref': mkformat(fgcolor='darkorange'),
    #'operator': mkformat(fgcolor='red'),
    'string': mkformat(fgcolor='coral'),
    'string2': mkformat(fgcolor='darkmagenta'),
    'numbers': mkformat(fgcolor='brown'),
}

class OPEHighlighter (QSyntaxHighlighter):
    """Syntax highlighter for OPE command files.
    """
    def __init__(self, parent):
        super().__init__(parent)

        self.defined_vars = set([])

        rules = []

        # Keyword, operator, and brace rules
        # rules += [(r'\b%s\b' % w, 0, STYLES['keyword'])
        #     for w in OPEHighlighter.keywords]

        # All other rules
        rules += [
            # variable reference ($)
            (r'\$[\w_\.]+', 0, 'varref'),

            # Numeric literals
            (r'\b[+-]?[0-9]+[lL]?\b', 0, 'numbers'),
            (r'\b[+-]?0[xX][0-9A-Fa-f]+[lL]?\b', 0, 'numbers'),
            (r'\b[+-]?[0-9]+(?:\.[0-9]+)?(?:[eE][+-]?[0-9]+)?\b', 0, 'numbers'),

            # Double-quoted string, possibly containing escape sequences
            (r'"[^"\\]*(\\.[^"\\]*)*"', 0, 'string'),
            # Single-quoted string, possibly containing escape sequences
            (r"'[^'\\]*(\\.[^'\\]*)*'", 0, 'string'),

            # comments
            (r'#[^#][^\n]*', 0, 'comment1'),
            (r'##[^#][^\n]*', 0, 'comment2'),
            (r'###[^\n]*', 0, 'comment3'),
        ]

        # Build a QRegExp for each pattern
        self.rules = [(QtCore.QRegExp(pat), index, OPE_STYLES[kwd], kwd)
                      for (pat, index, kwd) in rules]

    def highlightBlock(self, text):
        """Apply syntax highlighting to the given block of text.
        """
        # Do other syntax formatting
        for expression, nth, format, keyword in self.rules:
            index = expression.indexIn(text, 0)
            while index >= 0:
                # We actually want the index of the nth match
                index = expression.pos(nth)
                length = len(expression.cap(nth))
                if keyword == 'varref':
                    # get variable name
                    refname = text[index:index + length][1:]
                    if refname not in self.defined_vars:
                        format = OPE_STYLES['badref']

                self.setFormat(index, length, format)
                index = expression.indexIn(text, index + length)

        self.setCurrentBlockState(0)

    def set_defined_vars(self, varset):
        """Call this with the set of defined references after the OPE
        file has been scanned.
        """
        self.defined_vars = varset
        self.rehighlight()
