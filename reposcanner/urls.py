from django.urls import path
from . import views

urlpatterns = [
    path('', views.list_scans, name='list-scans'),
    path('trigger/', views.trigger_scan, name='trigger-scan'),
    path('stats/', views.get_scan_stats, name='scan-stats'),
    path('<int:scan_id>/', views.get_scan, name='get-scan'),
    path('<int:scan_id>/delete/', views.delete_scan, name='delete-scan'),
    path('<int:scan_id>/re-scan/', views.re_scan, name='re-scan'),
]