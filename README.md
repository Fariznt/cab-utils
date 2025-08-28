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
-definitely want to do a tiny bit of unit testing at least on the API. MAYBE cb later for selenium if its particularly valuable
-validate phone numbers server+client side, probably with preexisting packages
-encrypt passwords
-let people restart it by text upon failure
-privacy policy regarding phone numbers and passwords (not gauranteeing safety of data but gauranteeing it wont be deliberately sold)
-prevent duplicate numbers when watching a seat
-if i ship this fully into production for student use, i need backups for the database, plus figure moving databases in and out without
    pushing sensitive info onto a public repo (scp? django commands?)
-do to the way seat signal is written, need to verify only 1-1 relationship between users and numbers in db and in input validation
    + 1 seat signal per user-session
-when shipping into an actual web app on my vps, use either a multi-container set up that also launches process_tasks or set up honcho
    for now im running python manage.my process_tasks with my app
-if this app scales to many more users, i should switch to something like telnyx that charges per-second. rn per-minute costs
    are making this expensive.
-security stuff, including sha 384 
-profile elements need renaming in templates
    clean up css overall. make filled form and regular form class, and then share them w/ seat signal
-dont let register before checking box
-edit button for profiel, deleting profile
-do some editing for background image
-logging error details officially. bc error messages are sort of reserved for nontechnical users

-phone number validation during registration with library phonenumbers 
-fix imgur not working either
-refactor tasks.py for scale: have only one running regardless of seat signals, and let it check all people's signals through ONE api call to C@B instead of linearly scaling with signals (note that i havent verified that deletion carries over to the background task. in refactor, make sure that signals checked are based on current existent objects for model seatsignal, so that it does)
    also make the single task a heartbeat task asw---have it cache the timezone.now() so i can check in django code to see if its running (allowing error handling)
    also at the same time add buffer to calls arent spammed and i dont end up on a scam likely list
    exception handling in watch_tasks
-security stuff:
    -the app right now is sort of susceptible to malicious users, because while there is per-user caps on usage, people can easily make multiple accounts, with or without valid phone numbers. if someone
    (for whatever reason) makes a script to automate user creation and seat signal making, it could stress my vps, clog up signal activation, and use twilio credits
-restfulify and make more secure and consistent my API

-barebones prereq map
-homepage readme barebones
-final security polish, and ship



IMPORTANT README TO-INCLUDE INFO:
"Want to extend my app? Don't forget to create a .env file and define your own values for..."
-decided to not include frontend-specific validation. frontend is raw js so i didnt want unwanted complexity + backend validation is quick and routes user-friendly error message fine
-talk about why chose simple js and scope creep.


FRONTEND PLAN
make navigation bar + background image darker with scrolling