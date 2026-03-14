from django.urls import path
from . import views

urlpatterns = [
    path('', views.list_reviews, name='list-reviews'),
    path('trigger/', views.trigger_review, name='trigger-review'),
    path('stats/', views.get_review_stats, name='review-stats'),
    path('<int:review_id>/', views.get_review, name='get-review'),
    path('<int:review_id>/delete/', views.delete_review, name='delete-review'),
    path('<int:review_id>/re-review/', views.re_review, name='re-review'),
]