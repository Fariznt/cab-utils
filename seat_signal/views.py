from django.shortcuts import render, HttpResponse
from django.http import JsonResponse
from core.models import CourseSession
from seat_signal.models import SeatSignal
from django.db.models import Q
from django.core.exceptions import MultipleObjectsReturned
import seat_signal.utils as utils
import json
from django.conf import settings

def ss_view(request):
    """
    The only view that renders a page for the Seat Signal app. Frontend js handles any UI changes using API views below
    """
    sems = list(CourseSession.objects.values_list('sem_id', flat=True).distinct())
    recent_sems = utils.get_recent_sems(sems) # list of tuples e.g. ('202510', 'Fall 2025')

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
        'sections': sections,
        'recent_sems': recent_sems,
        'signal_cap': settings.SIGNAL_CAP
    })

def watch_course(request):
    """
    API endpoint that to POST a new course session-watching 'Seat Signal'.
    """

    if not request.user.is_authenticated:
        return JsonResponse({'status': 'failure', 'message': 'User not authenticated'})

    # Enforce cap on seat signals per phone number
    # good frontend code prevents this but backend validation is critical due to twilio costs
    if SeatSignal.objects.filter(user=request.user).count() >= int(settings.SIGNAL_CAP):
        return JsonResponse({'status': 'failure', 'message': 'You have reached the cap on watched courses!'})

    
    # Pull expected parameters
    sem_id = request.POST['sem_id']
    code = request.POST['code'] # course session identifier
    section = request.POST['section']
    contact_method = request.POST['contact_method']

    # Validate that expected parameters are defined
    for name, val in (('sem_id', sem_id), ('code', code), ('section', section), ('contact_method', contact_method)):
        if not val:
            return JsonResponse({'status': 'failure', 'message': f'An unexpected error occured'}, status=400)
    if contact_method not in ('call', 'text', 'both'):
        return JsonResponse({'status': 'failure', 'message': 'Invalid contact method'})

    # Get session
    try:
        session = CourseSession.objects.get(code=code, section=section, sem_id=sem_id)
    except CourseSession.DoesNotExist:
        return JsonResponse({'status': 'failure', 'message': 'Session does not exist in relevant semesters!'})
    except MultipleObjectsReturned:
        return JsonResponse({'status': 'failure', 
                             'message': f'Multiple course sessions satisfy this code, section, and semester.'})

    # Create signal / start watching the course session
    try:
        new_seat_signal, created = SeatSignal.objects.get_or_create(
            user = request.user,
            session = session
        )

        if created:
            return JsonResponse({'status': 'success', 'message': 'Watching course, crn:' + session.crn})
        else:
            return JsonResponse({'status': 'failure', 'message': 'Already watching this course session!'}, status=400)

    except Exception as e:
        return JsonResponse({'status': 'failure', 'message': f'An unexpected error occured'}, status=400)
    
def stop_watching_course(request, semester, code, section):
    """
    API endpoint to DELETE an instance of seat signal with a given semester, course code, and section.
    """
    if request.method != 'DELETE':
        return HttpResponse(status=405)  # Method not allowed
    try:
        # pull expected parameters
        sem_id = utils.get_sem_id(semester)
        session_to_delete = CourseSession.objects.get(code = code, section = section, sem_id = sem_id)
        signal_to_delete = SeatSignal.objects.get(user = request.user, session = session_to_delete)
        signal_to_delete.delete()
        return HttpResponse(status=204)  # No content
    except (CourseSession.DoesNotExist, SeatSignal.DoesNotExist):
        return HttpResponse(status=404)

def get_signal_sessions(request):
    """
    API endpoint to GET session info for all active signals for active user in JSON.
    """
    sessions = CourseSession.objects.filter(session_signals__user=request.user)
    sessions_attr_list = []
    for session in sessions:
        session_elt = {
            'semester': utils.get_sem_str(session.sem_id),
            'code': session.code,
            'section': session.section
        }
        sessions_attr_list += [session_elt]

    payload = {
        'attribute_list': sessions_attr_list,
        'count': len(sessions_attr_list)
        }

    return JsonResponse(payload)

def get_auth(request):
    """
    API endpoint to GET authentication information.
    """
    is_auth = request.user.is_authenticated
    return JsonResponse({
        "is_authenticated": is_auth,
        "username": request.user.username if is_auth else None,
    })