import os
import pytz
from datetime import datetime
from django.utils import timezone
from django.urls import reverse
from .parser import _parse_logs
from django_admin_logs_viewer.conf import app_settings

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

    for row in reversed(all_rows): # Assumes logs are from oldest to newest
        row_time = datetime.fromisoformat(str(row[time_column_index]))
        if timezone.is_naive(row_time):
            row_time = log_tz.localize(row_time)

        if row_time < prev_login:
            break

        row_level = str(row[level_column_index]).lower()
        if row_time >= prev_login and row_level in ("error", "critical"):
            errors_count += 1

    return errors_count

def _count_errors_in_dir(path, request):
    total_errors = 0
    parser_config = app_settings.LOGS_PARSER

    if not app_settings.SHOW_ERRORS_SINCE_LAST_LOG_IN or not parser_config or not parser_config.get("column_names") or not app_settings.LOGS_SEPARATOR:
        return 0

    if os.path.isfile(path):
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
        mode ,column_names, column_types, all_rows = _parse_logs(content, parser_config)
        total_errors += _count_errors_in_rows(all_rows, column_types, request)

    elif os.path.isdir(path):
        for root, dirs, files in os.walk(path):
            for filename in files:
                file_path = os.path.join(root, filename)
                with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()
                mode, column_names, column_types, all_rows = _parse_logs(content, parser_config)
                total_errors += _count_errors_in_rows(all_rows, column_types, request)

    return total_errors

def _build_breadcrumbs(current_path, log_dirs):
    breadcrumbs = [{
        'name': 'Logs directories',
        'url': reverse('logs_view')
    }]

    current_path = os.path.normpath(current_path)
    log_dirs = [os.path.normpath(d) for d in log_dirs]

    for log_dir in log_dirs:
        if current_path.startswith(log_dir):
            relative_parts = os.path.relpath(current_path, log_dir).split(os.sep)
            breadcrumbs.append({
                'name': os.path.basename(log_dir),
                'url': f"{reverse('logs_view')}?path={log_dir}"
            })
            accumulated_path = log_dir
            for part in relative_parts:
                if part == '.':
                    continue
                accumulated_path = os.path.join(accumulated_path, part)
                breadcrumbs.append({
                    'name': part,
                    'url': f"{reverse('logs_view')}?path={accumulated_path}"
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

def _is_inside_logs_dirs(path):
    path = os.path.abspath(path)
    for log_dir in app_settings.LOGS_DIRS:
        log_dir = os.path.abspath(log_dir)
        if os.path.commonpath([path, log_dir]) == log_dir:
            return True
    return False

def _validate_settings():
    errors = []

    # --- LOGS_DIRS ---
    if not app_settings.LOGS_DIRS or not isinstance(app_settings.LOGS_DIRS, list):
        errors.append("LOGS_DIRS must be a non-empty list of paths.")
    else:
        for d in app_settings.LOGS_DIRS:
            if not os.path.exists(d):
                errors.append(f"Log directory does not exist: {d}")

    # --- LOGS_PARSER ---
    if app_settings.LOGS_PARSER:
        if not isinstance(app_settings.LOGS_PARSER, dict):
            errors.append("LOGS_PARSER must be defined as a dictionary.")
        else:
            parser = app_settings.LOGS_PARSER
            if "type" not in parser:
                errors.append("LOGS_PARSER must define 'type'.")
            elif parser["type"] not in ("separator", "json", "regex"):
                errors.append("LOGS_PARSER['type'] must be one of: separator, json, regex.")

            if parser.get("type") == "separator" and "separator" not in parser:
                errors.append("LOGS_PARSER['separator'] is required for type 'separator'.")
            if parser.get("type") == "regex" and "pattern" not in parser:
                errors.append("LOGS_PARSER['pattern'] is required for type 'regex'.")

            if "column_names" in parser and "column_types" in parser:
                if len(parser["column_names"]) != len(parser["column_types"]):
                    errors.append("LOGS_PARSER['column_names'] and LOGS_PARSER['column_types'] must have the same length.")

    # --- LOGS_SEPARATOR ---
    if app_settings.LOGS_SEPARATOR:
        if not isinstance(app_settings.LOGS_SEPARATOR, str):
            errors.append("LOGS_SEPARATOR must be a string (regex pattern).")

    # --- LOGS_ROWS_PER_PAGE ---
    if app_settings.LOGS_ROWS_PER_PAGE and app_settings.LOGS_ROWS_PER_PAGE <= 0:
        errors.append("LOGS_ROWS_PER_PAGE should be > 0")

    return errors
