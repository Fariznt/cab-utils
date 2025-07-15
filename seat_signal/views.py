from django.shortcuts import render, HttpResponse
from django.http import JsonResponse
from core.models import CourseSession
from seat_signal.tasks import watch_task
from seat_signal.models import SeatSignal
from django.db.models.functions import Substr
from django.db.models import Q
from django.core.exceptions import MultipleObjectsReturned


def ss_view(request):
    sems = CourseSession.objects.values_list('sem_id', flat=True).distinct()
    # recent_sems = ...
    # ^ once i finally do this, i should probably also limit sessions to only those in the given semesters. vvv

    sessions = CourseSession.objects.all()
    codes = (
        sessions
        .order_by('code')
        .values_list('code', flat=True)
        .distinct()
    )
    sections = (
        sessions
        .filter(Q(section__startswith='S') |
            Q(section__startswith='C') |
            Q(section__startswith='L')) # this is to get rid of some rare unneeded section types ("01", "02", and blank)
        .order_by('section')
        .values_list('section', flat=True)
        .distinct()
    )

    return render(request, 'seat_signal.html', {
        'codes': codes,
        'sections': sections #,
        # 'recent_sems': recent_sems
    })

# TODO: this function is written badly. prone to bugs. bad validation. not exposed as an API. redo later but get working first
def watch_course(request):
    code = request.POST['code'] # course session identifier
    section = request.POST['section']
    contact_method = request.POST['contact_method']
    sem_id = request.POST['sem_id'] #TBD
    # code = request.GET.get('code')xxx
    # section = request.GET.get('section') xx 
    # number = request.GET.get('number') xxx

    # TODO: do a complete rewrite of this section to make clear and use try except block instead
    # if no crn provided, attempt to get crn from course code and section 
    # if crn == None: 
    #     code = request.GET.get('code')
    #     section = request.Get.get('section')
    #     if code != None and section != None: # if we have at least code & section, get crn from those values
    #         session = CourseSession.objects.filter(code=str(code), section=str(section))
    #         if not session.exists():
    #             return JsonResponse({
    #                 'status': 'failure', 
    #                 'message': f'Course session with code {str(code)} and section {str(section)} does not exist in the database.'
    #                 })
    #         else:
    #             crn = session.first().get(crn)
    #     else: # if not, return failure status
    #         return JsonResponse({
    #             'status': 'failure', 
    #             'message': 'Provide either a crn or both a course id (e.g. "CSCI 0150") and section (e.g. "S01")'
    #             })
    # if not CourseSession.objects.filter(crn=crn).exists():
    #     return JsonResponse({'status': 'failure', 'message': 'Invalid crn'})
    # # TODO ^^^^^

    if request.user.is_authenticated: # Call came from logged-in user
        # Get session
        try:
            session = CourseSession.objects.get(code=code, section=section, sem_id=sem_id)
        except CourseSession.DoesNotExist:
            return JsonResponse({'status': 'failure', 'message': 'Session does not exist'})
        except MultipleObjectsReturned:
            return JsonResponse({'status': 'failure', 'message': f'Multiple objects satisfy code={code}, section={section}, sem_id={sem_id}. Most likely suggests faulty internal database.'})


        user = request.user

        new_seat_signal = SeatSignal(user = user, session = session)
        new_seat_signal.save()

        number = user.phone_num

        watch_task(session.crn, number, contact_method)
        return JsonResponse({'status': 'success', 'message': 'Watching course, crn:' + crn})
    else:
        return JsonResponse({'status': 'failure', 'message': 'User not authenticated'})
    
