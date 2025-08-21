const csrftoken = window.csrftoken;
const watchCourseUrl = window.watchCourseUrl;
const getAuthUrl = window.getAuthUrl;
const getSessionsUrl = window.getSessionsUrl;

const container = document.querySelector('.signal-page');
const addBtn = container.querySelector('#add-button');
const form = container.querySelector('#signal-form');
const filledFormTpl = document.querySelector('#filled-form');

// Load in user info
let loggedIn = false
fetch(getAuthUrl, {
    method: 'GET',
    credentials: 'same-origin',
    headers: {
        'X-CSRFToken': csrftoken
    },
})
.then(response => response.json())
.then(userAuthInfo => {
    console.log(userAuthInfo)
    if (userAuthInfo.is_authenticated) {
        loadCurrentSignals()
        loggedIn = true
    }
})

document.addEventListener('DOMContentLoaded', () => { 
    // Load form to create new signal when user clicks add button
    addBtn.addEventListener('click', () => {
        if (loggedIn) {
            addSignalForm()
        } else {
            alert("You cannot use SeatSignal without being logged in! A phone number is needed to send alerts.")
        }
    });
});

function loadCurrentSignals() {
    // use API to get existing signals and load them into the page

    fetch(getSessionsUrl, {
        method: 'GET',
        credentials: 'same-origin',
        headers: {
            'X-CSRFToken': csrftoken
        }
    })
    .then(response => response.json())
    .then(signals => {
        for (let i = 0; i < signals.count; i++) {
            sem = signals.attribute_list[i].semester
            code = signals.attribute_list[i].code
            sec = signals.attribute_list[i].section
            loadFilledForm(sem, code, sec)
        }
    })
}

function loadFilledForm(semester, code, section) {
    let filledForm = filledFormTpl.content.cloneNode(true)
    filledForm.querySelector('.signal-sem-val').innerHTML = semester
    filledForm.querySelector('.signal-code-val').innerHTML = code
    filledForm.querySelector('.signal-section-val').innerHTML = section
    container.insertBefore(filledForm, form)
}

function addSignalForm() {
    // remove add button (until submission)
    addBtn.classList.add('d-none');

    // show new signal form
    form.classList.remove('d-none');

    // set the form to receive submission
    const startBtn = container.querySelector('.start');
    startBtn.addEventListener('click', () => submitSignalForm());
}

function submitSignalForm() {
    sem_id = document.querySelector('#sem-selection').value
    sem_label = document.querySelector('#sem-selection').innerHTML
    code = document.querySelector('#code-selection').value
    section = document.querySelector('#section-selection').value
    // contactMethod = ... currently not implemented

    if (validateInput(sem_id, code, section)) {
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

                // add the completed form to loaded forms
                loadFilledForm(sem_label, code, section)

                // bring back add button
                if (!reachedSignalCap()) {
                    addBtn.classList.remove('d-none')
                }
            }
        })
    }
}

function validateInput(sem_id, code, section) {
    // TODO code to validate input, if anything bad display message on screen
    return true; // all valid for now
}

function reachedSignalCap() {
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