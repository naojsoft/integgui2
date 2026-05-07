from qtpy.QtWidgets import QFrame, QWidget, QTextEdit, QHBoxLayout, QToolTip
from qtpy import QtGui
from qtpy.QtGui import QPainter, QFont, QTextCursor
from qtpy.QtCore import QEvent

from ope_syntax import mkformat

__all__ = ['QEnhancedTextEdit', 'QNumberedTextEdit']


class QNumberBar(QWidget):
    """Specialty class used by NumberedTextEdit to provide line numbers
    and line marking icons.  See NumberedTextEdit for use.
    """

    def __init__(self, *args):
        QWidget.__init__(self, *args)
        self.icon_px = 0
        self.edit = None
        # This is used to update the width of the control.
        # It is the highest line that is currently visibile.
        self.highest_line = 0
        self.nb_enabled = False

        self.icon_dct = dict()

    def setTextEdit(self, edit):
        self.edit = edit

    def numbers_onoff(self, tf):
        self.nb_enabled = tf
        self.update()

    def set_icon_column_px(self, pad_px):
        self.icon_px = pad_px
        self.update()

    def set_icon_for_line(self, line, image):
        self.icon_dct[line] = image
        self.update()

    def unset_icon_for_line(self, line):
        if line in self.icon_dct:
            del self.icon_dct[line]
        self.update()

    def clear_icons(self):
        self.icon_dct = dict()
        self.update()

    def update(self, *args):
        '''
        Updates the number bar to display the current set of numbers.
        Also, adjusts the width of the number bar if necessary.
        '''
        if not self.nb_enabled:
            width = self.icon_px
        else:
            # The + 4 is used to compensate for the current line being bold.
            width = self.fontMetrics().width(str(self.highest_line)) + 4 + self.icon_px
        if self.width() != width:
            self.setFixedWidth(width)
        QWidget.update(self, *args)

    def paintEvent(self, event):
        contents_y = self.edit.verticalScrollBar().value()
        page_bottom = contents_y + self.edit.viewport().height()
        font_metrics = self.fontMetrics()
        current_block = self.edit.document().findBlock(self.edit.textCursor().position())

        painter = QPainter(self)

        line_count = 0
        # Iterate over all text blocks in the document.
        block = self.edit.document().begin()
        while block.isValid():
            line_count += 1

            # The top left position of the block in the document
            position = self.edit.document().documentLayout().blockBoundingRect(block).topLeft()

            # Check if the position of the block is out side of the visible
            # area.
            if position.y() > page_bottom:
                break

            # See if there is an icon to be drawn here
            icon_img = self.icon_dct.get(line_count, None)
            if icon_img is not None:
                x = self.width() - self.icon_px
                y = round(position.y()) - contents_y
                painter.drawImage(x, y, icon_img)

            # We want the line number for the selected line to be bold.
            bold = False
            if block == current_block:
                bold = True
                font = painter.font()
                font.setBold(True)
                painter.setFont(font)

            # Draw the line number right justified at the y position of the
            # line. 3 is a magic padding number. drawText(x, y, text).
            #x = self.width() - font_metrics.width(str(line_count)) - 3
            x = self.width() - self.icon_px - font_metrics.width(str(line_count)) - 3
            y = round(position.y()) - contents_y + font_metrics.ascent()
            painter.drawText(x, y, str(line_count))

            # Remove the bold style if it was set previously.
            if bold:
                font = painter.font()
                font.setBold(False)
                painter.setFont(font)

            block = block.next()

        self.highest_line = self.edit.document().blockCount()
        painter.end()

        QWidget.paintEvent(self, event)


