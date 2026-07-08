import weakref

from ginga import colors
from ginga.gw import Widgets
from ginga.misc import Callback
from ginga.events import KeyEvent

from ginga.qtw.QtHelp import (QtCore, QtGui, QWidget, QTextCursor, QFont,
                              QPainter, QColor)

from qtpy.QtCore import QEvent
from qtpy.QtWidgets import QToolTip
from qtpy.QtGui import QTextCharFormat, QTextOption


class TextBufferRef(object):
    """Live reference to a character offset in a QTextSource buffer.

    The ref follows inserts and deletes performed through the owning text
    widget.  Gravity controls how the ref behaves when text is inserted at
    exactly the ref's offset.
    """

    def __init__(self, buffer, offset, gravity='right'):
        if gravity not in ('left', 'right'):
            raise ValueError("gravity must be 'left' or 'right'")
        self._buffer = buffer
        self._offset = buffer._clamp_offset(offset)
        self._gravity = gravity
        self._valid = True

    def get_offset(self):
        return self._offset

    def get_gravity(self):
        return self._gravity

    def is_valid(self):
        return self._valid

    def get_line_column(self):
        self._check_valid()
        text = self._buffer.get_text()
        prefix = text[:self._offset]
        line = prefix.count('\n')
        last_nl = prefix.rfind('\n')
        col = self._offset if last_nl < 0 else self._offset - last_nl - 1
        return (line, col)

    def get_line(self):
        self._check_valid()
        return self._buffer._line_of_offset(self._offset)

    def set_offset(self, offset):
        self._check_valid()
        self._set_offset(offset)

    def set_line(self, lineno):
        self._check_valid()
        self._set_offset(self._buffer._offset_of_line_start(lineno))

    def to_ref(self, other):
        self._check_valid()
        if not isinstance(other, TextBufferRef):
            raise TypeError("to_ref requires a TextBufferRef")
        if other._buffer is not self._buffer:
            raise ValueError("TextBufferRef belongs to a different buffer")
        if not other._valid:
            raise ValueError("Source TextBufferRef has been invalidated")
        self._set_offset(other._offset)

    def copy(self):
        self._check_valid()
        return self._buffer.create_ref(self._offset, self._gravity)

    def to_line_start(self):
        self._check_valid()
        self._set_offset(self._buffer._offset_of_line_start(self.get_line()))

    def to_line_end(self):
        self._check_valid()
        text = self._buffer.get_text()
        idx = text.find('\n', self._offset)
        if idx < 0:
            idx = len(text)
        self._set_offset(idx)

    def to_next_line(self):
        self._check_valid()
        text = self._buffer.get_text()
        idx = text.find('\n', self._offset)
        if idx >= 0:
            self._set_offset(idx + 1)

    def to_prev_line(self):
        self._check_valid()
        line = self.get_line()
        if line > 0:
            self._set_offset(self._buffer._offset_of_line_start(line - 1))

    def to_next_char(self):
        self._check_valid()
        self._set_offset(self._offset + 1)

    def to_prev_char(self):
        self._check_valid()
        self._set_offset(self._offset - 1)

    def _check_valid(self):
        if not self._valid:
            raise ValueError("TextBufferRef has been invalidated")

    def _set_offset(self, new_offset):
        self._offset = self._buffer._clamp_offset(new_offset)
        self._buffer._refresh_icon_gutter()

    def _invalidate(self):
        self._valid = False


