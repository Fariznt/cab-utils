from django.shortcuts import render, HttpResponse
from django.http import JsonResponse
from core.models import CourseSession
from seat_signal.tasks import watch_task
from seat_signal.models import SeatSignal
from django.db.models.functions import Substr
from django.db.models import Q
from django.core.exceptions import MultipleObjectsReturned




def ss_view(request):
    """
    The only view that renders a page for the Seat Signal app. Frontend js handles any UI changes using API views below
    """
    sems = list(CourseSession.objects.values_list('sem_id', flat=True).distinct())
    recent_sems = get_recent_sems(sems) # list of ruples e.g. ('202510', 'Fall 2025')

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
        'recent_sems': recent_sems
    })

def watch_course(request):
    if not request.user.is_authenticated:
        return JsonResponse({'status': 'failure', 'message': 'User not authenticated'})
    
    # Pull expected parameters
    sem_id = request.POST['sem_id']
    code = request.POST['code'] # course session identifier
    section = request.POST['section']
    contact_method = request.POST['contact_method']

    # Validate that expected parameters are defined
    for name, val in (('sem_id', sem_id), ('code', code), ('section', section), ('contact_method', contact_method)):
        if not val:
            return JsonResponse({'status': 'failure', 'message': f'Missing parameter: {name}'}, status=400)
    if contact_method not in ('call', 'text', 'both'):
        return JsonResponse({'status': 'failure', 'message': 'Invalid contact method'})

    # Get session
    try:
        session = CourseSession.objects.get(code=code, section=section, sem_id=sem_id)
        print(session.section)
    except CourseSession.DoesNotExist:
        return JsonResponse({'status': 'failure', 'message': 'Session does not exist!'})
    except MultipleObjectsReturned:
        return JsonResponse({'status': 'failure', 
                             'message': f'Multiple course sessions satisfy this code, section, and semester.'})

    # Create signal / start watching the course session
    try:
        new_seat_signal = SeatSignal(user = request.user, session = session)
        new_seat_signal.save()

        number = request.user.phone_num

        #watch_task(session.crn, number, contact_method)
        return JsonResponse({'status': 'success', 'message': 'Watching course, crn:' + session.crn})
    except Exception as e:
        return JsonResponse({'status': 'failure', 'message': f'Error: {e}'})

    
def get_recent_sems(sem_ids: list[str], n: int = 2) -> list[str]:
    """
    Takes a list of semester ids (e.g. 202510) and returns a list of the n most recent semesters as a tuple including 
    a readable version of the semester representation e.g. (202510, Fall 2025)
    """
    # Define chronological ordering of term-related substring in sem_id 
    # (for e.g. '10' in id '202510' can be interpreted to mean last term of a year)
    term_rank = {
        '15': 0, # Winter
        '20': 1, # Spring
        '00': 2, # Summer
        '10': 3  # Fall
    }
    # sort by year, term_rank
    sorted_ids = sorted(
        sem_ids,
        key = lambda id: (int(id[:4]), term_rank.get(id[4:])),
        reverse= True
    )

    recent_sem_ids = sorted_ids[:n]
    recent_sem_names = [get_sem_str(s) for s in recent_sem_ids]
    return [(recent_sem_ids[i], recent_sem_names[i]) for i in range(len(recent_sem_ids))]

def get_sem_str(sem_id: str) -> str:
    """
    Takes a string semester id and returns a readable representation of the semester (e.g. Fall 2025)
    """
    term_names = {
        '15': 'Winter',
        '20': 'Spring',
        '00': 'Summer',
        '10': 'Fall'
    }
    term = term_names[sem_id[4:]]
    year = sem_id[:4]
    return f'{term} {year}'

def get_sem_id(sem_str: str) -> str:
    """
    Takes a readable representation of the semester in '<Term> <Year>' format and converts to semester id
    """
    term_names = {
        'Winter': '15',
        'Spring': '20',
        'Summer': '00',
        'Fall': '10'
    }
    year = sem_str[5:]
    term_id = term_names[sem_str[:-5]]

    return year + term_id