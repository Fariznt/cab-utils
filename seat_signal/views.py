from django.shortcuts import render, HttpResponse

# Create your views here.
def ss_view(request):
    return render(request, 'seat_signal.html')
