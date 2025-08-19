from django.urls import path
from .views.logs_view import logs_view

urlpatterns = [
    path('', logs_view, name='logs_view'),
]
