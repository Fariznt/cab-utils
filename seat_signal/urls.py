from django.urls import path
from . import views

urlpatterns = [
    path('', views.ss_view, name='seat-signal'),
    # API Routes
    path('api/watch_course', views.watch_course, name='watch_course')
    
]
