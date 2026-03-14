from django.urls import path
from . import views

urlpatterns = [
    path('developers/', views.get_developer_analytics, name='developer-analytics'),
    path('developers/<str:username>/', views.get_developer_detail, name='developer-detail'),
    path('developers/<str:username>/sync/', views.sync_developer, name='developer-sync'),
    path('repositories/', views.get_repository_analytics, name='repository-analytics'),
    path('overview/', views.get_overview_stats, name='overview-stats'),
]