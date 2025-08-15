from django.urls import reverse

def logs_url(request):
    return {
        "logs_url": reverse("logs_viewer")
    }
