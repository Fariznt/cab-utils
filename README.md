TBD. currently using readme to plan

-implement an ugly version of seat signal, starting with seat_signal/views.watch_course triggering task.py with django-background-tasks
    -do a basic frontend in js to get more experience w/ js basics. include array methods and async/await with fetch
-react/ts lectures
-navigation bar

for now, im deferring exposing a seat_signal API. it probably wont get used at least for a while, and its complicating my prototyping

things i dont want to forget about when im polishing
-definitely want to do a tiny bit of unit testing at least on the API. MAYBE cb later for selenium if its particularly valuable
-validate phone numbers server+client side, probably with preexisting packages
-encrypt passwords
-login ui format could mimic an older project
-could probably put login/register under the same html file, use js and render context
<!-- Later, let users edit password and phone number in the same format as registration. fix username tho
    <form action="{% url 'update_user' %}" method="POST">
        {% csrf_token %}
        Username:
        <input type="text" name="username" placeholder="e.g. CPax">
        Password:
        <input type="password" name="password" placeholder="e.g. 12345 (jk)">
        Phone number:
        <input type="tel" name="phone-number">
        <input type="submit" value="Login">
    </form> -->
-let people restart it by text upon failure

-privacy policy regarding phone numbers and passwords (not gauranteeing safety of data but gauranteeing it wont be deliberately sold)