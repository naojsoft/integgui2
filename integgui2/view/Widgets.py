from ginga.qtw.QtHelp import (QtCore, QtGui, QWidget, QTextCursor, QFont,
                              QPainter, QColor)
from ginga.qtw import Widgets, QtHelp

from qtpy.QtCore import QEvent
from qtpy.QtWidgets import QToolTip
from qtpy.QtGui import QTextCharFormat, QTextOption

from ginga import colors
from ginga.gw import Widgets


class ButtonBox(Widgets.HBox):
    def __init__(self):
        super().__init__()

        # TODO: automatically recalculate and resize as needed
        self.btn_width = 30
        self.set_border_width(4)

    def add_widget(self, child):
        wd, ht = child.get_size()
        child.resize(self.btn_width, ht)
        child.cfg_expand(horizontal='minimum')

        super().add_widget(child, stretch=0)


class QNumberBar(QWidget):
    """Specialty class used by QNumberedTextEdit to provide line numbers
    and line marking icons.  See QNumberedTextEdit for use.
    """

    def __init__(self, *args, **kwargs):
        QWidget.__init__(self, *args, **kwargs)
        self.icon_px = 0
        self.edit = None
        # This is used to update the width of the control.
        # It is the highest line that is currently visibile.
        self.highest_line = 0
        self.nb_enabled = False

        self.icon_dct = dict()

    def setTextEdit(self, edit):
        self.edit = edit

    def show_line_numbers(self, tf):
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


class QEnhancedTextEdit(QtGui.QTextEdit):
    """Speciality class that enhances a QTextEdit to be able to easily color
    lines and provides some convenience functions for syntax highlighting.
    See QNumberedTextEdit for use.
    """
    def __init__(self, *args, **kwargs):
        QtGui.QTextEdit.__init__(self, *args, **kwargs)

        self.syntax_hl = None
        self.growing = True
        self.document().documentLayout().documentSizeChanged.connect(
            self.sizeChange_cb)
        self.heightMin = 0
        self.heightMax = 65000
        self.tt_cb = None
        self.tt_args = []

        self.setUndoRedoEnabled(True)

    def sizeChange_cb(self):
        if not self.growing:
            return
        docHeight = self.document().size().height()
        # add some margin to prevent auto scrollbars
        docHeight += 20
        if self.heightMin <= docHeight <= self.heightMax:
            self.setMaximumHeight(int(docHeight))

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
        if self.tt_cb is None or event.type() != QEvent.ToolTip:
            return super().event(event)

        args = [event]
        if len(self.tt_args) > 0:
            args.extend(self.tt_args)
        return self.tt_cb(*args)

    def set_tooltip_callback(self, func, *args):
        self.tt_cb = func
        self.tt_args = args

    def color_line(self, line_num, fgcolor=None, bgcolor=None):
        # NOTE: line numbers seem to be indexed from 0
        blk = self.document().findBlockByLineNumber(line_num - 1)
        cur = QTextCursor(blk)
        cur.movePosition(QTextCursor.StartOfBlock)
        cur.setPosition(cur.position() + blk.length(), QTextCursor.KeepAnchor)
        fmt = mkformat(fgcolor=fgcolor, bgcolor=bgcolor)
        #cur.mergeBlockCharFormat(fmt)
        cur.mergeCharFormat(fmt)


class QNumberedTextEdit(QtGui.QFrame):
    """Enhanced QTextEdit-like widget that can show line numbers and icons
    marking lines.
    """
    def __init__(self, *args, **kwargs):
        QtGui.QFrame.__init__(self, *args, **kwargs)

        self.setFrameStyle(QtGui.QFrame.StyledPanel | QtGui.QFrame.Sunken)

        # this is our embedded text widget
        self.tw = QEnhancedTextEdit()
        self.tw.setFrameStyle(QtGui.QFrame.NoFrame)
        self.tw.setAcceptRichText(False)
        self.tw.setMouseTracking(True)

        # this is our number bar
        self.nb = QNumberBar()
        self.nb.setTextEdit(self.tw)

        hbox = QtGui.QHBoxLayout(self)
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

    def show_line_numbers(self, tf):
        return self.nb.show_line_numbers(tf)

    def set_icon_column_px(self, pad_px):
        return self.nb.set_icon_column_px(pad_px)

    def set_icon_for_line(self, line, image):
        return self.nb.set_icon_for_line(line, image)

    def unset_icon_for_line(self, line):
        return self.nb.unset_icon_for_line(line)

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
        return QtGui.QFrame.eventFilter(object, event)

    def set_wrap(self, tf):
        if tf:
            self.tw.setLineWrapMode(QtGui.QTextEdit.WidgetWidth)
        else:
            self.tw.setLineWrapMode(QtGui.QTextEdit.NoWrap)

    def set_editable(self, tf):
        self.tw.setReadOnly(not tf)

    def set_text(self, text):
        self.tw.setPlainText(text)

    def set_font(self, qfont):
        self.tw.setFont(qfont)
        self.nb.setFont(qfont)

    def color_line(self, line_num, fgcolor=None, bgcolor=None):
        return self.tw.color_line(line_num, fgcolor=fgcolor, bgcolor=bgcolor)


