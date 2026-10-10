"""
Render big documents in parts, then join them.

WeasyPrint keeps every page of a document in memory until it writes the PDF, so memory grows
with the page count (~0.6 GB + ~6.5 MB per page). Big documents are therefore split into parts
of whole files (~100 pages each), each rendered in its own child process, which returns all of
its memory when it exits; several parts can run at the same time.

Things that need the whole document are done afterwards:
  - the contents page, with page numbers written in, rendered once the parts' page counts are known
  - page headers and footers ("x / N"), rendered as an overlay of empty pages and stamped on
  - links from the contents page, bookmarks and metadata, added with pypdf when joining
"""

import logging
import os
import sys
import tempfile
import time

PART_PAGES = 100   # estimated pages per part; override with $CODE2PDF_PART_PAGES


def _timing(label, started):
    """With $CODE2PDF_DEBUG_TIMING set, print how long a stage took."""
    if os.environ.get("CODE2PDF_DEBUG_TIMING"):
        print(f"\n[timing] {label}: {time.monotonic() - started:.2f}s", file=sys.stderr)
    return time.monotonic()


def part_pages():
    return int(os.environ.get("CODE2PDF_PART_PAGES") or PART_PAGES)


def default_jobs():
    """Parts rendered at the same time (~1.3 GB each): 3 with 16 GB of RAM or more, 2 with 8 GB or
    more, else 1; never more than the CPU count."""
    if os.environ.get("CODE2PDF_JOBS"):
        return max(1, int(os.environ["CODE2PDF_JOBS"]))
    try:
        ram = os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES")
    except (ValueError, OSError):
        ram = 8 << 30
    jobs = 3 if ram >= 16 << 30 else 2 if ram >= 8 << 30 else 1
    return max(1, min(jobs, os.cpu_count() or 1))


def partition(estimates, part_pages):
    """Split file indexes (in order) into parts of about PART_PAGES estimated pages; files are never split."""
    parts, current, size = [], [], 0
    for i, pages in enumerate(estimates):
        if current and size + pages > part_pages:
            parts.append(current)
            current, size = [], 0
        current.append(i)
        size += pages
    if current:
        parts.append(current)
    return parts


# --- child process ---------------------------------------------------------------------------

_QUEUE = None
_STARTED = time.monotonic()


def _init_worker(queue):
    global _QUEUE
    _QUEUE = queue


class _PageReporter(logging.Handler):
    def __init__(self, part):
        super().__init__()
        self.part = part

    def emit(self, record):
        message = record.getMessage()
        if message.startswith("Step 5 - Creating layout - Page ") and "up-to-date" not in message:
            _QUEUE.put(("page", self.part, int(message.split("Page ")[1].split()[0])))


def render_part(job):
    """Render one part (no contents page, no headers/footers). Returns its page count and the
    0-based page on which each file starts."""
    from weasyprint import HTML
    from weasyprint.text.fonts import FontConfiguration
    import dir_to_pdf
    import theme as themes

    theme = themes.resolve_theme(job["theme"])
    info = dir_to_pdf.SourceInfo(job["summary"], job["labels"])
    sections, _, _, style_defs = dir_to_pdf.build_sections(job["entries"], theme, info,
                                                           first_index=job["first_index"])
    css = themes.font_face_css() + style_defs + themes.page_css(theme, "", chrome=False)
    html = dir_to_pdf.wrap_document(job["title"], job["printed_moment"], css, "".join(sections))

    logger = logging.getLogger("weasyprint.progress")
    handler = _PageReporter(job["part"])
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False
    started = time.monotonic()
    try:
        document = HTML(string=html, base_url=job["root"]).render(font_config=FontConfiguration())
    finally:
        logger.removeHandler(handler)
    rendered = time.monotonic()
    starts = {}
    for number, page in enumerate(document.pages):
        for anchor in page.anchors:
            if anchor.startswith("f") and anchor[1:].isdigit():
                starts.setdefault(int(anchor[1:]), number)
    document.write_pdf(job["output"])
    if os.environ.get("CODE2PDF_DEBUG_TIMING"):
        print(f"\n[timing] part {job['part']}: {len(document.pages)} pages, render {rendered - started:.1f}s, "
              f"write {time.monotonic() - rendered:.1f}s (process up {time.monotonic() - _STARTED:.1f}s)", file=sys.stderr)
    _QUEUE.put(("done", job["part"], len(document.pages)))
    return {"part": job["part"], "pages": len(document.pages), "starts": starts}


