const csrftoken = window.csrftoken;
const watchCourseUrl = window.watchCourseUrl;
const container = document.querySelector('.signal-page');
const addBtn = container.querySelector('.add-button');
const form = document.getElementById('signal-form');

document.addEventListener('DOMContentLoaded', () => { // TODO rmeove probably dont need it with defer
    console.log("logging") //TODO REMOVE
    load_current()
    // add form
    addBtn.addEventListener('click', () => add_signal_form());
});

function load_current() {
    // use API to get existing signals and load them into the page
}


function add_signal_form() {
    // remove add button (until submission)
    addBtn.classList.add('d-none');

    // show new signal form
    form.classList.remove('d-none');

    // set the form to receive submission
    const startBtn = container.querySelector('.start');
    startBtn.addEventListener('click', () => submit_signal_form());
}

function submit_signal_form() {
    sem_id = document.querySelector('#sem-selection').value,
    code = document.querySelector('#code-selection').value,
    section = document.querySelector('#section-selection').value
    // contactMethod = ... currently not implemented

    if (validate_input(sem_id, code, section)) {
        // create form using what the user selected
        const formData = new FormData();
        formData.append('sem_id', sem_id);
        formData.append('code', code);
        formData.append('section', section);
        formData.append('contact_method', 'call'); // hardcoded for now as there is no backend for texting

        // post new seat signal (use watch_course)
        fetch(watchCourseUrl, {
            method: 'POST',
            credentials: 'same-origin',
            headers: {
                'X-CSRFToken': csrftoken
            },
            body: formData
        })
        .then(response => response.json())
        .then(result => {
            if (result.status == 'failure') {
                document.querySelector('#message').innerHTML = result.message
            } else if (result.status == 'success') {
                // remove form used to add signal
                form.classList.add('d-none');

                // append the completed form
                temp = document.createElement("span"); // TEMPORARY ELEMENT, WILL BE REPLACED WITH FULL ACTUAL FORM. implementation will be shared with initial completed form loading
                temp.textContent = 'temp';
                container.insertBefore(temp, form);

                // bring back add button
                if (!reached_signal_cap()) {
                    addBtn.classList.remove('d-none')
                }
            }
        })
    }
}

function validate_input(sem_id, code, section) {
    // TODO code to validate input, if anything bad display message on screen
    return true; // all valid for now
}

function reached_signal_cap() {
    // TODO use api to check if reached
    return false;
}

// Get CSRF token
function getCookie(name) {
  const match = document.cookie.match(
    new RegExp('(^|;\\s*)' + name + '=([^;]+)')
  );
  return match ? decodeURIComponent(match[2]) : null;
}