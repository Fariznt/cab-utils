document.addEventListener('DOMContentLoaded', () => { 
    editBtn = document.querySelector('.edit-button')
    editBtn.addEventListener('click', () => {
        console.log("reached")
        editBtn.textContent = "save"
    })
});
