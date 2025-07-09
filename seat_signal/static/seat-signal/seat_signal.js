// document.addEventListener('DOMContentLoaded', function() {
//     console.log('reach')
//     // Listen for new signal elements to be added
//     document.querySelector('.add-button').addEventListener('click', add_signal_form);

//     // Load existing signal elements
//     load_signal_elements();
// })

// function add_signal_form() {
//     console.log('reach2')
//     // deal with later: should have forms in same div as buttons.
//     document.querySelector('.signal-page').insertAd = `<div class='signal-element'>HELLO HELLO HELLO</div>` 
//                                                                 + document.querySelector('.signal-page').innerHTML;
// }

// function load_signal_elements() {

// }

const container = document.querySelector('.signal-page');
const addBtn    = container.querySelector('.add-button');
const tpl       = document.getElementById('signal-form-tpl');


document.addEventListener('DOMContentLoaded', () => {


    // adding new signal elements
    addBtn.addEventListener('click', () => add_signal_form());
});

function add_signal_form() {
    const form_clone = tpl.content.cloneNode(true);
    container.insertBefore(form_clone, addBtn);   // keeps button last
}
