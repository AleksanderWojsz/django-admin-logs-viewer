import os
from django.contrib.admin.views.decorators import staff_member_required
from django.http import HttpResponse
from django.template.loader import render_to_string
from django.conf import settings

@staff_member_required
def logs_viewer(request):
    log_root = os.path.join(settings.BASE_DIR, "logs")
    logs = []

    for root, dirs, files in os.walk(log_root):
        for filename in files:
            filepath = os.path.join(root, filename)
            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read()
                logs.append({
                    "name": os.path.relpath(filepath, log_root),
                    "content": content
                })


    html = render_to_string("admin/logs_viewer.html", {"logs": logs})
    return HttpResponse(html)
