// WhatsApp click-to-chat widget — Master Commercial Cleaning
document.addEventListener("DOMContentLoaded", function () {
  var waFab = document.querySelector("#wa-fab");
  var waOverlay = document.querySelector("#wa-overlay");
  var waForm = document.querySelector("#wa-form");
  var waClose = document.querySelector("#wa-close");
  var WA_NUMBER = "17052807059"; // wa.me format: country code + number, no symbols (test number)

  function waOpen() {
    if (!waOverlay) return;
    waOverlay.classList.add("wa-open");
    var nameInput = document.querySelector("#wa-name");
    if (nameInput) nameInput.focus();
  }

  function waCloseModal() {
    if (waOverlay) waOverlay.classList.remove("wa-open");
  }

  if (waFab) waFab.addEventListener("click", waOpen);
  if (waClose) waClose.addEventListener("click", waCloseModal);
  if (waOverlay) {
    waOverlay.addEventListener("click", function (e) {
      if (e.target === waOverlay) waCloseModal();
    });
  }
  document.addEventListener("keydown", function (e) {
    if (e.key === "Escape" && waOverlay && waOverlay.classList.contains("wa-open")) {
      waCloseModal();
    }
  });

  if (waForm) {
    waForm.addEventListener("submit", function (e) {
      e.preventDefault();
      var name = document.querySelector("#wa-name").value.trim();
      var phone = document.querySelector("#wa-phone").value.trim();
      var service = document.querySelector("#wa-service").value;
      var message = document.querySelector("#wa-message").value.trim();

      if (!name || !phone) return;

      var lines = [
        "Hi Master Commercial Cleaning! My name is " + name + ".",
        "Phone: " + phone,
        "Interested in: " + service,
      ];
      if (message) lines.push("Details: " + message);
      var text = encodeURIComponent(lines.join("\n"));

      window.open("https://wa.me/" + WA_NUMBER + "?text=" + text, "_blank");
      waCloseModal();
      waForm.reset();
    });
  }
});
