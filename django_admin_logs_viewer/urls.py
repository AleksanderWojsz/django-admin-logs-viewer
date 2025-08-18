from django.contrib import admin
from django.urls import path
from django_admin_logs_viewer.views.logs_viewer import logs_viewer

urlpatterns = [
    path('admin/logs/', logs_viewer, name='logs_viewer'),
    path('admin/', admin.site.urls),
]
