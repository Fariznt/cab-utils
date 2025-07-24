const csrftoken = window.csrftoken;
const watchCourseUrl = window.watchCourseUrl;
const user = window.currentUsername;
const getAuthUrl = window.getAuthUrl;

const container = document.querySelector('.signal-page');
const addBtn = container.querySelector('.add-button');
const form = document.getElementById('signal-form');


// Load in user info
let logged_in = false
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
    console.log("load called")
    // 1. use get_signals and log it so ik what im even getting. decide on it or smth else b4 moving on
    // 2. make nay needed changes to the view function
    // 3. make the actual loadCurrentsignals function
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
    sem_id = document.querySelector('#sem-selection').value,
    code = document.querySelector('#code-selection').value,
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

                // append the completed form
                temp = document.createElement("span"); // TEMPORARY ELEMENT, WILL BE REPLACED WITH FULL ACTUAL FORM. implementation will be shared with initial completed form loading
                temp.textContent = 'temp';
                container.insertBefore(temp, form);

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