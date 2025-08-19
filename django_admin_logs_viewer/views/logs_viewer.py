import os
import re
import json
import shutil
import tempfile
import logging
import pytz
from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import render, redirect
from django.urls import reverse
from django.http import FileResponse
from django.core.paginator import Paginator
from datetime import datetime
from django_admin_logs_viewer.conf import app_settings
from django.utils import timezone

@staff_member_required
def logs_viewer(request):
    errors = _validate_settings()
    if errors:
        for e in errors:
            logging.error(e)
        return render(request, "admin/errors.html", {
            "errors": errors,
            "breadcrumbs": [{"name": "Logs error", "url": ""}],
        })

    log_dirs = app_settings.LOGS_DIRS
    current_path = request.GET.get("path", "")

    if current_path:
        current_path = os.path.abspath(current_path)
        if not _is_inside_logs_dirs(current_path):
            return render(request, "admin/errors.html", {
                "errors": ["Path does not exist or is outside of LOGS_DIRS."],
                "breadcrumbs": [{"name": "Logs error", "url": ""}],
            })

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
            is_dir = os.path.isdir(log_dir)
            errors_count = _count_errors_in_dir(log_dir, request)

            items.append({
                "name": os.path.basename(log_dir),
                "path": log_dir,
                "is_dir": is_dir,
                "errors_since_last_login": errors_count
            })

        if len(items) == 1: # Only one directory -> display its insights right away
            drilled = _auto_drill_down(items[0]["path"])
            return redirect(f"{request.path}?path={drilled}")

        return render(request, "admin/logs_dir.html", {
            "items": items,
            "current_path": current_path,
            "breadcrumbs": _build_breadcrumbs(current_path, log_dirs),
        })

    current_path = os.path.abspath(current_path)
    current_path = _auto_drill_down(current_path)

    # Handle directories
    if os.path.isdir(current_path):
        items = []
        for name in sorted(os.listdir(current_path)):
            item_path = os.path.join(current_path, name)
            is_dir = os.path.isdir(item_path)
            errors_count = _count_errors_in_dir(item_path, request)

            items.append({
                "name": name,
                "path": item_path,
                "is_dir": is_dir,
                "errors_since_last_login": errors_count,
            })

        return render(request, "admin/logs_dir.html", {
            "items": items,
            "current_path": current_path,
            "breadcrumbs": _build_breadcrumbs(current_path, log_dirs),
        })
    # Handle files
    else:
        parser_config = app_settings.LOGS_PARSER
        rows_per_page = app_settings.LOGS_ROWS_PER_PAGE
        page_number = int(request.GET.get("page", 1))
        search_query = request.GET.get("search_query", "").strip()
        level_filter = request.GET.get("level_filter", "").strip().lower()
        time_from = request.GET.get("time_from", "").strip()
        time_to = request.GET.get("time_to", "").strip()

        with open(current_path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()

        column_names, column_types, all_rows = _parse_logs(content, parser_config)

        if search_query:
            filtered_rows = []
            for row in all_rows:
                if any(search_query.lower() in str(value).lower() for value in row):
                    filtered_rows.append(row)
            all_rows = filtered_rows

        if level_filter:
            level_column_index = list(map(lambda e: e.lower(), column_types)).index("level")
            if level_column_index >= 0:
                filtered_rows = []
                for row in all_rows:
                    row_level = str(row[level_column_index]).lower()
                    if row_level == level_filter:
                        filtered_rows.append(row)
                all_rows = filtered_rows

        if (time_from or time_to) and column_types:
            time_column_index = list(map(lambda e: e.lower(), column_types)).index("time")
            filtered_rows = []
            for row in all_rows:
                row_time = datetime.fromisoformat(row[time_column_index])
                include = True
                if time_from:
                    from_dt = datetime.fromisoformat(time_from)
                    if row_time < from_dt:
                        include = False
                if time_to:
                    to_dt = datetime.fromisoformat(time_to)
                    if row_time > to_dt:
                        include = False
                if include:
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
            "current_path": current_path,
            "page_obj": page_obj,
            "search_query": search_query,
            "level_filter": level_filter,
            "breadcrumbs": _build_breadcrumbs(current_path, log_dirs),
        })

