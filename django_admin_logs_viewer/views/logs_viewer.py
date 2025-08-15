import os
import re
import json
from django.conf import settings
from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import render, redirect
from django.urls import reverse

@staff_member_required
def logs_viewer(request):
    log_dirs = settings.LOGS_DIRS
    current_path = request.GET.get("path", "")

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
            "breadcrumb": breadcrumb
        })
    # Handle files
    else:
        with open(current_path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()

        parsed_rows = None
        column_names = None
        parser_config = getattr(settings, "LOGS_PARSER", None)
        if parser_config:
            column_names, parsed_rows = _parse_logs(content, parser_config)

        return render(request, "admin/logs_file.html", {
            "content": content if not parsed_rows else None,
            "rows": parsed_rows,
            "column_names": column_names,
            "breadcrumb": _build_breadcrumb(current_path, log_dirs)
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
    column_names = parser_config.get("column_names", [])

    if parser_type == "separator":
        rows = []
        for line in content.splitlines():
            values = line.split(parser_config["separator"])
            rows.append(values)
        return column_names, rows

    elif parser_type == "json":
        rows = []

        for line in content.splitlines():
            line = line.replace("\\", "\\\\") # So \ works
            obj = json.loads(line)
            rows.append(obj.values())

            if not column_names:
                column_names = obj.keys()
        return column_names, rows

    else: # parser_type == "regex":
        regex = re.compile(parser_config["pattern"])
        rows = []

        for line in content.splitlines():
            match = regex.fullmatch(line)
            if match:
                rows.append(match.groups())
        return column_names, rows
