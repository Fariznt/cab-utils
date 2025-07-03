"""
URL configuration for CAB_Utils project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from core import views as core_views
from seat_signal import views as ss_views

urlpatterns = [
    path('admin/', admin.site.urls),

    # core: users + homepage
    path('', core_views.index, name='index'),
    path('profile/', core_views.profile_view, name='profile'),
    path('register/', core_views.register_view, name='register'),
    path('login/', core_views.login_view, name='login'),
    path('logout/', core_views.logout_view, name='logout'),

    # utility apps
    path('seat-signal/', ss_views.ss_view, name='seat-signal')
    # path('prereq-path/' include(prereq_path.urls')) when theres another app

    # API

]
