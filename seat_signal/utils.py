def get_recent_sems(sem_ids: list[str], n: int = 2) -> list[str]:
    """
    View helper that takes a list of semester ids (e.g. 202510) and returns a list of the n most recent semesters as a tuple including 
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
    View helper that takes a string semester id and returns a readable representation of the semester (e.g. Fall 2025)
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
    View helper that takes a readable representation of the semester in '<Term> <Year>' format and converts to semester id
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