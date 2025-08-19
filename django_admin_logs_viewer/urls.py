from django.urls import path
from .views.logs_viewer import logs_viewer

urlpatterns = [
    path('', logs_viewer, name='logs_viewer'),
]
