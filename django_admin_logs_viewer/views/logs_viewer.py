import os
from django.conf import settings
from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import render, redirect

@staff_member_required
def logs_viewer(request):
    log_dirs = settings.LOGS_DIRS
    current_path = request.GET.get("path", "")

    # Just entered logs view
    if not current_path:
        directories = []
        for log_dir in log_dirs:
            directories.append({
                "name": os.path.basename(log_dir),
                "path": log_dir
            })

        if len(directories) == 1: # Only one directory -> display its insights right away
            drilled = _auto_drill_down(directories[0]["path"])
            return redirect(f"{request.path}?path={drilled}")

        return render(request, "admin/logs_root.html", {"directories": directories})

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
        breadcrumb = _build_breadcrumb(current_path, log_dirs)
        return render(request, "admin/logs_file.html", {
            "content": content,
            "breadcrumb": breadcrumb
        })

def _build_breadcrumb(current_path, log_dirs):
    for log_dir in log_dirs:
        if current_path.startswith(log_dir):
            relative_parts = os.path.relpath(current_path, log_dir).split(os.sep)
            breadcrumb = [{"name": os.path.basename(log_dir), "path": log_dir}]
            for part in relative_parts:
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
