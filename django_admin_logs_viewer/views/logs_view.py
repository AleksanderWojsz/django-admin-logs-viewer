import os
import tempfile
import shutil
import logging
from datetime import datetime
from django.shortcuts import render, redirect
from django.http import FileResponse
from django.core.paginator import Paginator
from django.contrib.admin.views.decorators import staff_member_required
from django_admin_logs_viewer.conf import app_settings
from .utils import _count_errors_in_dir, _build_breadcrumbs, _auto_drill_down, _is_inside_logs_dirs, _validate_settings
from .parser import _parse_logs
from django_admin_logs_viewer.defaults import DEFAULTS

@staff_member_required
def logs_view(request):

    # Show errors if any
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

    # Check if path exists and is allowed
    if current_path:
        current_path = os.path.abspath(current_path)
        if not _is_inside_logs_dirs(current_path):
            return render(request, "admin/errors.html", {
                "errors": ["Path does not exist or is outside of LOGS_DIRS."],
                "breadcrumbs": [{"name": "Logs error", "url": ""}],
            })

    # Handle downloads
    if request.GET.get("download"):
        if not current_path: # Starting directory (one with listed log_dirs)
            tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".zip")
            with tempfile.TemporaryDirectory() as tmpdir:
                for i, log_dir in enumerate(log_dirs):
                    path = log_dir["path"]
                    if os.path.exists(path):
                        dst = os.path.join(tmpdir, f"{os.path.basename(path)}_{i}")
                        shutil.copytree(path, dst)
                shutil.make_archive(tmp.name, "zip", tmpdir)
            return FileResponse(open(tmp.name + ".zip", "rb"), as_attachment=True, filename="all_logs.zip")
        elif os.path.isdir(current_path):
            tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".zip")
            shutil.make_archive(tmp.name, "zip", current_path)
            return FileResponse(open(tmp.name + ".zip", "rb"), as_attachment=True, filename=os.path.basename(current_path) + ".zip")
        elif os.path.isfile(current_path):
            return FileResponse(open(current_path, "rb"), as_attachment=True, filename=os.path.basename(current_path))

    ###### Handle path changes ######

    # Just entered logs view
    if not current_path:
        items = []
        for log_dir in log_dirs:
            path = log_dir["path"]
            is_dir = os.path.isdir(path)
            errors_count = _count_errors_in_dir(path, request)

            items.append({
                "name": os.path.basename(path),
                "path": path,
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
        rows_per_page = app_settings.LOGS_ROWS_PER_PAGE
        page_number = int(request.GET.get("page", 1))
        search_query = request.GET.get("search_query", "").strip()
        level_filter = request.GET.get("level_filter", "").strip().lower()
        time_from = request.GET.get("time_from", "").strip()
        time_to = request.GET.get("time_to", "").strip()

        with open(current_path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()

        # Find parser
        parser_name = None
        for entry in log_dirs:
            if current_path.startswith(os.path.abspath(entry["path"])):
                parser_name = entry.get("parser")
                break

        mode, column_names, column_types, all_rows, datetime_format = _parse_logs(content, parser_name)

        if all_rows:
            all_rows.reverse() # So new ones are at the top

        # Filter by search query
        if search_query:
            filtered_rows = []
            for row in all_rows:
                if any(search_query.lower() in str(value).lower() for value in row):
                    filtered_rows.append(row)
            all_rows = filtered_rows

        # Filter by level
        if level_filter and column_types:
            level_column_index = list(map(lambda e: e.lower(), column_types)).index("level")
            if level_column_index >= 0:
                filtered_rows = []
                for row in all_rows:
                    row_level = str(row[level_column_index]).lower()
                    if row_level == level_filter:
                        filtered_rows.append(row)
                all_rows = filtered_rows

        # Filter by time
        if (time_from or time_to) and column_types:
            time_column_index = list(map(lambda e: e.lower(), column_types)).index("time")
            if time_column_index >= 0:
                filtered_rows = []
                for row in all_rows:
                    row_time_str = str(row[time_column_index])

                    row_time = datetime.strptime(row_time_str, datetime_format or DEFAULTS["datetime_format"])

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

        if all_rows:
            paginator = Paginator(all_rows, rows_per_page)
            page_obj = paginator.get_page(page_number)
            rows = page_obj.object_list
        else:
            page_obj = None
            rows = None

        return render(request, "admin/logs_file.html", {
            "mode": mode,
            "content": None if parser_name else content,
            "rows": rows,
            "column_names": column_names,
            "column_types": column_types,
            "current_path": current_path,
            "page_obj": page_obj,
            "search_query": search_query,
            "level_filter": level_filter,
            "breadcrumbs": _build_breadcrumbs(current_path, log_dirs),
        })
