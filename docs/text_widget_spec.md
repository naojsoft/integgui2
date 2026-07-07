# Canonical text-widget spec

The application's colored/tagged text buffers (the GtkSourceView replacement)
are provided by two implementations that MUST expose the same API and
semantics:

- **Qt / Ginga**: `TextSource` (Ginga wrapper) + `QTextSource` (inner Qt
  widget) in `integgui2/view/Widgets.py`
- **pg / browser**: `TextSource` in
  `~/Git/pgwidgets/pgwidgets_js/static/modules/TextSource.js` (pgwidgets-js).
  The names now match across backends (`TextSource`).

This document is the contract. Page-level code must depend only on the methods
below, never on backend-native APIs (no GTK iters/marks/tag-tables, no direct
`QTextEdit`, no DOM).

## Data model (both backends)

- A plain-text string is the source of truth; the native editor is a rendered
  view synced from it.
- **`TextBufferRef`** — a live character-offset reference with `left`/`right`
  gravity that follows inserts/deletes. Replaces GTK iters *and* marks.
- **Tag intervals** — `{name, start, end, seq}` records applied over ranges,
  rendered into character formatting. Replaces the GTK tag table.
- **Ref-anchored gutter icons** — replace GTK source marks.

## API surface

Legend: ✅ implemented · ⚠️ diverges / verify · ❌ missing

| Group | Method | Qt | JS |
|---|---|---|---|
| Content | `get_text` / `get_length` / `set_text` / `clear` | ✅ | ✅ |
| | `get_text_range(start_ref, end_ref)` | ✅ | ✅ |
| | `insert_text(ref, text, tags=None)` | ✅ | ✅ |
| | `delete_range(start_ref, end_ref)` | ✅ | ✅ |
| | `append_text(text, autoscroll, tags)` | ✅ | ⚠️ verify |
| Refs | `create_ref` / `remove_ref` | ✅ | ✅ (diff GC) |
| | `create_named_ref` / `get_named_ref` / `remove_named_ref` | ✅ | ✅ |
| | `get_ref_start/end/bounds`, `get_ref_line_start/end` | ✅ | ⚠️ verify |
| Cursor/sel | `get_cursor` / `set_cursor` | ✅ | ✅ |
| | `get_selection_range` / `set_selection_range` | ✅ | ✅ |
| | `has_selection()` | ✅ | ✅ |
| | `get_selection_bounds()` → ref pair or `None` | ✅ | ✅ |
| Tags | `create_tag`/`remove_tag_def`/`has_tag`/`apply_tag`/`remove_tag` | ✅ | ✅ |
| | `get_tags_at` / `get_tags_range` | ✅ | ✅ |
| | `get_tag_region(name)` / `get_tag_regions(name)` | ✅ | ✅ |
| Undo | `can_undo` / `can_redo` / `undo` / `redo` | ✅ | ✅ |
| Find | `find` / `find_all` / `replace` | ✅ | ✅ |
| Display | `set_editable`/`set_wrap`/`set_line_numbers`/`set_icon_gutter` | ✅ | ✅ |
| | `set_icon(ref, image)` / `clear_icons` / `set_font` | ✅ | ⚠️ `set_font` |
| Scroll | `scroll_to_ref`/`scroll_to_lineno`/`scroll_to_end`/`set_scroll_pos` | ✅ | ⚠️ partial |
| Callbacks | `changed`, `cursor_moved`, `key-press`, `line-clicked` | ✅ | ⚠️ changed/cursor |
| | `tooltip` (Qt), `icon_clicked` | ⚠️ tooltip only | ⚠️ no tooltip |

## Semantics fixed by decision

- **`get_selection_bounds()`** returns `(start_ref, end_ref)` or `None` when
  there is no selection (guard with `has_selection()`). It does NOT raise.
- **Undo/redo is modeled at the widget level**, not delegated to the native
  editor. Each `_replace_range` edit records `(start, old_text, new_text,
  cursor_before, cursor_after)`; undo replays the inverse with refs and tag
  intervals kept consistent. Qt's native `QTextEdit` undo is disabled so the
  two do not double-fire. `set_text` clears the undo history.
- **`delete_range(start_ref, end_ref)`** is the canonical deletion method.
  There is no `delete_region`.
- **`get_tag_region(name)`** returns the overall span (first start → last end)
  of a tag — the replacement for the old GTK `common.get_region`.
  `get_tag_regions(name)` returns one ref pair per maximal contiguous run.

## Syntax highlighting is done through tags (portable)

