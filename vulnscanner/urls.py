from django.urls import path
from . import views

urlpatterns = [
    path('trigger/', views.trigger_vuln_scan, name='trigger-vuln-scan'),
    path('list/', views.list_vuln_scans, name='list-vuln-scans'),
    path('<int:scan_id>/', views.get_vuln_scan, name='get-vuln-scan'),
    path('<int:scan_id>/delete/', views.delete_vuln_scan, name='delete-vuln-scan'),
]