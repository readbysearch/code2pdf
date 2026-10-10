"""
Progress reporting for code2pdf.

The total page count is only known after layout, so it is estimated up front from line
counts and line lengths (see estimate_pages) and raised if layout runs past it.

In a terminal the status is one line updated in place; otherwise (logs, pipes) a line is
printed every 10%.
"""

import math
import time

# Matches the page CSS in theme.py: A4, 20/18 mm vertical margins, 8.5pt/1.45 code text,
# 17 mm side margins and the line-number gutter.
ROWS_PER_PAGE = 59
TITLE_ROWS = 5          # folder, file name and details above the first line of code
COLUMNS = 89            # code characters per row before a line wraps
CONTENTS_ENTRIES_PER_PAGE = 32


def estimate_pages(sources, contents=False):
    """Estimated page count for a document with one section per source text."""
    pages = 0
    for source in sources:
        rows = sum(max(1, math.ceil(len(line.expandtabs(4)) / COLUMNS)) for line in source.splitlines()) or 1
        pages += 1 + math.ceil(max(0, rows - (ROWS_PER_PAGE - TITLE_ROWS)) / ROWS_PER_PAGE)
    if contents:
        pages += max(1, math.ceil(len(sources) / CONTENTS_ENTRIES_PER_PAGE))
    return pages


def _clock(seconds):
    seconds = int(round(seconds))
    return f"{seconds // 60}:{seconds % 60:02d}"


class Progress:
    """Three stages: [1/3] preparing (parse HTML/CSS), [2/3] laying out pages, [3/3] writing the PDF.

    WeasyPrint only reports individual pages during layout, so in a terminal a background
    ticker keeps the elapsed time moving during the other two stages."""

    BAR_WIDTH = 20
    MIN_INTERVAL = 0.1   # seconds between terminal redraws during layout
    WRITE_RATIO = 0.5    # writing takes roughly this fraction of the layout time (measured 0.3-0.7)

    def __init__(self, stream, files, lines, estimated_pages, quiet=False, tick=0.5):
        import threading
        self.stream = stream
        self.quiet = quiet
        self.tty = hasattr(stream, "isatty") and stream.isatty()
        self.estimate = max(1, estimated_pages)
        self.started = time.monotonic()
        self.layout_started = None
        self.layout_seconds = None
        self.write_started = None
        self.stage = None
        self.parts_total = 0      # > 0 when rendering in parts (see parts.py)
        self.parts_done = 0
        self.last_page = 0
        self.last_draw = 0.0
        self.last_bucket = 0
        self.lock = threading.Lock()
        self.stopped = threading.Event()
        self._write(f"code2pdf: {files:,} file{'s' if files != 1 else ''}, {lines:,} line{'s' if lines != 1 else ''} "
                    f"(~{self.estimate:,} pages)\n")
        if self.tty and tick and not quiet:
            threading.Thread(target=self._tick, args=(tick,), daemon=True).start()

    def _write(self, text):
        if not self.quiet:
            self.stream.write(text)
            self.stream.flush()

    def _status(self, text):
        if self.tty:
            self._write("\r  " + text + "\x1b[K")
        else:
            self._write("  " + text + "\n")

    def _tick(self, interval):
        while not self.stopped.wait(interval):
            with self.lock:
                if self.stage in ("preparing", "writing", "assembling"):
                    self._draw_silent_stage()

    def _draw_silent_stage(self):
        now = time.monotonic()
        if self.stage == "preparing":
            self._status(f"[1/3] Preparing layout…  {_clock(now - self.started)} elapsed")
        elif self.stage == "assembling":
            self._status(f"[3/3] Joining {self.parts_total} parts…  {_clock(now - self.started)} elapsed")
        else:
            text = f"[3/3] Writing PDF…  {_clock(now - self.started)} elapsed"
            if self.layout_seconds is not None:
                left = self.WRITE_RATIO * self.layout_seconds - (now - self.write_started)
                text += f", ~{_clock(max(0.0, left))} left"
            self._status(text)

    def preparing(self):
        with self.lock:
            self.stage = "preparing"
            self._draw_silent_stage()

    def parts(self, total, jobs):
        """Switch to parts mode: pages are counted across all parts."""
        with self.lock:
            self.parts_total = total
            self.WRITE_RATIO = 0.1  # per-part writing is included in the page rate; joining is quick
            self._write(f"  in {total} parts of ~{max(1, round(self.estimate / total))} pages, {jobs} at a time\n")

    def part_done(self, pages_so_far):
        with self.lock:
            self.parts_done += 1
            self.last_draw = 0.0
        self.page(pages_so_far, force=True)

    def assembling(self):
        with self.lock:
            self.stage = "assembling"
            self._draw_silent_stage()

    def page(self, number, force=False):
        with self.lock:
            if number < self.last_page or (number == self.last_page and not force):  # repagination revisits pages
                return
            now = time.monotonic()
            if self.layout_started is None:
                self.layout_started = now
            self.stage = "layout"
            self.last_page = number
            if number > self.estimate:
                self.estimate = math.ceil(number * 1.05) + 1

            fraction = min(number / self.estimate, 1.0)
            if self.tty:
                if now - self.last_draw < self.MIN_INTERVAL and number != self.estimate and not force:
                    return
                self.last_draw = now
                filled = int(fraction * self.BAR_WIDTH)
                bar = "█" * filled + "░" * (self.BAR_WIDTH - filled)
                per_page = (now - self.layout_started) / number
                left = per_page * (self.estimate - number) + self.WRITE_RATIO * per_page * self.estimate
                self._status(f"[2/3] {self._verb()} page {number:,} of ~{self.estimate:,}  [{bar}] {int(fraction * 100):3d}%  "
                             f"{_clock(now - self.started)} elapsed, ~{_clock(left)} left{self._parts_note()}")
            else:
                bucket = int(fraction * 10)
                if bucket > self.last_bucket:
                    self.last_bucket = bucket
                    self._status(f"[2/3] {self._verb()} page {number:,} of ~{self.estimate:,} ({bucket * 10}%), "
                                 f"{_clock(now - self.started)} elapsed{self._parts_note()}")

    def _verb(self):
        return "Rendering" if self.parts_total else "Laying out"

    def _parts_note(self):
        return f"  (parts done: {self.parts_done}/{self.parts_total})" if self.parts_total else ""

    def writing(self):
        with self.lock:
            now = time.monotonic()
            self.write_started = now
            if self.layout_started is not None:
                self.layout_seconds = now - self.layout_started
            self.stage = "writing"
            self._draw_silent_stage()

    def done(self, pages, output):
        self.stopped.set()
        with self.lock:
            self.stage = "done"
            message = f"Done: {pages:,} page{'s' if pages != 1 else ''} in {_clock(time.monotonic() - self.started)} → {output}"
            self._write(("\r" + message + "\x1b[K\n") if self.tty else (message + "\n"))

    def abort(self):
        """Stop the ticker and end the status line, e.g. before an error message."""
        self.stopped.set()
        with self.lock:
            if self.tty and self.stage not in (None, "done"):
                self._write("\n")
            self.stage = "done"
