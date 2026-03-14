from django.urls import path
from . import views

urlpatterns = [
    path('', views.list_repositories, name='list-repositories'),
    path('add/', views.add_repository, name='add-repository'),
    path('<int:repo_id>/', views.get_repository, name='get-repository'),
    path('<int:repo_id>/delete/', views.delete_repository, name='delete-repository'),
    path('<int:repo_id>/sync/', views.sync_repository, name='sync-repository'),
    path('<int:repo_id>/branches/', views.get_repository_branches, name='repository-branches'),
]