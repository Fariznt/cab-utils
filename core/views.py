from django.shortcuts import render
from django.urls import reverse
from django.http import HttpResponse, HttpResponseRedirect
from django.contrib.auth import authenticate, login, logout
from django.db import IntegrityError
from .models import User

def index(request):
    return render(request, "core/index.html")

def register_view(request):  
    if request.method == "POST": # take registration request from registration page
        username = request.POST["username"]
        password = request.POST["password"]
        confirm_password = request.POST["confirm_password"]
        number = request.POST['phone_number']

        # Validate password
        if password != confirm_password:
            return render(request, "core/register.html", {
                "message": "Confirmed password is not identical"
                })
        
        # TODO other server side validation of inputs
        
        try:
            user = User.objects.create_user(username=username, password=password, phone_num=number)
            user.save()
        except IntegrityError as e:
            print(e)
            return render(request, "core/register.html", {
                "message": "Username was already taken."
            })
        login(request, user)
        return HttpResponseRedirect(reverse("index"))
    else: # load registration page
        return render(request, "core/register.html")

def login_view(request):
    if request.method == "POST": # take login request from login page
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
    else: # load login page
        return render(request, "core/login.html")

def profile_view(request):
    if not request.user.is_authenticated:
        return HttpResponseRedirect(reverse("login"))
    else:
        if request.method == "POST": # TODO: take edit request from profile page 
            pass
        else: # display profile page
            return render(request, "core/profile.html")

def logout_view(request):
    logout(request)
    return HttpResponseRedirect(reverse("index"))
