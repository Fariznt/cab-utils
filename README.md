TBD. currently using readme to plan

-do a basic frontend in js for seat_signal to get more experience w/ js basics. include array methods and async/await with fetch. 
-navigation bar
-backend polishing

unspecified time in future:
-react/ts lectures
-frontend polishing
-unit testing


for now, im deferring texting functionality (Due to cost on twilio), but want to keep the app extensible for texting as a signal method.
    if i add texting, i should probably use voips for lower cost.

things i dont want to forget about when im polishing
-refactor tasks.py for scale: have only one running regardless of seat signals, and let it check all people's signals through ONE api call to C@B instead of linearly scaling with signals
    also make the single task a heartbeat task asw---have it cache the timezone.now() so i can check in django code to see if its running (allowing error handling)
    also at the same time add buffer to calls arent spammed and i dont end up on a scam likely list
    exception handling in watch_tasks
    
-enforce that there are no duplicate tasks at multiple levels
-definitely want to do a tiny bit of unit testing at least on the API. MAYBE cb later for selenium if its particularly valuable
-validate phone numbers server+client side, probably with preexisting packages
-encrypt passwords
-let people restart it by text upon failure
-especially for api users, need the service to be cancellable by text. smth like (gpt example):
    def stop_my_task(request):
    # filter by task name and, optionally, by your args
    Task.objects.filter(
        task_name='my_looping_task',
        # Uncomment to match specific args:
        # task_params__contains='"arg1_value"'
    ).delete()
    return HttpResponse("Stopped my_looping_task.")
-privacy policy regarding phone numbers and passwords (not gauranteeing safety of data but gauranteeing it wont be deliberately sold)
-prevent duplicate numbers when watching a seat
-if i ship this fully into production for student use, i need backups for the database, plus figure moving databases in and out without
    pushing sensitive info onto a public repo (scp? django commands?)
-do to the way seat signal is written, need to verify only 1-1 relationship between users and numbers in db and in input validation
    + 1 seat signal per user-session
-when shipping into an actual web app on my vps, use either a multi-container set up that also launches process_tasks or set up honcho
    for now im running python manage.my process_tasks with my app
-my number got labeled scam likely... might have to purchase another from twilio and/or get whitelisted by carrier
-if this app scales to many more users, i should switch to something like telnyx that charges per-second. rn per-minute costs
    are making this expensive.
-security stuff, including sha 384 
-make tos actually work
-profile elements need renaming in templates
    clean up css overall. make filled form and regular form class, and then share them w/ seat signal


IMPORTANT README TO-INCLUDE INFO:
"Want to extend my app? Don't forget to create a .env file and define your own values for..."

FRONTEND PLAN
make navigation bar + background image darker with scrolling