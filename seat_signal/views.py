from django.shortcuts import render, HttpResponse
from django.http import JsonResponse
from core.models import CourseSession
from seat_signal.tasks import watch_task
from seat_signal.models import SeatSignal

def ss_view(request):
    return render(request, 'seat_signal.html')

# TODO: this function is written sort of badly. prone to bugs. not exposed as an API redo later
def watch_course(request):

    crn = request.GET.get('crn') # course session identifier
    code = request.GET.get('code')
    section = request.GET.get('section')
    number = request.GET.get('number')

    # TODO: do a complete rewrite of this section to make clear and use try except block instead
    # if no crn provided, attempt to get crn from course code and section 
    if crn == None: 
        code = request.GET.get('code')
        section = request.Get.get('section')
        if code != None and section != None: # if we have at least code & section, get crn from those values
            session = CourseSession.objects.filter(code=str(code), section=str(section))
            if not session.exists():
                return JsonResponse({
                    'status': 'failure', 
                    'message': f'Course session with code {str(code)} and section {str(section)} does not exist in the database.'
                    })
            else:
                crn = session.first().get(crn)
        else: # if not, return failure status
            return JsonResponse({
                'status': 'failure', 
                'message': 'Provide either a crn or both a course id (e.g. "CSCI 0150") and section (e.g. "S01")'
                })
    if not CourseSession.objects.filter(crn=crn).exists():
        return JsonResponse({'status': 'failure', 'message': 'Invalid crn'})
    # TODO ^^^^^

    if request.user.is_authenticated:
        # Call came from logged-in user
        user = request.user
        new_seat_signal = SeatSignal(user = user, session = CourseSession.objects.get(crn=crn))
        new_seat_signal.save()
        watch_task(crn)
        return JsonResponse({'status': 'success', 'message': 'Watching course, crn:' + crn})
    else:
        return JsonResponse({'status': 'failure', 'message': 'User not authenticated'})