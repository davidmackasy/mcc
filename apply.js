(function () {
  var form = document.getElementById("apply-form");
  var step = 1;
  var total = 9;
  var jobRules = {};
  var certCount = 0;
  var extraCount = 0;
  var selectedJob = null;
  var days = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"];
  var parts = ["morning", "afternoon", "evening", "overnight"];
  document.querySelector(".nav-toggle").addEventListener("click", function () {
    document.querySelector(".site-header").classList.toggle("nav-open");
  });
  var daysEl = document.getElementById("days");
  days.forEach(function (day) {
    var row = document.createElement("div");
    row.className = "day-row";
    row.innerHTML = "<strong>" + day[0].toUpperCase() + day.slice(1) + "</strong><div class='checks'>" +
      parts.map(function (part) {
        return "<label><input type='checkbox' data-day='" + day + "' data-part='" + part + "'> " + part + "</label>";
      }).join("") + "</div>";
    daysEl.appendChild(row);
  });
  document.querySelectorAll("input[name='has_cleaning_experience']").forEach(function (input) {
    input.addEventListener("change", function () {
      document.getElementById("experience-extra").hidden = input.value !== "yes" || !input.checked;
    });
  });
  document.getElementById("no_previous_employment").addEventListener("change", function (event) {
    document.getElementById("previous-fields").hidden = event.target.checked;
  });
  function showStep() {
    document.querySelectorAll("[data-step]").forEach(function (section) {
      section.hidden = Number(section.getAttribute("data-step")) !== step;
    });
    document.getElementById("step-label").textContent = "Step " + step + " of " + total;
    document.getElementById("back").hidden = step === 1;
    document.getElementById("next").hidden = step === total;
    document.getElementById("submit").hidden = step !== total;
    if (step === total) renderReview();
    window.scrollTo(0, 0);
  }
  function value(name) {
    var el = form.elements[name];
    if (!el) return "";
    if (el.type === "radio") {
      var picked = form.querySelector("input[name='" + name + "']:checked");
      return picked ? picked.value : "";
    }
    if (el.type === "checkbox") return el.checked;
    return el.value || "";
  }
  function yes(name) { return value(name) === "yes"; }
  var authLabels = { citizen: "Canadian Citizen", permanent_resident: "Permanent Resident", work_permit: "Valid Work Permit", study_permit: "Study Permit with work authorization", other: "Other authorization", sponsorship: "Requires sponsorship", unspecified: "Prefer not to specify" };
  function renderReview() {
    var days = collectAvailability();
    var dayLine = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"].map(function (day) {
      var slots = days[day] || [];
      return slots.length ? day.slice(0, 3) + " " + slots.join("/") : "";
    }).filter(Boolean).join(", ");
    document.getElementById("review").innerHTML =
      card("Position", [["Role", selectedJob ? selectedJob.title : value("job_id")], ["Job ID", selectedJob ? selectedJob.job_id : value("job_id")], ["Location", selectedJob ? selectedJob.location : ""], ["Type", selectedJob ? selectedJob.type : value("employment_preference")]]) +
      card("Personal", [["Name", value("first_name") + " " + value("last_name")], ["Email", value("email")], ["Phone", value("phone")], ["City", value("city") + ", " + value("province")]]) +
      card("Availability", [["Start", value("start_date") || "Not set"], ["Preference", value("employment_preference")], ["Weekends", value("weekends") || "Not answered"], ["Evenings", value("evenings") || "Not answered"], ["Days", dayLine || "No days selected"]], true) +
      card("Experience", [["Cleaning experience", yes("has_cleaning_experience") ? (value("years_experience") || "Yes") : "No"], ["Details", value("experience_description") || "—"]]) +
      card("Transportation", [["Driver's licence", value("drivers_license") || "Not answered"], ["Transportation", value("reliable_transportation") || "Not answered"], ["Travel", value("willing_to_travel") || "Not answered"]]) +
      card("Work authorization", [["Authorization", authLabels[value("work_authorization")] || value("work_authorization") || "Not answered"], ["Authorized to work", value("eligible_to_work") === "yes" ? "Yes" : value("eligible_to_work") === "no" ? "No" : "Not answered"]]) +
      card("Documents", fileRows(), true);
  }
  function card(title, pairs, wide) {
    return "<section class='review-card" + (wide ? " wide" : "") + "'><h3>" + title + "</h3><dl>" + pairs.filter(function (pair) { return pair[1]; }).map(function (pair) {
      return "<div><dt>" + escapeHtml(pair[0]) + "</dt><dd>" + escapeHtml(pair[1]) + "</dd></div>";
    }).join("") + "</dl></section>";
  }
  function collectAvailability() {
    var map = {};
    document.querySelectorAll("#days input:checked").forEach(function (input) {
      var day = input.getAttribute("data-day");
      map[day] = map[day] || [];
      map[day].push(input.getAttribute("data-part"));
    });
    return map;
  }
  function escapeHtml(text) {
    return String(text).replace(/[&<>"']/g, function (ch) {
      return ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[ch];
    });
  }
  function payload() {
    return {
      job_id: value("job_id"),
      first_name: value("first_name"),
      last_name: value("last_name"),
      email: value("email"),
      phone: value("phone"),
      street_address: value("street_address"),
      city: value("city"),
      province: value("province"),
      postal_code: value("postal_code"),
      start_date: value("start_date"),
      employment_preference: value("employment_preference"),
      weekends: yes("weekends"),
      evenings: yes("evenings"),
      availability: collectAvailability(),
      has_cleaning_experience: yes("has_cleaning_experience"),
      years_experience: value("years_experience"),
      experience_description: value("experience_description"),
      no_previous_employment: !!value("no_previous_employment"),
      previous_employer: value("previous_employer"),
      previous_position: value("previous_position"),
      previous_employment_length: value("previous_employment_length"),
      drivers_license: yes("drivers_license"),
      reliable_transportation: yes("reliable_transportation"),
      willing_to_travel: yes("willing_to_travel"),
      eligible_to_work: value("eligible_to_work") === "" ? null : yes("eligible_to_work"),
      work_authorization: value("work_authorization"),
      work_permit_type: value("work_permit_type"),
      work_permit_expiry: value("work_permit_expiry"),
      study_permit_expiry: value("study_permit_expiry"),
      authorization_notes: value("authorization_notes"),
      drivers_license_expiry: value("drivers_license_expiry"),
      able_to_perform_duties: value("able_to_perform_duties") === "" ? null : yes("able_to_perform_duties"),
      cover_letter: value("cover_letter"),
      documents: { certificates: collectMeta("certificate"), additional: collectMeta("additional") },
      certified: !!value("certified"),
      consent_contact: !!value("consent_contact"),
      company_website: value("company_website"),
      references: [1, 2].map(function (n) {
        return { name: value("ref" + n + "_name"), relationship: value("ref" + n + "_relationship"), phone: value("ref" + n + "_phone"), email: value("ref" + n + "_email") };
      })
    };
  }
  function collectMeta(prefix) {
    var map = {};
    document.querySelectorAll("[data-" + prefix + "-slot]").forEach(function (box) {
      var slot = box.getAttribute("data-" + prefix + "-slot");
      map[slot] = {
        certificate_type: (box.querySelector("[data-kind]") || {}).value || "",
        document_type: (box.querySelector("[data-doc-type]") || {}).value || "other",
        name: (box.querySelector("[data-name]") || {}).value || "",
        expiry: (box.querySelector("[data-expiry]") || {}).value || ""
      };
    });
    return map;
  }
  function fileRows() {
    var labels = { resume: "Resume", cover_letter_file: "Cover letter", work_permit: "Work permit", study_permit: "Study permit", drivers_license_file: "Driver's licence" };
    var rows = Object.keys(labels).map(function (name) {
      var input = form.elements[name];
      return input && input.files[0] ? [labels[name], input.files[0].name] : null;
    }).filter(Boolean);
    document.querySelectorAll("[data-cert-file], [data-extra-file]").forEach(function (input) {
      if (input.files[0]) rows.push(["Supporting file", input.files[0].name]);
    });
    if (!rows.length && value("cover_letter")) rows.push(["Cover letter", "Written in the form"]);
    return rows.length ? rows : [["Files", "None uploaded"]];
  }
  function markFile(input) {
    var status = form.querySelector(".file-status[data-for='" + input.id + "']");
    if (status) status.textContent = input.files[0] ? input.files[0].name + " uploaded" : "";
  }
  function showError(message) {
    var box = document.getElementById("form-error");
    box.hidden = !message;
    box.textContent = message || "";
  }
  document.getElementById("next").addEventListener("click", function () {
    var section = document.querySelector("[data-step='" + step + "']");
    var invalid = section.querySelector(":invalid");
    if (invalid) { invalid.reportValidity(); return; }
    if (step === 1 && !value("job_id")) { showError("Choose a position before continuing."); return; }
    showError("");
    step += 1;
    showStep();
  });
  document.getElementById("back").addEventListener("click", function () {
    step = Math.max(1, step - 1);
    showStep();
  });
  form.addEventListener("submit", function (event) {
    event.preventDefault();
    showError("");
    var tooBig = Array.prototype.some.call(form.querySelectorAll("input[type=file]"), function (input) {
      return input.files[0] && input.files[0].size > 10 * 1024 * 1024;
    });
    if (tooBig) { showError("Each file must be 10 MB or smaller."); return; }
    var body = new FormData();
    body.append("application", JSON.stringify(payload()));
    ["resume", "cover_letter_file", "work_permit", "study_permit", "drivers_license_file"].forEach(function (name) {
      var input = form.elements[name];
      if (input && input.files[0]) body.append(name, input.files[0], input.files[0].name);
    });
    form.querySelectorAll("[data-cert-file]").forEach(function (input) {
      if (input.files[0]) body.append("certificate_file_" + input.getAttribute("data-cert-file"), input.files[0], input.files[0].name);
    });
    form.querySelectorAll("[data-extra-file]").forEach(function (input) {
      if (input.files[0]) body.append("additional_file_" + input.getAttribute("data-extra-file"), input.files[0], input.files[0].name);
    });
    var button = document.getElementById("submit");
    button.disabled = true;
    fetch("/api/v1/applications", { method: "POST", body: body }).then(function (res) {
      return res.json().then(function (data) { return { ok: res.ok, data: data }; });
    }).then(function (result) {
      button.disabled = false;
      if (!result.ok) {
        showError(result.data.error || "The application could not be submitted. Your answers are still here.");
        return;
      }
      form.hidden = true;
      document.getElementById("step-label").hidden = true;
      document.getElementById("success").hidden = false;
      document.getElementById("success-copy").textContent = result.data.message;
      document.getElementById("reference").textContent = result.data.application_number;
    }).catch(function () {
      button.disabled = false;
      showError("The application could not be submitted. Your answers are still here.");
    });
  });
  var requested = new URLSearchParams(location.search).get("job");
  var fallbackJobs = [{ job_id: "JOB-1001", title: "Evening Commercial Cleaner", location: "Oakbank", employment_type_label: "Part-Time" }];
  fetch("/api/v1/jobs").then(function (res) {
    if (!res.ok) throw new Error("unavailable");
    return res.json();
  }).catch(function () {
    return { jobs: fallbackJobs };
  }).then(function (data) {
    var jobs = data.jobs || [];
    var picker = document.getElementById("job-picker");
    var select = document.getElementById("job_id");
    jobs.forEach(function (job) {
      var option = document.createElement("option");
      option.value = job.job_id;
      option.textContent = job.title + " — " + job.location;
      option.dataset.title = job.title;
      option.dataset.location = job.location;
      option.dataset.type = job.employment_type_label;
      select.appendChild(option);
    });
    if (requested && jobs.some(function (job) { return job.job_id === requested; })) {
      select.value = requested;
      picker.hidden = true;
    } else if (!requested && jobs.length) {
      picker.hidden = false;
    } else if (requested) {
      document.getElementById("applying").hidden = false;
      document.getElementById("applying").innerHTML = "<h2>This position is no longer available.</h2><p><a href='/careers.html'>View Current Opportunities</a></p>";
      form.hidden = true;
      return;
    } else {
      document.getElementById("applying").hidden = false;
      document.getElementById("applying").innerHTML = "<h2>No Open Positions Right Now</h2><p>We don't currently have any positions available.</p>";
      form.hidden = true;
      return;
    }
    function paint() {
      var option = select.selectedOptions[0];
      if (!option) return;
      selectedJob = { job_id: option.value, title: option.dataset.title, location: option.dataset.location, type: option.dataset.type };
      var box = document.getElementById("applying");
      box.hidden = false;
      box.innerHTML = "<p class='eyebrow'>Applying for</p><h2>" + escapeHtml(selectedJob.title) + "</h2><p>" + escapeHtml(selectedJob.location) + "<br>" + escapeHtml(selectedJob.type) + "</p>";
    }
    select.addEventListener("change", function () { paint(); loadRules(); });
    paint();
    loadRules();
    showStep();
  });
  function loadRules() {
    if (!value("job_id")) return;
    fetch("/api/v1/jobs/" + encodeURIComponent(value("job_id"))).then(function (res) { return res.json(); }).then(function (data) {
      jobRules = data.job || {};
      var resumeLabel = document.querySelector("#resume-field label");
      if (resumeLabel) resumeLabel.firstChild.textContent = jobRules.resume_requirement === "required" ? "Upload Resume / CV (required)" : "Upload Resume / CV";
      document.getElementById("resume-field").hidden = jobRules.resume_requirement === "not_required";
      document.getElementById("cover-file-field").hidden = jobRules.cover_letter_requirement === "not_required";
    });
  }
  document.getElementById("work_authorization").addEventListener("change", function () {
    document.getElementById("permit-fields").hidden = value("work_authorization") !== "work_permit";
    document.getElementById("permit-upload").hidden = value("work_authorization") !== "work_permit";
    document.getElementById("study-fields").hidden = value("work_authorization") !== "study_permit";
    document.getElementById("study-upload").hidden = value("work_authorization") !== "study_permit";
  });
  document.querySelectorAll("input[name='drivers_license']").forEach(function (input) {
    input.addEventListener("change", function () {
      var show = value("drivers_license") === "yes";
      document.getElementById("licence-expiry").hidden = !show;
      document.getElementById("licence-upload").hidden = !show;
    });
  });
  form.querySelectorAll("input[type=file]").forEach(function (input) {
    input.addEventListener("change", function () { markFile(input); });
  });
  document.getElementById("add-certificate").addEventListener("click", function () {
    certCount += 1;
    var box = document.createElement("div");
    box.className = "panel";
    box.setAttribute("data-certificate-slot", String(certCount));
    box.innerHTML = "<div class='field'><label>Certificate type<select data-kind><option value='whmis'>WHMIS</option><option value='first_aid'>First Aid / CPR</option><option value='food_safety'>Food Safety</option><option value='cleaning'>Cleaning Training</option><option value='floor_care'>Floor Care / Strip & Wax</option><option value='other'>Other</option></select></label></div><div class='field'><label>Certificate name<input data-name></label></div><div class='field'><label>Expiry date<input data-expiry type='date'></label></div><div class='field'><label>Upload document<input data-cert-file='" + certCount + "' type='file' accept='.pdf,.doc,.docx,.jpg,.jpeg,.png'></label></div><button class='btn btn-ghost' type='button'>Remove</button>";
    box.querySelector("button").onclick = function () { box.remove(); };
    document.getElementById("certificates").appendChild(box);
  });
  document.getElementById("add-document").addEventListener("click", function () {
    extraCount += 1;
    var box = document.createElement("div");
    box.className = "panel";
    box.setAttribute("data-additional-slot", String(extraCount));
    box.innerHTML = "<div class='field'><label>Document type<select data-doc-type><option value='certification'>Certification</option><option value='drivers_license'>Driver's licence</option><option value='reference_letter'>Reference letter</option><option value='other'>Other</option></select></label></div><div class='field'><label>Name<input data-name></label></div><div class='field'><label>Upload<input data-extra-file='" + extraCount + "' type='file' accept='.pdf,.doc,.docx,.jpg,.jpeg,.png'></label></div><button class='btn btn-ghost' type='button'>Remove</button>";
    box.querySelector("button").onclick = function () { box.remove(); };
    document.getElementById("additional-docs").appendChild(box);
  });
  showStep();
})();
