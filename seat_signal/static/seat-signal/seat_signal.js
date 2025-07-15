const container = document.querySelector('.signal-page');
const addBtn = container.querySelector('.add-button');
const form = document.getElementById('signal-form');


document.addEventListener('DOMContentLoaded', () => {
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
    if (validate_input()) {
        // post new seat signal (use watch_course)
        fetch('api/watch_course', {
            method: 'POST',
            body: JSON.stringify({
                
            })
            // .. CONT HERE
        })

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
}

function validate_input() {
    // TODO code to validate input, if anything bad display message on screen
    return true; // all valid for now
}

function reached_signal_cap() {
    // TODO use api to check if reached
    return false;
}