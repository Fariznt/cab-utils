document.addEventListener('DOMContentLoaded', function() {
    console.log('reach')
    // Listen for new signal elements to be added
    document.querySelector('.add-button').addEventListener('click', add_signal_form);

    // Load existing signal elements
    load_signal_elements();
})

function add_signal_form() {
    console.log('reach2')
    // deal with later: should have forms in same div as buttons.
    document.querySelector('.signal-elements').innerHTML = `<div class='signal-element'>HELLO HELLO HELLO</div>` 
                                                                + document.querySelector('.signal-elements').innerHTML;
}

function load_signal_elements() {

}