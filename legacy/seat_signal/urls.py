from django.urls import path
from . import views

urlpatterns = [
    path('', views.ss_view, name='seat_signal'),

    # API Routes
    path('api/watch_course', views.watch_course, name='watch_course'),
    path('api/seat-signals/<str:semester>/<str:code>/<str:section>/', views.stop_watching_course, name='stop_watching_course'),
    path('api/get_auth', views.get_auth, name='get_auth'),
    path('api/get_signal_sessions', views.get_signal_sessions, name='get_signal_sessions')
]
