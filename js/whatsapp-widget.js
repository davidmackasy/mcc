// WhatsApp click-to-chat widget — Master Commercial Cleaning
(function () {
  if (document.getElementById("zsiqscript")) return;
  var zoho = document.createElement("script");
  zoho.id = "zsiqscript";
  zoho.defer = true;
  zoho.src = "https://salesiq.zohopublic.com/widget?wc=siq3b029d200719b4370510aefd589bdec30f827e00c97d13cb3ada97fabf888abac25590f3b9a9dd549e92b620a8057e06e9250a05f0cb84341a3c7411623e8ad170e1b0008154a903077e31309cd328c4";
  document.head.appendChild(zoho);
})();

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
