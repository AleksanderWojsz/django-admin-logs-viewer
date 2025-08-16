import os
import re
import json
import shutil
import tempfile
from django.conf import settings
from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import render, redirect
from django.urls import reverse
from django.http import FileResponse
from django.core.paginator import Paginator

@staff_member_required
def logs_viewer(request):
    log_dirs = settings.LOGS_DIRS
    current_path = request.GET.get("path", "")

    if request.GET.get("download"):
        if not current_path: # Starting directory (one with listed log_dirs)
            tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".zip")
            with tempfile.TemporaryDirectory() as tmpdir:
                for i, log_dir in enumerate(log_dirs):
                    if os.path.exists(log_dir):
                        dst = os.path.join(tmpdir, f"{os.path.basename(log_dir)}_{i}")
                        shutil.copytree(log_dir, dst)
                shutil.make_archive(tmp.name, "zip", tmpdir)
            return FileResponse(open(tmp.name + ".zip", "rb"), as_attachment=True, filename="all_logs.zip")
        elif os.path.isdir(current_path):
            tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".zip")
            shutil.make_archive(tmp.name, "zip", current_path)
            return FileResponse(open(tmp.name + ".zip", "rb"), as_attachment=True, filename=os.path.basename(current_path) + ".zip")
        elif os.path.isfile(current_path):
            return FileResponse(open(current_path, "rb"), as_attachment=True, filename=os.path.basename(current_path))

    # Just entered logs view
    if not current_path:
        items = []
        for log_dir in log_dirs:
            items.append({
                "name": os.path.basename(log_dir),
                "path": log_dir,
                "is_dir": os.path.isdir(log_dir)
            })

        if len(items) == 1: # Only one directory -> display its insights right away
            drilled = _auto_drill_down(items[0]["path"])
            return redirect(f"{request.path}?path={drilled}")

        return render(request, "admin/logs_dir.html", {
            "items": items,
            "breadcrumb": [{"name": "Log directories", "path": reverse("logs_viewer")}],
            "current_path": current_path,
        })

    current_path = os.path.abspath(current_path)
    current_path = _auto_drill_down(current_path)

    # Handle directories
    if os.path.isdir(current_path):
        items = []
        for name in sorted(os.listdir(current_path)):
            item_path = os.path.join(current_path, name)
            items.append({
                "name": name,
                "path": item_path,
                "is_dir": os.path.isdir(item_path)
            })

        breadcrumb = _build_breadcrumb(current_path, log_dirs)
        return render(request, "admin/logs_dir.html", {
            "items": items,
            "breadcrumb": breadcrumb,
            "current_path": current_path,
        })
    # Handle files
    else:
        parser_config = settings.LOGS_PARSER
        rows_per_page = getattr(settings, "LOGS_ROWS_PER_PAGE", 100)
        page_number = int(request.GET.get("page", 1))
        search_query = request.GET.get("search_query", "").strip()

        with open(current_path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()

        column_names, column_types, all_rows = _parse_logs(content, parser_config)

        if search_query:
            filtered_rows = []
            for row in all_rows:
                if any(search_query.lower() in str(value).lower() for value in row):
                    filtered_rows.append(row)
            all_rows = filtered_rows

        paginator = Paginator(all_rows, rows_per_page)
        page_obj = paginator.get_page(page_number)
        rows = page_obj.object_list

        return render(request, "admin/logs_file.html", {
            "content": None if parser_config else content,
            "rows": rows,
            "column_names": column_names,
            "column_types": column_types,
            "breadcrumb": _build_breadcrumb(current_path, log_dirs),
            "current_path": current_path,
            "page_obj": page_obj,
            "search_query": search_query,
        })

def _build_breadcrumb(current_path, log_dirs):
    for log_dir in log_dirs:
        if current_path.startswith(log_dir):
            relative_parts = os.path.relpath(current_path, log_dir).split(os.sep)
            breadcrumb = [
                {"name": "Log directories", "path": reverse("logs_viewer")},
                {"name": os.path.basename(log_dir), "path": log_dir}
            ]
            for part in relative_parts:
                if part == ".":
                    continue
                breadcrumb.append({"name": part, "path": os.path.join(log_dir, part)})
            return breadcrumb
    return []

def _auto_drill_down(path):
    """Keep going down if directory contains only one subdirectory and no files."""
    while True:
        if not os.path.isdir(path):
            break
        entries = sorted(os.listdir(path))
        subdirs = [e for e in entries if os.path.isdir(os.path.join(path, e))]
        files = [e for e in entries if os.path.isfile(os.path.join(path, e))]
        if len(subdirs) == 1 and not files:
            path = os.path.join(path, subdirs[0])
        else:
            break
    return path

def _parse_logs(content, parser_config):
    parser_type = parser_config["type"]
    column_names = list(parser_config.get("column_names", [])) # List, so copy it made
    column_types = parser_config.get("column_types", [])
    separators = getattr(settings, "LOGS_SEPARATORS", [])

    records = _split_log_records(content, separators)
    rows = []

    for record in records:
        main_line, *traceback_text = record.split("\n", maxsplit=1)

        if parser_type == "separator":
            values = main_line.split(parser_config["separator"])
        elif parser_type == "json":
            main_line = main_line.replace("\\", "\\\\") # So `\` is parsed correctly
            obj = json.loads(main_line)
            if not column_names:
                column_names = list(obj.keys())
            values = list(obj.values())
        else: # parser_type == "regex":
            match = re.fullmatch(parser_config["pattern"], main_line)
            values = list(match.groups())

        if traceback_text:
            values.append(traceback_text[0])

        rows.append(values)

    column_names += ["Traceback"]

    return column_names, column_types, rows

def _split_log_records(content, separators):
    separator_pattern = re.compile("|".join(separators), re.MULTILINE)

    records = []
    current_record = [] # Can be multiline
    for line in content.splitlines():
        if separator_pattern.match(line) and current_record:
            records.append("\n".join(current_record))
            current_record = [line]
        else:
            current_record.append(line)

    if current_record:
        records.append("\n".join(current_record))

    return records