# --- parent process --------------------------------------------------------------------------

def _pdf_date(moment):
    offset = moment.strftime("%z") or "+0000"
    return moment.strftime("D:%Y%m%d%H%M%S") + f"{offset[:3]}'{offset[3:]}'"


def render_in_parts(entries, output, theme, project, printed_moment, info, sources, estimates,
                    progress, root, jobs=None):
    """Render ENTRIES into OUTPUT (a path in the final directory) in parts; see the module docstring."""
    import multiprocessing
    from concurrent.futures import ProcessPoolExecutor
    from pypdf import PdfReader, PdfWriter
    from pypdf.generic import ArrayObject, NameObject
    from weasyprint import HTML
    from weasyprint.text.fonts import FontConfiguration
    import dir_to_pdf
    import theme as themes

    groups_of_files = partition(estimates, part_pages())
    jobs = min(jobs or default_jobs(), len(groups_of_files))
    progress.parts(len(groups_of_files), jobs)
    printed = printed_moment.date().isoformat()
    title = project or "code2pdf"
    right = dir_to_pdf.header_right(project, printed)

    with tempfile.TemporaryDirectory(prefix=".code2pdf-parts-", dir=os.path.dirname(os.path.abspath(output))) as tmp:
        context = multiprocessing.get_context("spawn")
        queue = context.Queue()
        job_list = []
        for part, indexes in enumerate(groups_of_files):
            part_entries = [entries[i] for i in indexes]
            job_list.append({
                "part": part, "first_index": indexes[0], "entries": part_entries, "theme": theme.name,
                "summary": info.summary, "labels": {rel: info.files.get(rel) for rel, _ in part_entries},
                "title": title, "printed_moment": printed_moment, "root": root,
                "output": os.path.join(tmp, f"part{part:04d}.pdf"),
            })

        # Render the parts, reporting pages as the children lay them out
        mark = time.monotonic()
        progress.preparing()
        laid_out = [0] * len(job_list)
        results = {}
        with ProcessPoolExecutor(max_workers=jobs, mp_context=context,
                                 initializer=_init_worker, initargs=(queue,)) as pool:
            futures = [pool.submit(render_part, job) for job in job_list]
            while len(results) < len(futures):
                try:
                    kind, part, value = queue.get(timeout=0.2)
                except Exception:  # queue.Empty
                    kind = None
                if kind == "page":
                    laid_out[part] = max(laid_out[part], value)
                    progress.page(sum(laid_out))
                elif kind == "done":
                    laid_out[part] = value
                    progress.part_done(sum(laid_out))
                for future in futures:
                    if future.done() and id(future) not in results:
                        result = future.result()  # re-raises a child's exception
                        results[id(future)] = result
        results = sorted(results.values(), key=lambda r: r["part"])
        mark = _timing("render parts", mark)

        # Global page numbers: contents first, then the parts in order
        progress.assembling()
        sections_lines = sum(dir_to_pdf.count_lines(sources[path]) for _, path in entries)
        groups = {}
        for i, (rel, _) in enumerate(entries):
            folder, name = os.path.split(rel)
            groups.setdefault(folder, []).append((i, name))
        part_offsets, offset = [], 0
        for result in results:
            part_offsets.append(offset)
            offset += result["pages"]
        body_pages = offset

        contents_pages, contents_pdf = 1, None
        for _ in range(3):  # the numbers depend on the contents page count, which rarely changes
            starts = {}
            for result, part_offset in zip(results, part_offsets):
                for i, local in result["starts"].items():
                    starts[i] = contents_pages + part_offset + local + 1
            nav = dir_to_pdf.build_contents(project, len(entries), sections_lines, printed, info, groups,
                                            page_numbers=starts)
            css = themes.font_face_css() + themes.page_css(theme, right, chrome=False)
            document = HTML(string=dir_to_pdf.wrap_document(title, printed_moment, css, nav)).render(
                font_config=FontConfiguration())
            if len(document.pages) == contents_pages:
                contents_pdf = os.path.join(tmp, "contents.pdf")
                document.write_pdf(contents_pdf)
                break
            contents_pages = len(document.pages)
        else:
            raise RuntimeError("contents page count did not settle")
        mark = _timing("contents page", mark)

        # Headers and footers for every page, as an overlay
        total = contents_pages + body_pages
        page_paths = [""] * contents_pages
        for result in results:
            order = sorted(result["starts"].items(), key=lambda item: item[1])
            for local in range(result["pages"]):
                current = ""
                for i, start in order:
                    if start <= local:
                        current = entries[i][0]
                page_paths.append(current)
        import html as html_module
        overlay_body = "".join(f'<div class="page" data-path="{html_module.escape(path)}"></div>' for path in page_paths)
        overlay_pdf = os.path.join(tmp, "overlay.pdf")
        HTML(string=dir_to_pdf.wrap_document(title, printed_moment, themes.font_face_css() + themes.overlay_css(theme, right),
                                             overlay_body)).write_pdf(overlay_pdf, font_config=FontConfiguration())
        mark = _timing("overlay", mark)

        # Join
        # add_page() rather than append(): append() also imports every named destination (one per
        # code line), which made joining ~10x slower and the PDF ~6x bigger
        writer = PdfWriter()
        for path in [contents_pdf] + [os.path.join(tmp, f"part{r['part']:04d}.pdf") for r in results]:
            for page in PdfReader(path).pages:
                writer.add_page(page)
        overlay = PdfReader(overlay_pdf)
        if len(overlay.pages) != total or len(writer.pages) != total:
            raise RuntimeError(f"page count mismatch: overlay {len(overlay.pages)}, document {len(writer.pages)}, expected {total}")
        mark = _timing("append parts", mark)
        for page, stamp in zip(writer.pages, overlay.pages):
            page.merge_page(stamp)
            page.compress_content_streams()  # merge_page writes the combined stream uncompressed (~6x size)
        mark = _timing("stamp overlay", mark)

        for page in writer.pages[:contents_pages]:
            for annot in page.get("/Annots", []) or []:
                annot = annot.get_object()
                uri = annot.get("/A", {}).get("/URI", "")
                if str(uri).startswith("code2pdf:f"):
                    target = starts[int(str(uri)[len("code2pdf:f"):])] - 1
                    annot[NameObject("/Dest")] = ArrayObject([writer.pages[target].indirect_reference, NameObject("/Fit")])
                    del annot["/A"]
        for i, (rel, _) in enumerate(entries):
            writer.add_outline_item(rel, starts[i] - 1)
        writer.add_metadata({"/Title": title, "/Creator": "code2pdf", "/CreationDate": _pdf_date(printed_moment),
                             "/Producer": "WeasyPrint, pypdf"})
        progress.writing_final()
        writer.write(output)
        _timing("write joined PDF", mark)
        if os.environ.get("CODE2PDF_DEBUG_TIMING"):
            sizes = {name: os.path.getsize(os.path.join(tmp, name)) for name in os.listdir(tmp)}
            print(f"[timing] part files: {sum(v for k, v in sizes.items() if k.startswith('part'))/1e6:.1f} MB, "
                  f"overlay {sizes.get('overlay.pdf', 0)/1e6:.1f} MB, joined {os.path.getsize(output)/1e6:.1f} MB",
                  file=sys.stderr)
    return total
