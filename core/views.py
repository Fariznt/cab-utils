from django.shortcuts import render
from django.urls import reverse
from django.http import HttpResponse, HttpResponseRedirect
from django.contrib.auth import authenticate, login, logout


# Create your views here.
def index(request):
    return render(request, "core/index.html")


def register_view(request):
    pass

def login_view(request):
    if request.method == "POST":
        username = request.POST["username"]
        password = request.POST["password"]
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            return HttpResponseRedirect(reverse("index"))
        else: 
            return render(request, "core/login.html", {
                "message": "Invalid username and/or password"
            })
    else:
        return render(request, "core/login.html")

def profile_view(request):
    if not request.user.is_authenticated:
        return HttpResponseRedirect(reverse("login"))

def logout_view(request):
    logout(request)
    return render(request, "core/index.html")