OPE syntax highlighting is applied through the **tag table**, not a
backend-native highlighter.  `OpePage.color()` drives it from the OPE parser
(`oscript.parse.ope.check_ope`): `taglist` gives line-level comment tags,
`reflist` gives per-`$VAR` character ranges for `varref` (plus `badref` where
undefined).  These are the same `common.decorative_tags` applied with the same
`apply_tag` mechanism used for execution marking, so syntax colors and command
status **compose** (foreground vs background) instead of fighting a separate
layer.  This works identically on both backends.

Tag color names must be resolvable by `ginga.colors` — use spaceless names
(`darkgreen`, not `dark green`).  The old Qt `QSyntaxHighlighter`
(`syntax/ope_syntax.py`) and the widget-level `set_syntax_highlighter_class` /
`get_syntax_highlighter` methods are no longer used by any page (kept only as
dead/optional Qt-specific API; `ope_syntax.py` can be deleted).

## Not portable (backend-specific, optional)

- **Ref lifetime.** Qt uses a `WeakSet` + explicit `remove_ref`; JS uses a
  `FinalizationRegistry`. The contract is behavioral: `remove_ref` always
  works and unreferenced refs eventually free.

## Outstanding (tracked, not yet done)

- JS side: verify `append_text`, `get_ref_*`, `set_font`, scroll methods reach
  Qt parity. (`has_selection`, `get_selection_bounds`, `get_tag_region(s)` are
  now done.)
- Qt side: `line_clicked` / `icon_clicked` gutter callbacks.
- Page porting (Prong B): **B1 `common.py` shims — DONE**
  (`get_region`/`get_region_lines`/`clear_tags`/`clear_tags_region`/
  `clear_selection`/`select_all`/`remove_all_marks`/`scroll_to_lineno`/
  `get_end_lineno`, all on the TextSource widget API).
  **B2 `CodePage.find`/`_find` — DONE** (find/replace now use the widget's
  `find_all`/`delete_range`/`set_selection_range` + a tracked `_search_offset`;
  reverse search and wrap-around are driven from `find_all`; case sensitivity
  now maps correctly from the dialog checkbox).
  **B3 `OpePage` + `OpeCommandObject` — DONE** (all `self.buf`/GTK iter/mark
  calls ported to `self.tw` refs + tags; command regions tagged by `guitag`;
  `mark_status` re-tags queued/executing/done/error; executing/error source
  marks became gutter icons anchored by named refs — `_set_exec_mark` /
  `_clear_exec_marks`, icons `apple-green.png`/`apple-red.png`; `current()`
  finds the mark via named refs; save/restore-selection reimplemented on refs).
  **B4 `DDCommandPage` + `QueuePage` — DONE** (both switched to `TextSource`,
  dropped `tw.tw.get_buffer()`; DDCommandPage's raw-GTK `attach_queue` ported to
  ginga widgets; QueuePage's redraw/selection/cursor/paste/move/insbreak ported
  to refs+tags, cursor-line highlight via the `cursor_moved` callback).
  The inner `QTextSource` is now a `Callback.Callbacks` subclass firing
  `changed` / `cursor-moved` / `key-press`; the wrapper relays them as
  `changed` / `cursor_moved` / `key-press`. **Keystroke callbacks now work on
  our `TextSource`** (via an event filter + `_key_name` Qt→ginga keymap), which
  unblocked QueuePage's single-key shortcuts.

  Remaining keystroke gap: `OpePage.keypress` uses **Ctrl-modified** shortcuts;
  the `key-press` callback currently passes only a keyname (no modifiers), so
  those stay deferred until the key event also reports modifiers. Ginga's own
  base TextAreas still have no keystroke callback (only our TextSource does).

  **`TagPage` — DONE** (was needed by `OpePage.color()`): ported off `self.buf`
  and the GTK `button-press-event`; `add_mapping` uses `append_text(tags=...)` +
  `get_end_lineno`; click-to-jump now uses a new **`line-clicked`** widget
  callback (Qt: mouse-press in the viewport → `cursorForPosition().blockNumber()`
  → `make_callback('line-clicked', lineno)`). `build_toplevel` now enables
  `add_queue` + `add_tagpage` (both pages ported).

  **B6 startup — VERIFIED (headless, offscreen Qt, no Gen2 stack):**
  `IntegView` constructs, `build_toplevel` builds the desktop/workspaces/pages,
  and `load_ope()` loads + colors an OPE file through the tag table
  (varref/comment/badref tags applied), populates the Tags page, and
  click-to-jump works. Full `main()` still needs the real Gen2 environment
  (remote objects / monitor / controller) — run there.

  Remaining GTK pages: `DirectoryPage`, `SkMonitorPage`, `Confirmation` dialog
  in `dialogs.py`. `text_widget_extensions.py` is an orphan (nothing imports
  it) — ignore. Keystroke shortcuts with modifiers (OpePage/QueuePage Ctrl+key)
  still need the `key-press` callback to also report modifiers.
