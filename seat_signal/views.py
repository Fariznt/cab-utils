from django.shortcuts import render, HttpResponse

def ss_view(request):
    return render(request, 'seat_signal.html')

def watch_course(request):
    pass
