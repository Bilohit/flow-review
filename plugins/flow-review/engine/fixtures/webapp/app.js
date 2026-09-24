// plugins/flow-review/engine/fixtures/webapp/app.js
document.addEventListener("DOMContentLoaded", () => {
  const form = document.getElementById("login-form");
  form.addEventListener("submit", (event) => {
    event.preventDefault();
    const username = document.getElementById("username").value;
    const password = document.getElementById("pw").value;
    if (username && password) {
      document.getElementById("signin-status").hidden = false;
    }
  });

  document.getElementById("save-button").addEventListener("click", () => {
    console.log("saved");
  });
  document.getElementById("cancel-button").addEventListener("click", () => {
    console.log("cancelled");
  });
  // #help-button is intentionally left without a click handler (planted dead-button bug).

  document.getElementById("load-button").addEventListener("click", () => {
    fetch("/api/fail")
      .then((res) => {
        if (!res.ok) {
          console.error("load failed: " + res.status);
        }
      })
      .catch((err) => console.error("load error: " + err));
  });
});