class NumberedTextArea(Widgets.WidgetBase):

    def __init__(self, wrap=False, editable=False):
        super().__init__()

        # tw = QtGui.QTextEdit()
        self.widget = QNumberedTextEdit()
        tw = self.widget.get_internal_text_widget()
        tw.setReadOnly(not editable)
        if wrap:
            tw.setLineWrapMode(QtGui.QTextEdit.WidgetWidth)
        else:
            tw.setLineWrapMode(QtGui.QTextEdit.NoWrap)
        self.tw = tw

        for name in ['tooltip']:
            self.enable_callback(name)

    def append_text(self, text, autoscroll=True):
        if text.endswith('\n'):
            text = text[:-1]
        self.tw.append(text)
        if not autoscroll:
            return

        self.tw.moveCursor(QTextCursor.End)
        self.tw.moveCursor(QTextCursor.StartOfLine)
        self.tw.ensureCursorVisible()

    def get_text(self):
        return self.tw.document().toPlainText()

    def clear(self):
        self.tw.clear()

    def set_text(self, text):
        self.clear()
        self.append_text(text)

    def set_editable(self, tf):
        self.tw.setReadOnly(not tf)

    def set_limit(self, numlines):
        # self.tw.setMaximumBlockCount(numlines)
        pass

    def set_font(self, font, size=10):
        if not isinstance(font, QFont):
            font = self.get_font(font, size)
        self.tw.setCurrentFont(font)

    def set_wrap(self, kind):
        if isinstance(kind, bool):
            # <-- old API
            kind = 'full' if kind else 'none'

        if kind == 'none':
            self.tw.setLineWrapMode(QtGui.QTextEdit.NoWrap)
        else:
            self.tw.setLineWrapMode(QtGui.QTextEdit.WidgetWidth)
            if kind in ('char', 'full'):
                self.tw.setWordWrapMode(QTextOption.WrapAnywhere)
            elif kind == 'word':
                self.tw.setWordWrapMode(QTextOption.WrapAtWordBoundaryOrAnywhere)

    def set_scroll_pos(self, pos):
        vsb = self.tw.verticalScrollBar()
        if pos == -1:
            vsb.setValue(vsb.maximum())
        else:
            vsb.setValue(pos)

    def show_line_numbers(self, tf):
        return self.widget.show_line_numbers(tf)

    def enable_line_icons(self, tf):
        self.widget.nb.set_icon_column_px(24 if tf else 0)

    def enable_tooltips(self, tf):
        self.tw.set_tooltip_callback(self._tt_cb if tf else None)

    def _tt_cb(self, event):
        cur = self.tw.cursorForPosition(event.pos())
        # print("hovering over character {} in line {}".format(cur.positionInBlock(),
        #                                                      cur.blockNumber()))
        # cur.select(QTextCursor.WordUnderCursor)
        # varref = cur.selectedText().strip()
        # if len(varref) != 0:
        #     # TODO: lookup varref definition
        #     vardef = f"FOO! {varref}"
        #     QToolTip.showText(event.globalPos(), vardef)

        pos_in_line = cur.positionInBlock()
        block = cur.block()
        line_no = block.firstLineNumber()
        text = block.text()
        res = []
        self.make_callback('tooltip', res, line_no, pos_in_line, text)
        if len(res) > 0:
            # NOTE: text to be displayed (if any) is returned as the
            # first item in res
            text = res[0]
            QToolTip.showText(event.globalPos(), text)

        return True

    def set_syntax_highlighter_class(self, klass):
        return self.tw.set_syntax_highlighter_class(klass)

    def get_syntax_highlighter(self):
        return self.tw.get_syntax_highlighter()


class FixedLayout(Widgets.ContainerBase):
    """A container widget in which children can be placed at fixed
    positions.
    """

    def __init__(self):
        super().__init__()

        self.widget = QWidget()

    def add_widget(self, child, x_px, y_px):
        child_w = child.get_widget()
        child_w.setParent(self.widget)

        child_w.move(x_px, y_px)
        self.add_ref(child)

    def remove(self, child, delete=False):
        if child not in self.children:
            raise ValueError("Widget is not a child of this container")
        self.children.remove(child)

        child_w = child.get_widget()
        child_w.unParent()
        if delete:
            child_w.deleteLater()

        self.make_callback('widget-removed', child)


def mkformat(fgcolor=None, bgcolor=None, style=[], baseformat=None):
    """Return a QTextCharFormat with the given attributes.
    """
    _format = QTextCharFormat()
    if baseformat is not None:
        _format.merge(baseformat)

    if fgcolor is not None:
        _fgcolor = QColor()
        rgb = colors.resolve_color(fgcolor, format='tuple')
        _fgcolor.setRgbF(rgb[0], rgb[1], rgb[2], 1.0)
        _format.setForeground(_fgcolor)

    if bgcolor is not None:
        _bgcolor = QColor()
        rgb = colors.resolve_color(bgcolor, format='tuple')
        _bgcolor.setRgbF(rgb[0], rgb[1], rgb[2], 1.0)
        _format.setBackground(_bgcolor)

    if 'bold' in style:
        _format.setFontWeight(QFont.Bold)
    if 'italic' in style:
        _format.setFontItalic(True)

    return _format
