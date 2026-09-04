from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("sms/", include("sms.urls")),
    path("ops/", include("ops.urls")),
]