def _count_errors_in_rows(all_rows, column_types, request):
    prev_login_str = request.session.get('previous_login')

    if not prev_login_str or not hasattr(app_settings, "LOGS_TIMEZONE"):
        return 0

    try:
        prev_login = datetime.fromisoformat(prev_login_str)
    except Exception:
        return 0

    log_tz = pytz.timezone(app_settings.LOGS_TIMEZONE)

    if timezone.is_naive(prev_login):
        prev_login = log_tz.localize(prev_login)

    errors_count = 0
    column_types_lower = [s.lower() for s in column_types]

    try:
        time_column_index = column_types_lower.index("time")
        level_column_index = column_types_lower.index("level")
    except ValueError:
        return 0

    for row in all_rows:
        row_time = datetime.fromisoformat(str(row[time_column_index]))
        if timezone.is_naive(row_time):
            row_time = log_tz.localize(row_time)

        row_level = str(row[level_column_index]).lower()
        if row_time >= prev_login and row_level in ("error", "critical"):
            errors_count += 1

    return errors_count

def _count_errors_in_dir(path, request):
    if not app_settings.SHOW_ERRORS_SINCE_LAST_LOG_IN:
        return 0

    total_errors = 0
    parser_config = app_settings.LOGS_PARSER

    if os.path.isfile(path):
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
        column_names, column_types, all_rows = _parse_logs(content, parser_config)
        total_errors += _count_errors_in_rows(all_rows, column_types, request)

    elif os.path.isdir(path):
        for root, dirs, files in os.walk(path):
            for filename in files:
                file_path = os.path.join(root, filename)
                with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()
                column_names, column_types, all_rows = _parse_logs(content, parser_config)
                total_errors += _count_errors_in_rows(all_rows, column_types, request)

    return total_errors

def _build_breadcrumbs(current_path, log_dirs):
    breadcrumbs = [{
        'name': 'Logs directories',
        'url': reverse('logs_viewer')
    }]

    for log_dir in log_dirs:
        if current_path.startswith(log_dir):
            relative_parts = os.path.relpath(current_path, log_dir).split(os.sep)
            breadcrumbs.append({
                'name': os.path.basename(log_dir),
                'url': f"{reverse('logs_viewer')}?path={log_dir}"
            })
            accumulated_path = log_dir
            for part in relative_parts:
                if part == '.':
                    continue
                accumulated_path = os.path.join(accumulated_path, part)
                breadcrumbs.append({
                    'name': part,
                    'url': f"{reverse('logs_viewer')}?path={accumulated_path}"
                })
            break

    return breadcrumbs

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
    separators = app_settings.LOGS_SEPARATORS

    records = _split_log_records(content, separators)
    rows = []

    for record in records:
        try:
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
                if not match:
                    raise ValueError(f"Regex did not match line: {main_line}")
                values = list(match.groups())

            if traceback_text:
                values.append(traceback_text[0])
            else:
                values.append("")

            rows.append(values)

        except Exception as e:
            rows.append([f"Parse error: {e}", record])

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

def _is_inside_logs_dirs(path):
    path = os.path.abspath(path)
    for log_dir in app_settings.LOGS_DIRS:
        log_dir = os.path.abspath(log_dir)
        if os.path.commonpath([path, log_dir]) == log_dir:
            return True
    return False

def _validate_settings():
    errors = []

    if not app_settings.LOGS_DIRS or not isinstance(app_settings.LOGS_DIRS, list):
        errors.append("LOGS_DIRS must be a non-empty list of paths.")
    else:
        for d in app_settings.LOGS_DIRS:
            if not os.path.exists(d):
                errors.append(f"Log directory does not exist: {d}")

    if not isinstance(app_settings.LOGS_PARSER, dict):
        errors.append("LOGS_PARSER must be defined as a dictionary.")
    else:
        parser = app_settings.LOGS_PARSER
        if "type" not in parser:
            errors.append("LOGS_PARSER must define 'type'.")
        elif parser["type"] not in ("separator", "json", "regex"):
            errors.append("LOGS_PARSER['type'] must be one of: separator, json, regex.")

        if parser["type"] == "separator" and "separator" not in parser:
            errors.append("LOGS_PARSER['separator'] is required for type 'separator'.")
        if parser["type"] == "regex" and "pattern" not in parser:
            errors.append("LOGS_PARSER['pattern'] is required for type 'regex'.")

    if not app_settings.LOGS_SEPARATORS or not isinstance(app_settings.LOGS_SEPARATORS, list):
        errors.append("LOGS_SEPARATORS must be a non-empty list of regex patterns.")

    if app_settings.LOGS_ROWS_PER_PAGE and app_settings.LOGS_ROWS_PER_PAGE <= 0:
        errors.append("LOGS_ROWS_PER_PAGE should be > 0")

    return errors
