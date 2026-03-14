from django.urls import path
from . import views

urlpatterns = [
    path('', views.list_notifications, name='list-notifications'),
    path('unread-count/', views.get_unread_count, name='unread-count'),
    path('mark-all-read/', views.mark_all_as_read, name='mark-all-read'),
    path('clear-all/', views.clear_all_notifications, name='clear-all'),
    path('<int:notification_id>/read/', views.mark_as_read, name='mark-as-read'),
    path('<int:notification_id>/delete/', views.delete_notification, name='delete-notification'),
]