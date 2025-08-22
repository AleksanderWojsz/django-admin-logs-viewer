import os
import pytz
from datetime import datetime
from django.utils import timezone
from django.urls import reverse
from .parser import _parse_logs
from django_admin_logs_viewer.conf import app_settings
from django_admin_logs_viewer.defaults import DEFAULTS

def _count_errors_in_rows(all_rows, column_types, request, datetime_format=None):
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
        try:
            row_time_str = str(row[time_column_index])
            row_time = datetime.strptime(row_time_str, datetime_format or DEFAULTS["datetime_format"])

            if timezone.is_naive(row_time):
                row_time = log_tz.localize(row_time)

            if row_time < prev_login:
                break

            row_level = str(row[level_column_index]).lower()
            if row_time >= prev_login and row_level in ("error", "critical"):
                errors_count += 1
        except Exception: # E.g: Line is "unmatched", so parsing time will fail
            pass

    return errors_count

def _count_errors_in_dir(path, request):
    total_errors = 0

    if not getattr(app_settings, "LOGS_SHOW_ERRORS_SINCE_LAST_LOG_IN", False):
        return 0

    if os.path.isfile(path):
        # Find parser for this file
        parser_name = None
        for entry in app_settings.LOGS_DIRS:
            if path.startswith(os.path.abspath(entry["path"])):
                parser_name = entry.get("parser")
                break

        if not parser_name:
            return 0

        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
        mode, column_names, column_types, all_rows, _ = _parse_logs(content, parser_name)
        total_errors += _count_errors_in_rows(all_rows, column_types, request)

    elif os.path.isdir(path):
        for root, dirs, files in os.walk(path):
            for filename in files:
                file_path = os.path.join(root, filename)
                # Find parser for this file
                parser_name = None
                for entry in app_settings.LOGS_DIRS:
                    if file_path.startswith(os.path.abspath(entry["path"])):
                        parser_name = entry.get("parser")
                        break

                if not parser_name:
                    continue

                with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()
                mode, column_names, column_types, all_rows, datetime_format = _parse_logs(content, parser_name)
                total_errors += _count_errors_in_rows(all_rows, column_types, request, datetime_format)

    return total_errors

def _build_breadcrumbs(current_path, log_dirs):
    breadcrumbs = [{
        'name': 'Logs directories',
        'url': reverse('logs_view')
    }]

    current_path = os.path.normpath(current_path)
    log_dirs = [os.path.normpath(d["path"]) for d in log_dirs]

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
        allowed_path = os.path.abspath(log_dir["path"])
        if os.path.commonpath([path, allowed_path]) == allowed_path:
            return True
    return False

def _validate_settings():
    errors = []

    # --- LOGS_DIRS ---
    if not app_settings.LOGS_DIRS or not isinstance(app_settings.LOGS_DIRS, list):
        errors.append("LOGS_DIRS must be a non-empty list of paths.")
    else:
        for d in app_settings.LOGS_DIRS:
            if not os.path.exists(d["path"]):
                errors.append(f"Log directory does not exist: {d['path']}")

    # --- LOGS_PARSERS ---
    if getattr(app_settings, "LOGS_PARSERS", None):
        if not isinstance(app_settings.LOGS_PARSERS, dict):
            errors.append("LOGS_PARSERS must be defined as a dictionary.")
        else:
            for parser_name, parser in app_settings.LOGS_PARSERS.items():
                if "pattern" not in parser:
                    errors.append(f"LOGS_PARSERS['{parser_name}'] must define 'pattern'.")
                if "column_names" in parser and "column_types" in parser:
                    if len(parser["column_names"]) != len(parser["column_types"]):
                        errors.append(f"LOGS_PARSERS['{parser_name}'] column_names and column_types must have the same length.")

    # --- LOGS_ROWS_PER_PAGE ---
    if getattr(app_settings, "LOGS_ROWS_PER_PAGE", None) and app_settings.LOGS_ROWS_PER_PAGE <= 0:
        errors.append("LOGS_ROWS_PER_PAGE should be > 0")

    return errors