class QEnhancedTextEdit(QTextEdit):
    """Speciality class that enhances a QTextEdit to be able to easily color
    lines and provides some convenience functions for syntax highlighting.
    See NumberedTextEdit for use.
    """

    def __init__(self, *args):
        QTextEdit.__init__(self, *args)

        self.syntax_hl = None

    # def mouseMoveEvent(self, event):
    #     pt = event.pos()
    #     cur = self.cursorForPosition(pt)
    #     print("hovering over character {} in line {}".format(cur.positionInBlock(),
    #                                                          cur.blockNumber()))
    #     super().mouseMoveEvent(event)

    def set_syntax_highlighter_class(self, klass):
        self.syntax_hl = klass(self.document())

    def get_syntax_highlighter(self):
        return self.syntax_hl

    def event(self, event):
        if event.type() != QEvent.ToolTip:
            return super().event(event)

        pt = event.pos()
        cur = self.cursorForPosition(pt)
        # print("hovering over character {} in line {}".format(cur.positionInBlock(),
        #                                                      cur.blockNumber()))
        cur.select(QTextCursor.WordUnderCursor)
        varref = cur.selectedText().strip()
        if len(varref) != 0:
            # TODO: lookup varref definition
            vardef = f"FOO! {varref}"
            QToolTip.showText(event.globalPos(), vardef)

        # super().event(event)
        return True

    def color_line(self, line_num, fgcolor=None, bgcolor=None):
        # NOTE: line numbers seem to be indexed from 0
        blk = self.document().findBlockByLineNumber(line_num - 1)
        cur = QTextCursor(blk)
        cur.movePosition(QTextCursor.StartOfBlock)
        cur.setPosition(cur.position() + blk.length(), QTextCursor.KeepAnchor)
        fmt = mkformat(fgcolor=fgcolor, bgcolor=bgcolor)
        #cur.mergeBlockCharFormat(fmt)
        cur.mergeCharFormat(fmt)


class QNumberedTextEdit(QFrame):
    """Enhanced QTextEdit-like widget that can show line numbers and icons
    marking lines.
    """

    def __init__(self, *args):
        QFrame.__init__(self, *args)

        self.setFrameStyle(QFrame.StyledPanel | QFrame.Sunken)

        # this is our embedded text widget
        self.tw = QEnhancedTextEdit()
        self.tw.setFrameStyle(QFrame.NoFrame)
        self.tw.setAcceptRichText(False)
        self.tw.setMouseTracking(True)

        # this is our number bar
        self.nb = QNumberBar()
        self.nb.setTextEdit(self.tw)

        hbox = QHBoxLayout(self)
        hbox.setSpacing(0)
        hbox.setContentsMargins(0, 0, 0, 0)
        hbox.addWidget(self.nb)
        hbox.addWidget(self.tw)

        self.tw.installEventFilter(self)
        self.tw.viewport().installEventFilter(self)

    def get_number_bar(self):
        return self.nb

    def get_internal_text_widget(self):
        return self.tw

    def numbers_onoff(self, tf):
        return self.nb.numbers_onoff(tf)

    def set_icon_column_px(self, pad_px):
        return self.nb.set_icon_column_px(pad_px)

    def set_icon_for_line(self, line, image):
        return self.nb.set_icon_for_line(line, image)

    def unset_icon_for_line(self, line):
        return self.nb.unset_icon_for_line(line, image)

    def clear_icons(self):
        return self.nb.clear_icons()

    def set_syntax_highlighter_class(self, klass):
        return self.tw.set_syntax_highlighter_class(klass)

    def get_syntax_highlighter(self):
        return self.tw.get_syntax_highlighter()

    def eventFilter(self, object, event):
        # Update the line numbers for all events on the text edit and
        # the viewport. This is easier than connecting all necessary signals.
        if object in (self.tw, self.tw.viewport()):
            self.nb.update()
            return False
        return QFrame.eventFilter(object, event)

    def set_wrap(self, tf):
        if tf:
            self.tw.setLineWrapMode(QTextEdit.WidgetWidth)
        else:
            self.tw.setLineWrapMode(QTextEdit.NoWrap)

    def set_editable(self, tf):
        self.tw.setReadOnly(not tf)

    def set_text(self, text):
        self.tw.setPlainText(text)

    def set_font(self, qfont):
        self.tw.setFont(qfont)
        self.nb.setFont(qfont)

    def color_line(self, line_num, fgcolor=None, bgcolor=None):
        return self.tw.color_line(line_num, fgcolor=fgcolor, bgcolor=bgcolor)
