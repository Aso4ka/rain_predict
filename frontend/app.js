const form = document.getElementById("registerForm");

if(form) {
    form.addEventListener("submit", (e) => {
        e.preventDefault();

        alert("Регистрация успешно выполнена!");

        window.location.href = "dashboard.html";
    });
}