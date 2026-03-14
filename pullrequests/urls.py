from django.urls import path
from . import views

urlpatterns = [
    path('', views.list_pull_requests, name='list-pull-requests'),
    path('sync/', views.sync_pull_requests, name='sync-pull-requests'),
    path('<int:pr_id>/', views.get_pull_request, name='get-pull-request'),
    path('stats/<int:repository_id>/', views.get_repository_pr_stats, name='pr-stats'),
    path('<int:pr_id>/files/', views.get_pull_request_files, name='pull-request-files'),

]