class QNumberBar(QWidget):
    """Specialty class used by QTextSource to provide line numbers
    and line marking icons.  See QTextSource for use.
    """

    def __init__(self, *args, **kwargs):
        QWidget.__init__(self, *args, **kwargs)
        self.icon_px = 0
        self.edit = None
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
        if not self.nb_enabled:
            width = self.icon_px
        else:
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
        block = self.edit.document().begin()
        while block.isValid():
            line_count += 1
            position = self.edit.document().documentLayout().blockBoundingRect(block).topLeft()
            if position.y() > page_bottom:
                break

            icon_img = self.icon_dct.get(line_count, None)
            if icon_img is not None:
                x = self.width() - self.icon_px
                y = round(position.y()) - contents_y
                painter.drawImage(x, y, icon_img)

            bold = False
            if block == current_block:
                bold = True
                font = painter.font()
                font.setBold(True)
                painter.setFont(font)

            x = self.width() - self.icon_px - font_metrics.width(str(line_count)) - 3
            y = round(position.y()) - contents_y + font_metrics.ascent()
            painter.drawText(x, y, str(line_count))

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
    See QTextSource for use.
    """
    def __init__(self, *args, **kwargs):
        QtGui.QTextEdit.__init__(self, *args, **kwargs)

        self.syntax_hl = None
        # When growing is True the widget caps its max height to the document
        # height (auto-sizing to content).  Default off so the editor instead
        # fills the space it is given, with text anchored at the top rather
        # than floating in the vertical center of an oversized cell.
        self.growing = False
        self.document().documentLayout().documentSizeChanged.connect(
            self.sizeChange_cb)
        self.heightMin = 0
        self.heightMax = 65000
        self.tt_cb = None
        self.tt_args = []

        # Undo/redo is modeled at the QTextSource level (see its
        # _undo_stack) so that refs and tag intervals are restored along
        # with the text.  Qt's native document undo would edit the
        # document directly, bypassing that model, so we disable it here.
        self.setUndoRedoEnabled(False)

    def sizeChange_cb(self):
        if not self.growing:
            return
        docHeight = self.document().size().height()
        docHeight += 20
        if self.heightMin <= docHeight <= self.heightMax:
            self.setMaximumHeight(int(docHeight))

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
        blk = self.document().findBlockByLineNumber(line_num - 1)
        cur = QTextCursor(blk)
        cur.movePosition(QTextCursor.StartOfBlock)
        cur.setPosition(cur.position() + blk.length(), QTextCursor.KeepAnchor)
        fmt = mkformat(fgcolor=fgcolor, bgcolor=bgcolor)
        cur.mergeCharFormat(fmt)


class QTextSource(QtGui.QFrame, Callback.Callbacks):
    """Enhanced QTextEdit-like widget with TextSource-style refs and tags.

    The widget keeps a plain-text model, live refs, and applied tag intervals
    as the source of truth.  The underlying ``QTextEdit`` is treated as the
    editable/rendered view of that model rather than as the authoritative data
    structure.

    It is also a ``Callback.Callbacks`` so it can notify observers (normally
    the Ginga ``TextSource`` wrapper) through the standard add_callback/
    make_callback machinery.  Callback categories: 'changed' (model text
    changed), 'cursor-moved' (cursor/selection changed), and 'key-press'
    (a key was pressed; the keyname is passed and a truthy return consumes
    the event).
    """

    def __init__(self, *args, **kwargs):
        QtGui.QFrame.__init__(self, *args, **kwargs)
        Callback.Callbacks.__init__(self)

        self.setFrameStyle(QtGui.QFrame.StyledPanel | QtGui.QFrame.Sunken)

        self.tw = QEnhancedTextEdit()
        self.tw.setFrameStyle(QtGui.QFrame.NoFrame)
        self.tw.setAcceptRichText(False)
        self.tw.setMouseTracking(True)

        self.nb = QNumberBar()
        self.nb.setTextEdit(self.tw)

        hbox = QtGui.QHBoxLayout(self)
        hbox.setSpacing(0)
        hbox.setContentsMargins(0, 0, 0, 0)
        hbox.addWidget(self.nb)
        hbox.addWidget(self.tw)

        self.tw.installEventFilter(self)
        self.tw.viewport().installEventFilter(self)

        self._text = ''
        self._refs = weakref.WeakSet()
        self._named_refs = {}
        self._tag_defs = {}
        self._tags = []
        self._tag_seq = 0
        self._icon_refs = {}
        self._cursor = 0
        self._sel_start = 0
        self._sel_end = 0
        self._show_icon_gutter = False
        self._syncing = False
        self._applying_formats = False

        # Model-level undo/redo (mirrors the pg TextSource design).  Each
        # entry records a single _replace_range edit as
        # (start, old_text, new_text, cursor_before, cursor_after) so it
        # can be inverted with refs and tags kept consistent.
        self._undo_stack = []
        self._redo_stack = []
        self._undo_limit = 500
        self._in_undo_redo = False

        for name in ('changed', 'cursor-moved', 'key-press', 'line-clicked'):
            self.enable_callback(name)

        self.tw.textChanged.connect(self._on_editor_text_changed)
        self.tw.cursorPositionChanged.connect(self._on_cursor_position_changed)

    def get_number_bar(self):
        return self.nb

    def get_internal_text_widget(self):
        return self.tw

    def eventFilter(self, obj, event):
        if obj in (self.tw, self.tw.viewport()):
            etype = event.type()
            if etype == QEvent.KeyPress:
                kev = _make_key_event(event)
                if kev is not None:
                    # A truthy return from a 'key-press' callback means the
                    # key was handled, so we consume the event.
                    if self.make_callback('key-press', kev):
                        return True
            elif (etype == QEvent.MouseButtonPress and
                  obj is self.tw.viewport()):
                # Report the clicked line (0-based); does not consume the
                # event, so normal cursor placement still happens.
                cur = self.tw.cursorForPosition(event.pos())
                self.make_callback('line-clicked', cur.blockNumber())
            self.nb.update()
            return False
        return QtGui.QFrame.eventFilter(self, obj, event)

    def get_length(self):
        return len(self._text)

    def get_text(self):
        return self._text

    def get_text_range(self, start_ref, end_ref):
        """Return the text spanning ``[start_ref, end_ref)``."""
        start = self._offset_of(start_ref)
        end = self._offset_of(end_ref)
        if start > end:
            start, end = end, start
        return self._text[start:end]

    def clear(self):
        self.set_text('')

    def set_text(self, text):
        """Replace the full buffer contents.

        This is destructive with respect to refs and applied tags: existing
        refs are invalidated and applied tag intervals are cleared.
        """
        self._text = '' if text is None else str(text)
        self._cursor = 0
        self._sel_start = 0
        self._sel_end = 0
        self._tags = []
        self._undo_stack = []
        self._redo_stack = []
        self._invalidate_all_refs()
        self._named_refs.clear()
        self._icon_refs.clear()
        self._set_editor_text(self._text)
        self._apply_all_formats()
        self._refresh_icon_gutter()
        self.tw.document().setModified(False)

    def insert_text(self, ref, text, tags=None):
        """Insert text at ``ref`` and optionally apply tags to that range."""
        if text is None or text == '':
            return
        offset = self._offset_of(ref)
        self._replace_range(offset, offset, str(text), tags=tags)

    def delete_range(self, start_ref, end_ref):
        """Delete the text spanning ``[start_ref, end_ref)``."""
        start = self._offset_of(start_ref)
        end = self._offset_of(end_ref)
        if start > end:
            start, end = end, start
        if start == end:
            return
        self._replace_range(start, end, '')

    def create_ref(self, offset, gravity='right'):
        """Create a live buffer ref at ``offset``."""
        ref = TextBufferRef(self, offset, gravity=gravity)
        self._refs.add(ref)
        return ref

    def remove_ref(self, ref):
        """Invalidate a ref and detach any named/icon bindings that use it."""
        if not isinstance(ref, TextBufferRef):
            return
        if not ref.is_valid():
            return
        for name, named_ref in list(self._named_refs.items()):
            if named_ref is ref:
                del self._named_refs[name]
        if ref in self._icon_refs:
            del self._icon_refs[ref]
        ref._invalidate()
        self._refresh_icon_gutter()

    def create_named_ref(self, name, offset, gravity='right'):
        """Create a live ref and bind it to ``name``."""
        existing = self._named_refs.get(name)
        if existing is not None:
            self.remove_ref(existing)
        ref = self.create_ref(offset, gravity=gravity)
        self._named_refs[name] = ref
        return ref

    def get_named_ref(self, name):
        return self._named_refs.get(name)

    def remove_named_ref(self, name):
        ref = self._named_refs.pop(name, None)
        if ref is not None:
            self.remove_ref(ref)

    def get_ref_start(self):
        return self.create_ref(0, 'right')

    def get_ref_end(self):
        return self.create_ref(len(self._text), 'right')

    def get_ref_bounds(self):
        return (self.get_ref_start(), self.get_ref_end())

    def get_ref_line_start(self, lineno):
        return self.create_ref(self._offset_of_line_start(lineno), 'right')

    def get_ref_line_end(self, lineno):
        start = self._offset_of_line_start(lineno)
        idx = self._text.find('\n', start)
        end = len(self._text) if idx < 0 else idx
        return self.create_ref(end, 'right')

    def create_tag(self, name, attrs=None, **kwdargs):
        """Define or redefine a named display tag."""
        attrs = {} if attrs is None else dict(attrs)
        attrs.update(kwdargs)
        self._tag_defs[name] = attrs
        # A tag definition only affects rendering where the tag is applied.
        # Defining a brand-new (unapplied) tag needs no reformat, which keeps
        # bulk tag creation (e.g. one tag per AST node) cheap.
        if self.has_tag(name):
            self._apply_all_formats()

    def remove_tag_def(self, name):
        if name in self._tag_defs:
            del self._tag_defs[name]
        self._tags = [tag for tag in self._tags if tag['name'] != name]
        self._apply_all_formats()

    def has_tag(self, name):
        return any(tag['name'] == name for tag in self._tags)

    def apply_tag(self, name, start_ref, end_ref):
        """Apply a previously-defined tag across a buffer range."""
        if name not in self._tag_defs:
            raise ValueError("Unknown tag: %s" % (name,))
        start = self._offset_of(start_ref)
        end = self._offset_of(end_ref)
        if start > end:
            start, end = end, start
        if start == end:
            return
        self._add_tag_interval(name, start, end)
        self._apply_all_formats(region=(start, end))

    def remove_tag(self, name, start_ref, end_ref):
        """Clip a tag out of the given buffer range."""
        start = self._offset_of(start_ref)
        end = self._offset_of(end_ref)
        if start > end:
            start, end = end, start
        next_tags = []
        for tag in self._tags:
            if tag['name'] != name or tag['end'] <= start or tag['start'] >= end:
                next_tags.append(tag)
                continue
            if tag['start'] < start:
                next_tags.append(dict(tag, end=start))
            if tag['end'] > end:
                next_tags.append(dict(tag, start=end))
        self._tags = next_tags
        self._apply_all_formats(region=(start, end))

    def get_tags_at(self, ref):
        offset = self._offset_of(ref)
        names = []
        seen = set()
        for tag in self._tags:
            if tag['start'] <= offset < tag['end'] and tag['name'] not in seen:
                names.append(tag['name'])
                seen.add(tag['name'])
        return names

    def get_tags_range(self, start_ref, end_ref):
        start = self._offset_of(start_ref)
        end = self._offset_of(end_ref)
        if start > end:
            start, end = end, start
        names = []
        seen = set()
        for tag in self._tags:
            if tag['end'] <= start or tag['start'] >= end:
                continue
            if tag['name'] not in seen:
                names.append(tag['name'])
                seen.add(tag['name'])
        return names

    def get_tag_region(self, name):
        """Return the overall ``(start_ref, end_ref)`` span of a named tag.

        This mirrors the old GTK ``get_region`` helper: it returns a single
        ref pair covering from the first occurrence of the tag to the last.
        Returns ``None`` if the tag is not applied anywhere.
        """
        spans = [tag for tag in self._tags if tag['name'] == name]
        if not spans:
            return None
        start = min(tag['start'] for tag in spans)
        end = max(tag['end'] for tag in spans)
        return (self.create_ref(start, 'right'),
                self.create_ref(end, 'right'))

    def get_tag_regions(self, name):
        """Return a list of ``(start_ref, end_ref)`` pairs, one per maximal
        contiguous run of the named tag."""
        spans = sorted((tag for tag in self._tags if tag['name'] == name),
                       key=lambda tag: tag['start'])
        if not spans:
            return []
        merged = []
        cur_start, cur_end = spans[0]['start'], spans[0]['end']
        for tag in spans[1:]:
            if tag['start'] <= cur_end:
                cur_end = max(cur_end, tag['end'])
            else:
                merged.append((cur_start, cur_end))
                cur_start, cur_end = tag['start'], tag['end']
        merged.append((cur_start, cur_end))
        return [(self.create_ref(s, 'right'), self.create_ref(e, 'right'))
                for s, e in merged]

    def find(self, query, start=None, case_insensitive=False):
        """Return the first match as ``(start_ref, end_ref)`` or ``None``."""
        match = self._find_offset(query, start=start,
                                  case_insensitive=case_insensitive)
        if match is None:
            return None
        return (self.create_ref(match[0], 'right'),
                self.create_ref(match[1], 'right'))

    def find_all(self, query, start=None, case_insensitive=False):
        """Return all non-overlapping matches as ref pairs."""
        matches = self._find_all_offsets(query, start=start,
                                         case_insensitive=case_insensitive)
        return [(self.create_ref(start_off, 'right'),
                 self.create_ref(end_off, 'right'))
                for start_off, end_off in matches]

    def replace(self, query, replacement, all=False, start=None,
                case_insensitive=False):
        """Replace one or all matches and return the replacement count."""
        if not query:
            return 0
        if all:
            matches = self._find_all_offsets(query, start=start,
                                             case_insensitive=case_insensitive)
        else:
            match = self._find_offset(query, start=start,
                                      case_insensitive=case_insensitive)
            matches = [] if match is None else [match]
        for start_off, end_off in reversed(matches):
            self._replace_range(start_off, end_off, replacement)
        return len(matches)

    def get_cursor(self):
        return self.create_ref(self._cursor, 'right')

    def set_cursor(self, ref):
        """Move the editor cursor to ``ref`` and clear any selection."""
        offset = self._offset_of(ref)
        self._cursor = offset
        self._sel_start = offset
        self._sel_end = offset
        self._apply_selection_to_editor()

    def has_selection(self):
        return self._sel_start != self._sel_end

    def get_selection_range(self):
        if self._sel_start == self._sel_end:
            return None
        start = min(self._sel_start, self._sel_end)
        end = max(self._sel_start, self._sel_end)
        return (self.create_ref(start, 'right'),
                self.create_ref(end, 'right'))

    # get_selection_bounds() is the canonical accessor used by page code;
    # it returns a (start_ref, end_ref) pair or None when there is no
    # selection.  Callers guard with has_selection().
    get_selection_bounds = get_selection_range

    def set_selection_range(self, start_ref, end_ref):
        """Select the text spanning ``[start_ref, end_ref)``."""
        start = self._offset_of(start_ref)
        end = self._offset_of(end_ref)
        self._sel_start = start
        self._sel_end = end
        self._cursor = end
        self._apply_selection_to_editor()

    def set_editable(self, tf):
        self.tw.setReadOnly(not tf)

    def set_wrap(self, kind):
        if isinstance(kind, bool):
            kind = 'hard' if kind else 'none'
        if kind == 'none':
            self.tw.setLineWrapMode(QtGui.QTextEdit.NoWrap)
        else:
            self.tw.setLineWrapMode(QtGui.QTextEdit.WidgetWidth)
            if kind == 'hard':
                self.tw.setWordWrapMode(QTextOption.WrapAnywhere)
            elif kind == 'word':
                self.tw.setWordWrapMode(QTextOption.WrapAtWordBoundaryOrAnywhere)
            else:
                raise ValueError("Invalid wrap mode: %s" % (kind,))

    def set_line_numbers(self, tf):
        self.nb.show_line_numbers(tf)

    def show_line_numbers(self, tf):
        self.set_line_numbers(tf)

    def set_icon_gutter(self, tf, pad_px=24):
        self._show_icon_gutter = bool(tf)
        self.nb.set_icon_column_px(pad_px if self._show_icon_gutter else 0)
        self._refresh_icon_gutter()

    def set_icon_column_px(self, pad_px):
        self._show_icon_gutter = pad_px > 0
        self.nb.set_icon_column_px(pad_px)
        self._refresh_icon_gutter()

    def set_icon_for_line(self, line, image):
        self.nb.set_icon_for_line(line, image)

    def unset_icon_for_line(self, line):
        self.nb.unset_icon_for_line(line)

    def clear_icons(self):
        self._icon_refs.clear()
        self.nb.clear_icons()

    def set_icon(self, ref, image):
        """Associate an icon with a ref so it follows text movement by line."""
        if not isinstance(ref, TextBufferRef):
            raise TypeError("set_icon requires a TextBufferRef")
        if ref._buffer is not self:
            raise ValueError("TextBufferRef belongs to a different buffer")
        if image is None:
            self._icon_refs.pop(ref, None)
        else:
            self._icon_refs.pop(ref, None)
            self._icon_refs[ref] = image
        self._refresh_icon_gutter()

    def scroll_to_ref(self, ref):
        """Ensure the line containing ``ref`` is visible."""
        cursor = QTextCursor(self.tw.document())
        cursor.setPosition(self._offset_of(ref))
        self.tw.setTextCursor(cursor)
        self.tw.ensureCursorVisible()

    def set_scroll_position(self, h_pct, v_pct):
        hbar = self.tw.horizontalScrollBar()
        vbar = self.tw.verticalScrollBar()
        if hbar.maximum() > 0:
            hbar.setValue(int(max(0.0, min(1.0, h_pct)) * hbar.maximum()))
        if vbar.maximum() > 0:
            vbar.setValue(int(max(0.0, min(1.0, v_pct)) * vbar.maximum()))

    def set_scroll_pos(self, pos):
        vsb = self.tw.verticalScrollBar()
        if pos == -1:
            vsb.setValue(vsb.maximum())
        else:
            vsb.setValue(pos)

    def set_font(self, qfont):
        self.tw.setFont(qfont)
        self.nb.setFont(qfont)
        self._apply_all_formats()

    def color_line(self, line_num, fgcolor=None, bgcolor=None):
        return self.tw.color_line(line_num, fgcolor=fgcolor, bgcolor=bgcolor)

    def set_syntax_highlighter_class(self, klass):
        return self.tw.set_syntax_highlighter_class(klass)

    def get_syntax_highlighter(self):
        return self.tw.get_syntax_highlighter()

    def set_tooltip_callback(self, func, *args):
        self.tw.set_tooltip_callback(func, *args)

    def get_modified(self):
        return self.tw.document().isModified()

    def get_end_lineno(self):
        return max(0, self.tw.document().blockCount() - 1)

    def scroll_to_lineno(self, lineno):
        cursor = QTextCursor(self.tw.document())
        block = self.tw.document().findBlockByLineNumber(max(0, lineno))
        if block.isValid():
            cursor.setPosition(block.position())
        else:
            cursor.movePosition(QTextCursor.End)
        self.tw.setTextCursor(cursor)
        self.tw.ensureCursorVisible()

    def scroll_to_end(self):
        cursor = self.tw.textCursor()
        cursor.movePosition(QTextCursor.End)
        self.tw.setTextCursor(cursor)
        self.tw.ensureCursorVisible()

    def _clamp_offset(self, offset):
        try:
            offset = int(offset)
        except Exception:
            offset = 0
        return max(0, min(len(self._text), offset))

    def _offset_of(self, ref):
        if not isinstance(ref, TextBufferRef):
            raise TypeError("API requires a TextBufferRef")
        if ref._buffer is not self:
            raise ValueError("TextBufferRef belongs to a different buffer")
        if not ref.is_valid():
            raise ValueError("TextBufferRef has been invalidated")
        return self._clamp_offset(ref._offset)

    def _line_of_offset(self, offset):
        return self._text[:self._clamp_offset(offset)].count('\n')

    def _offset_of_line_start(self, lineno):
        if lineno <= 0:
            return 0
        offset = 0
        for _idx in range(lineno):
            nl = self._text.find('\n', offset)
            if nl < 0:
                return len(self._text)
            offset = nl + 1
        return offset

    def _replace_range(self, start, end, new_text, tags=None, selection_after=None,
                       sync_editor=True, push_undo=True):
        """Replace ``[start, end)`` in the model and synchronize the view.

        All ref and tag shifting happens here so every edit path shares the
        same semantics.  ``sync_editor`` is disabled only when the edit
        originated from ``QTextEdit`` and the widget already reflects the new
        text.  ``push_undo`` is disabled when the edit is itself the result
        of an undo/redo replay.
        """
        old_text = self._text[start:end]
        if old_text == new_text:
            if selection_after is not None:
                self._cursor, self._sel_start, self._sel_end = selection_after
            return

        cursor_before = (self._cursor, self._sel_start, self._sel_end)

        self._text = self._text[:start] + new_text + self._text[end:]
        if end > start:
            self._update_refs_on_delete(start, end)
            self._update_tags_on_delete(start, end)
        if new_text:
            self._update_refs_on_insert(start, len(new_text))
            self._update_tags_on_insert(start, len(new_text))
        if tags:
            for name in tags:
                self._add_tag_interval(name, start, start + len(new_text))
        if selection_after is None:
            new_pos = start + len(new_text)
            self._cursor = new_pos
            self._sel_start = new_pos
            self._sel_end = new_pos
        else:
            self._cursor, self._sel_start, self._sel_end = selection_after

        if not self._in_undo_redo and push_undo:
            self._undo_stack.append((start, old_text, new_text, cursor_before,
                                     (self._cursor, self._sel_start, self._sel_end)))
            if len(self._undo_stack) > self._undo_limit:
                self._undo_stack.pop(0)
            self._redo_stack = []

        if sync_editor:
            # Edit only the changed span in the editor (not the whole
            # document), preserving existing formatting outside it.
            self._replace_editor_range(start, end, new_text)
            self._apply_selection_to_editor()
        # Only the inserted span needs (re)formatting: on an incremental
        # edit Qt keeps the formatting of the surrounding text, which has
        # merely shifted.  This keeps appends O(edit) rather than O(buffer).
        self._apply_all_formats(region=(start, start + len(new_text)))
        self._refresh_icon_gutter()

        self.make_callback('changed')

    def can_undo(self):
        return len(self._undo_stack) > 0

    def can_redo(self):
        return len(self._redo_stack) > 0

    def undo(self):
        if not self._undo_stack:
            return False
        start, old_text, new_text, cursor_before, cursor_after = \
            self._undo_stack.pop()
        self._in_undo_redo = True
        try:
            self._replace_range(start, start + len(new_text), old_text,
                                push_undo=False)
            self._cursor, self._sel_start, self._sel_end = cursor_before
            self._apply_selection_to_editor()
        finally:
            self._in_undo_redo = False
        self._redo_stack.append((start, old_text, new_text, cursor_before,
                                 cursor_after))
        return True

    def redo(self):
        if not self._redo_stack:
            return False
        start, old_text, new_text, cursor_before, cursor_after = \
            self._redo_stack.pop()
        self._in_undo_redo = True
        try:
            self._replace_range(start, start + len(old_text), new_text,
                                push_undo=False)
            self._cursor, self._sel_start, self._sel_end = cursor_after
            self._apply_selection_to_editor()
        finally:
            self._in_undo_redo = False
        self._undo_stack.append((start, old_text, new_text, cursor_before,
                                 cursor_after))
        return True

    def _invalidate_all_refs(self):
        for ref in list(self._refs):
            ref._offset = 0
            ref._invalidate()

    def _update_refs_on_insert(self, offset, amount):
        for ref in list(self._refs):
            if not ref.is_valid():
                continue
            if ref._offset > offset or (
                    ref._offset == offset and ref.get_gravity() == 'right'):
                ref._offset += amount

    def _update_refs_on_delete(self, start, end):
        amount = end - start
        for ref in list(self._refs):
            if not ref.is_valid():
                continue
            if ref._offset <= start:
                continue
            if ref._offset >= end:
                ref._offset -= amount
            else:
                ref._offset = start

    def _add_tag_interval(self, name, start, end):
        self._tag_seq += 1
        self._tags.append(dict(name=name, start=start, end=end, seq=self._tag_seq))

    def _update_tags_on_insert(self, offset, amount):
        for tag in self._tags:
            if tag['start'] >= offset:
                tag['start'] += amount
            if tag['end'] > offset or (
                    tag['end'] == offset and tag['start'] == tag['end']):
                tag['end'] += amount
            if tag['end'] < tag['start']:
                tag['end'] = tag['start']

    def _update_tags_on_delete(self, start, end):
        amount = end - start
        next_tags = []
        for tag in self._tags:
            tag_start = tag['start']
            tag_end = tag['end']
            if tag_end <= start:
                next_tags.append(tag)
                continue
            if tag_start >= end:
                next_tags.append(dict(tag, start=tag_start - amount,
                                      end=tag_end - amount))
                continue
            new_start = tag_start if tag_start < start else start
            new_end = tag_end - amount if tag_end > end else start
            if new_end > new_start:
                next_tags.append(dict(tag, start=new_start, end=new_end))
        self._tags = next_tags

    def _segments_for_range(self, start, end):
        """Split a range into maximal subranges sharing the same tag stack."""
        points = {start, end}
        active = []
        for tag in self._tags:
            if tag['end'] <= start or tag['start'] >= end:
                continue
            active.append(tag)
            points.add(max(tag['start'], start))
            points.add(min(tag['end'], end))
        sorted_points = sorted(points)
        segments = []
        for idx in range(len(sorted_points) - 1):
            seg_start = sorted_points[idx]
            seg_end = sorted_points[idx + 1]
            if seg_start >= seg_end:
                continue
            in_seg = [tag for tag in active
                      if tag['start'] <= seg_start and tag['end'] >= seg_end]
            in_seg.sort(key=lambda item: item['seq'])
            segments.append((seg_start, seg_end, [tag['name'] for tag in in_seg]))
        return segments

    def _merged_format(self, tag_names):
        attrs = {}
        for name in tag_names:
            attrs.update(self._tag_defs.get(name, {}))
        return mkformat(fgcolor=attrs.get('foreground'),
                        bgcolor=attrs.get('background'),
                        style=self._style_list_from_attrs(attrs))

    def _style_list_from_attrs(self, attrs):
        style = []
        if attrs.get('bold'):
            style.append('bold')
        if attrs.get('italic'):
            style.append('italic')
        return style

    def _apply_all_formats(self, region=None):
        """Rebuild character formatting from the tag interval model.

        Qt stores formatting on the document itself, so before reapplying tag
        styles we first reset the affected range back to the base widget
        palette and font.  This keeps stale formatting from surviving after
        tags move or are removed.

        ``region`` is an ``(start, end)`` offset pair limiting the work to a
        subrange; when ``None`` the entire document is reformatted.  Callers
        that only changed a bounded span pass that span so streaming edits
        stay O(edit) instead of O(buffer).
        """
        if self._applying_formats:
            return
        self._applying_formats = True
        try:
            if region is None:
                r_start, r_end = 0, len(self._text)
            else:
                r_start = max(0, min(region[0], region[1]))
                r_end = min(len(self._text), max(region[0], region[1]))
            self._reset_document_format(r_start, r_end)
            for seg_start, seg_end, tag_names in self._segments_for_range(r_start, r_end):
                if not tag_names:
                    continue
                # Formatting is applied with a QTextCursor selection because
                # QTextEdit/QTextDocument do not provide a simpler range-style
                # API for plain-text documents.
                cursor = QTextCursor(self.tw.document())
                cursor.setPosition(seg_start)
                cursor.setPosition(seg_end, QTextCursor.KeepAnchor)
                cursor.setCharFormat(self._merged_format(tag_names))
        finally:
            self._applying_formats = False

    def _reset_document_format(self, start=None, end=None):
        """Restore a range (default: whole document) to the base text format."""
        cursor = QTextCursor(self.tw.document())
        if start is None:
            cursor.select(QTextCursor.Document)
        else:
            cursor.setPosition(start)
            cursor.setPosition(end, QTextCursor.KeepAnchor)
        fmt = QTextCharFormat()
        fmt.setFont(self.tw.font())
        fmt.setForeground(self.tw.palette().text())
        fmt.setBackground(self.tw.palette().base())
        cursor.setCharFormat(fmt)

    def _replace_editor_range(self, start, end, new_text):
        """Replace ``[start, end)`` in the QTextEdit with ``new_text``.

        Uses a QTextCursor so only the changed span is touched (unlike
        setPlainText, which rewrites the whole document and drops all
        existing character formatting).
        """
        self._syncing = True
        try:
            cursor = QTextCursor(self.tw.document())
            cursor.setPosition(start)
            if end > start:
                cursor.setPosition(end, QTextCursor.KeepAnchor)
            cursor.insertText(new_text)
        finally:
            self._syncing = False

    def _set_editor_text(self, text):
        """Push model text into ``QTextEdit`` without reentering sync hooks."""
        self._syncing = True
        try:
            self.tw.setPlainText(text)
        finally:
            self._syncing = False

    def _apply_selection_to_editor(self):
        """Mirror model selection state into the QTextEdit cursor.

        ``QTextEdit`` represents selection entirely through ``QTextCursor``, so
        this method reconstructs the selection each time the model moves the
        caret or selection endpoints.
        """
        cursor = QTextCursor(self.tw.document())
        cursor.setPosition(self._clamp_offset(self._sel_start))
        cursor.setPosition(self._clamp_offset(self._sel_end),
                           QTextCursor.KeepAnchor)
        self._syncing = True
        try:
            self.tw.setTextCursor(cursor)
        finally:
            self._syncing = False

    def _refresh_icon_gutter(self):
        """Recompute visible gutter icons from ref-anchored registrations."""
        self.nb.clear_icons()
        if not self._show_icon_gutter:
            return
        line_icons = {}
        for ref, image in list(self._icon_refs.items()):
            if not ref.is_valid():
                self._icon_refs.pop(ref, None)
                continue
            line_icons[ref.get_line() + 1] = image
        for line, image in line_icons.items():
            self.nb.set_icon_for_line(line, image)

    def _on_editor_text_changed(self):
        """Pull user edits from QTextEdit back into the buffer model.

        Qt edits the document directly during typing, paste, and deletion.  We
        diff the previous model text against the new widget text, then replay
        that edit through ``_replace_range`` so refs and tag intervals are
        updated with the same logic used by programmatic edits.
        """
        # Applying character formats (setCharFormat) also emits textChanged,
        # but never changes the text.  Ignore those, otherwise every format
        # pass triggers a full-document toPlainText() diff -- an O(n^2) storm
        # while streaming appends.
        if self._syncing or self._applying_formats:
            return
        new_text = self.tw.toPlainText()
        if new_text == self._text:
            return
        start = 0
        old_text = self._text
        old_len = len(old_text)
        new_len = len(new_text)
        while start < old_len and start < new_len and old_text[start] == new_text[start]:
            start += 1
        old_end = old_len
        new_end = new_len
        while old_end > start and new_end > start and old_text[old_end - 1] == new_text[new_end - 1]:
            old_end -= 1
            new_end -= 1
        cursor = self.tw.textCursor()
        selection_after = (cursor.position(), cursor.anchor(), cursor.position())
        self._replace_range(start, old_end, new_text[start:new_end],
                            selection_after=selection_after,
                            sync_editor=False)

    def _on_cursor_position_changed(self):
        """Capture cursor and selection state after user interaction."""
        if self._syncing:
            return
        cursor = self.tw.textCursor()
        self._cursor = cursor.position()
        self._sel_start = cursor.anchor()
        self._sel_end = cursor.position()
        self._refresh_icon_gutter()
        self.make_callback('cursor-moved')

    def _find_offset(self, query, start=None, case_insensitive=False):
        if not query:
            return None
        offset = 0 if start is None else self._offset_of(start)
        haystack = self._text
        needle = query
        if case_insensitive:
            haystack = haystack.lower()
            needle = needle.lower()
        idx = haystack.find(needle, offset)
        if idx < 0:
            return None
        return (idx, idx + len(query))

    def _find_all_offsets(self, query, start=None, case_insensitive=False):
        if not query:
            return []
        offsets = []
        offset = 0 if start is None else self._offset_of(start)
        haystack = self._text
        needle = query
        if case_insensitive:
            haystack = haystack.lower()
            needle = needle.lower()
        while True:
            idx = haystack.find(needle, offset)
            if idx < 0:
                break
            offsets.append((idx, idx + len(query)))
            offset = idx + max(1, len(query))
        return offsets


class TextSource(Widgets.WidgetBase):
    """Ginga widget wrapper exposing the numbered Qt text editor."""

    def __init__(self, wrap=False, editable=False):
        super().__init__()

        self.widget = QTextSource()
        tw = self.widget.get_internal_text_widget()
        tw.setReadOnly(not editable)
        self.widget.set_wrap(wrap)
        self.tw = tw

        for name in ['tooltip', 'changed', 'cursor_moved', 'key-press',
                     'line-clicked']:
            self.enable_callback(name)

        # Relay the inner widget's callbacks out through this wrapper.  The
        # inner widget calls these with itself as the first argument.
        self.widget.add_callback('changed',
                                 lambda w: self.make_callback('changed'))
        self.widget.add_callback('cursor-moved',
                                 lambda w: self.make_callback('cursor_moved'))
        self.widget.add_callback('key-press', self._key_pressed)
        self.widget.add_callback(
            'line-clicked',
            lambda w, lineno: self.make_callback('line-clicked', lineno))

        # Default to a fixed-width font.  Code, tabular, and log content all
        # rely on monospaced alignment.  DejaVu Sans Mono matches the font
        # the GTK version used (via the system default monospace).
        self.set_font('DejaVu Sans Mono', 10)

    def _key_pressed(self, w, event):
        # Point the event at this (ginga) widget and relay it.  The return
        # value propagates back to QTextSource.eventFilter: truthy means a
        # page handler consumed the key.
        event.viewer = self
        return self.make_callback('key-press', event)

    def append_text(self, text, autoscroll=True, tags=None):
        end = self.widget.get_ref_end()
        self.widget.insert_text(end, text, tags=tags)
        self.widget.remove_ref(end)
        if autoscroll:
            self.widget.scroll_to_end()

    def get_text(self):
        return self.widget.get_text()

    def get_text_range(self, start_ref, end_ref):
        return self.widget.get_text_range(start_ref, end_ref)

    def can_undo(self):
        return self.widget.can_undo()

    def can_redo(self):
        return self.widget.can_redo()

    def undo(self):
        return self.widget.undo()

    def redo(self):
        return self.widget.redo()

    def clear(self):
        self.widget.clear()

    def set_text(self, text):
        self.widget.set_text(text)

    def set_editable(self, tf):
        self.widget.set_editable(tf)

    def set_limit(self, numlines):
        pass

    def set_font(self, font, size=10):
        if not isinstance(font, QFont):
            font = self.get_font(font, size)
        self.widget.set_font(font)

    def set_wrap(self, kind):
        self.widget.set_wrap(kind)

    def set_scroll_pos(self, pos):
        self.widget.set_scroll_pos(pos)

    def show_line_numbers(self, tf):
        return self.widget.show_line_numbers(tf)

    def enable_line_icons(self, tf):
        self.widget.set_icon_gutter(tf)

    def enable_tooltips(self, tf):
        self.tw.set_tooltip_callback(self._tt_cb if tf else None)

    def _tt_cb(self, event):
        cur = self.tw.cursorForPosition(event.pos())
        pos_in_line = cur.positionInBlock()
        block = cur.block()
        line_no = block.firstLineNumber()
        text = block.text()
        res = []
        self.make_callback('tooltip', res, line_no, pos_in_line, text)
        if len(res) > 0:
            QToolTip.showText(event.globalPos(), res[0])
        return True

    def set_syntax_highlighter_class(self, klass):
        return self.widget.set_syntax_highlighter_class(klass)

    def get_syntax_highlighter(self):
        return self.widget.get_syntax_highlighter()

    def get_modified(self):
        return self.widget.get_modified()

    def get_end_lineno(self):
        return self.widget.get_end_lineno()

    def scroll_to_lineno(self, lineno):
        return self.widget.scroll_to_lineno(lineno)

    def scroll_to_end(self):
        return self.widget.scroll_to_end()

    def get_length(self):
        return self.widget.get_length()

    def create_ref(self, offset, gravity='right'):
        return self.widget.create_ref(offset, gravity=gravity)

    def remove_ref(self, ref):
        return self.widget.remove_ref(ref)

    def create_named_ref(self, name, offset, gravity='right'):
        return self.widget.create_named_ref(name, offset, gravity=gravity)

    def get_named_ref(self, name):
        return self.widget.get_named_ref(name)

    def remove_named_ref(self, name):
        return self.widget.remove_named_ref(name)

    def get_ref_start(self):
        return self.widget.get_ref_start()

    def get_ref_end(self):
        return self.widget.get_ref_end()

    def get_ref_bounds(self):
        return self.widget.get_ref_bounds()

    def get_ref_line_start(self, lineno):
        return self.widget.get_ref_line_start(lineno)

    def get_ref_line_end(self, lineno):
        return self.widget.get_ref_line_end(lineno)

    def insert_text(self, ref, text, tags=None):
        return self.widget.insert_text(ref, text, tags=tags)

    def delete_range(self, start_ref, end_ref):
        return self.widget.delete_range(start_ref, end_ref)

    def create_tag(self, name, attrs=None, **kwdargs):
        return self.widget.create_tag(name, attrs=attrs, **kwdargs)

    def remove_tag_def(self, name):
        return self.widget.remove_tag_def(name)

    def has_tag(self, name):
        return self.widget.has_tag(name)

    def apply_tag(self, name, start_ref, end_ref):
        return self.widget.apply_tag(name, start_ref, end_ref)

    def remove_tag(self, name, start_ref, end_ref):
        return self.widget.remove_tag(name, start_ref, end_ref)

    def get_tags_at(self, ref):
        return self.widget.get_tags_at(ref)

    def get_tags_range(self, start_ref, end_ref):
        return self.widget.get_tags_range(start_ref, end_ref)

    def get_tag_region(self, name):
        return self.widget.get_tag_region(name)

    def get_tag_regions(self, name):
        return self.widget.get_tag_regions(name)

    def get_cursor(self):
        return self.widget.get_cursor()

    def set_cursor(self, ref):
        return self.widget.set_cursor(ref)

    def has_selection(self):
        return self.widget.has_selection()

    def get_selection_range(self):
        return self.widget.get_selection_range()

    def get_selection_bounds(self):
        return self.widget.get_selection_bounds()

    def set_selection_range(self, start_ref, end_ref):
        return self.widget.set_selection_range(start_ref, end_ref)

    def find(self, query, start=None, case_insensitive=False):
        return self.widget.find(query, start=start,
                                case_insensitive=case_insensitive)

    def find_all(self, query, start=None, case_insensitive=False):
        return self.widget.find_all(query, start=start,
                                    case_insensitive=case_insensitive)

    def replace(self, query, replacement, all=False, start=None,
                case_insensitive=False):
        return self.widget.replace(query, replacement, all=all, start=start,
                                   case_insensitive=case_insensitive)

    def set_icon(self, ref, image):
        return self.widget.set_icon(ref, image)

    def set_icon_gutter(self, tf, pad_px=24):
        return self.widget.set_icon_gutter(tf, pad_px=pad_px)

    def clear_icons(self):
        return self.widget.clear_icons()

    def scroll_to_ref(self, ref):
        return self.widget.scroll_to_ref(ref)


def _resolve_qt_enum(enum_name, attr):
    """Resolve a scoped Qt enum member across PyQt5/6 and PySide2/6.

    In Qt6 members live under a nested enum (e.g. ``Qt.Key.Key_Up``); in
    Qt5 they are attributes of ``Qt`` directly.
    """
    enum = getattr(QtCore.Qt, enum_name, None)
    if enum is not None and hasattr(enum, attr):
        return getattr(enum, attr)
    return getattr(QtCore.Qt, attr, None)


def _resolve_qt_key(attr):
    return _resolve_qt_enum('Key', attr)


def _enum_int(val):
    """Return the integer value of a Qt enum/flags member.

    PyQt6 scoped enums/flags are not always directly ``int()``-convertible,
    but expose a ``.value``; PyQt5/PySide return plain ints.
    """
    try:
        return int(val)
    except (TypeError, ValueError):
        return int(val.value)


# Map Qt key codes to ginga-style (lowercase) key names for keys page code
# cares about.  Printable keys fall through to the event's text().
_KEY_NAMES = {}
for _attr, _name in [
        ('Key_Up', 'up'), ('Key_Down', 'down'),
        ('Key_Left', 'left'), ('Key_Right', 'right'),
        ('Key_Shift', 'shift_l'), ('Key_Control', 'control_l'),
        ('Key_Alt', 'alt_l'), ('Key_Meta', 'meta_l'),
        ('Key_Return', 'return'), ('Key_Enter', 'return'),
        ('Key_Escape', 'escape'), ('Key_Tab', 'tab'),
        ('Key_Backspace', 'backspace'), ('Key_Delete', 'delete'),
        ('Key_Home', 'home'), ('Key_End', 'end'),
        ('Key_PageUp', 'page_up'), ('Key_PageDown', 'page_down'),
        ('Key_Space', 'space')]:
    _code = _resolve_qt_key(_attr)
    if _code is not None:
        _KEY_NAMES[_enum_int(_code)] = _name
del _attr, _name, _code

# Qt keyboard-modifier flags -> ginga modifier names (matches Bindings.py).
_MODIFIERS = []
for _attr, _name in [('ControlModifier', 'ctrl'), ('ShiftModifier', 'shift'),
                     ('AltModifier', 'alt'), ('MetaModifier', 'win')]:
    _flag = _resolve_qt_enum('KeyboardModifier', _attr)
    if _flag is not None:
        _MODIFIERS.append((_enum_int(_flag), _name))
del _attr, _name, _flag


def _make_key_event(qt_event, viewer=None):
    """Build a ginga ``KeyEvent`` from a Qt key event, or return None.

    Key names follow ginga's lowercase convention and modifiers are reported
    as a set (``ctrl``/``shift``/``alt``/``win``), so page handlers can read
    ``event.key`` and ``event.modifiers`` the same way ginga viewers do.
    """
    key = _enum_int(qt_event.key())
    mods = _enum_int(qt_event.modifiers())
    modset = set(name for flag, name in _MODIFIERS if mods & flag)

    name = _KEY_NAMES.get(key)
    if name is None:
        if modset & {'ctrl', 'alt', 'win'}:
            # text() is a control character under these modifiers, so derive
            # the base key from the key code instead.
            name = chr(key).lower() if 0x20 <= key <= 0x7e else None
        else:
            text = qt_event.text()
            name = text.lower() if text and text.isprintable() else None
    if name is None:
        return None
    return KeyEvent(key=name, state='down', modifiers=frozenset(modset),
                    viewer=viewer)


def mkformat(fgcolor=None, bgcolor=None, style=None, baseformat=None):
    """Return a QTextCharFormat with the given attributes."""
    style = [] if style is None else list(style)
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
