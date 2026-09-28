(function () {
  var app = document.getElementById("app");
  var employment = [["full-time", "Full-Time"], ["part-time", "Part-Time"], ["casual", "Casual"], ["temporary", "Temporary"], ["contract", "Contract"]];
  var shifts = ["morning", "day", "evening", "overnight", "flexible"];
  var payTypes = [["hourly", "Per hour"], ["salary", "Salary"], ["contract", "Contract"], ["negotiable", "Negotiable"]];
  var appStatuses = [["new", "New"], ["under_review", "Under Review"], ["shortlisted", "Shortlisted"], ["interview", "Interview"], ["offer", "Offer"], ["hired", "Hired"], ["rejected", "Rejected"], ["withdrawn", "Withdrawn"]];

  function esc(value) {
    return String(value == null ? "" : value).replace(/[&<>"']/g, function (ch) {
      return ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[ch];
    });
  }
  function api(path, options) {
    options = options || {};
    options.credentials = "same-origin";
    if (options.body && typeof options.body !== "string") {
      options.headers = Object.assign({ "Content-Type": "application/json" }, options.headers || {});
      options.body = JSON.stringify(options.body);
    }
    return fetch("/api/v1" + path, options).then(function (res) {
      var type = res.headers.get("Content-Type") || "";
      if (type.indexOf("application/json") === -1) return { ok: res.ok, status: res.status, data: null, raw: res };
      return res.json().then(function (data) { return { ok: res.ok, status: res.status, data: data }; });
    });
  }
  function shell(current, inner) {
    app.innerHTML = '<header class="top"><strong>Recruitment</strong><nav>' +
      link("/admin/recruitment", "Overview", current) +
      link("/admin/recruitment/jobs", "Jobs", current) +
      link("/admin/recruitment/applications", "Applications <span id='nav-apps'></span>", current) +
      link("/admin/recruitment/inquiries", "Inquiries <span id='nav-asks'></span>", current) +
      link("/admin/recruitment/quotes", "Quotes <span id='nav-quotes'></span>", current) +
      link("/admin/recruitment/locations", "Locations", current) +
      link("/admin/recruitment/settings", "Settings", current) +
      '</nav><button class="ghost" id="logout" type="button">Sign out</button></header><main class="page">' + inner + "</main>";
    api("/admin/summary").then(function (res) {
      var summary = (res.data && res.data.summary) || {};
      var apps = document.getElementById("nav-apps");
      var asks = document.getElementById("nav-asks");
      var quotes = document.getElementById("nav-quotes");
      if (apps && summary.new_applications) apps.textContent = "(" + summary.new_applications + ")";
      if (asks && summary.new_inquiries) asks.textContent = "(" + summary.new_inquiries + ")";
      if (quotes && summary.new_quotes) quotes.textContent = "(" + summary.new_quotes + ")";
    });
    document.getElementById("logout").onclick = function () {
      api("/admin/logout", { method: "POST" }).then(function () { location.href = "/admin"; });
    };
    app.querySelectorAll("a[data-nav]").forEach(function (anchor) {
      anchor.addEventListener("click", function (event) {
        event.preventDefault();
        go(anchor.getAttribute("href"));
      });
    });
  }
  function link(href, label, current) {
    var on = current === href ? ' aria-current="page"' : "";
    return '<a data-nav href="' + href + '"' + on + ">" + label + "</a>";
  }
  function go(path) {
    history.pushState({}, "", path);
    render();
  }
  function loginView() {
    app.innerHTML = '<div class="login-screen"><form class="login" id="login"><img src="/images/logo.png" alt="Master Commercial Cleaning"><span class="eyebrow">Recruitment</span><h1>Sign in</h1><p class="lede">Manage jobs, applications, and questions from one place.</p><label>Username<input name="username" autocomplete="username" required></label><label>Password<input name="password" type="password" autocomplete="current-password" required></label><p class="error" id="err" hidden></p><button type="submit">Sign in</button></form></div>';
    document.getElementById("login").onsubmit = function (event) {
      event.preventDefault();
      var data = Object.fromEntries(new FormData(event.target).entries());
      var err = document.getElementById("err");
      err.hidden = true;
      api("/admin/login", { method: "POST", body: data }).then(function (res) {
        if (!res.ok) {
          err.hidden = false;
          err.textContent = (res.data && res.data.error) || "Those credentials were not recognized.";
          return;
        }
        go("/admin/recruitment");
      }).catch(function () {
        err.hidden = false;
        err.textContent = "Sign in could not be completed. Please try again.";
      });
    };
  }
  function jobsView() {
    api("/admin/jobs").then(function (res) {
      var rows = ((res.data && res.data.jobs) || []).map(function (job) {
        var rate = job.views ? job.conversion_rate + "%" : "0%";
        return "<tr><td>" + esc(job.job_id) + "</td><td><a data-nav href='/admin/recruitment/jobs/" + esc(job.job_id) + "'>" + esc(job.title) + "</a><div>" + esc(job.views) + " views · " + esc(rate) + "</div></td><td>" + esc(job.location) + "</td><td>" + esc(job.employment_type_label) + "</td><td>" + esc(job.shift) + "</td><td><a data-nav href='/admin/recruitment/applications?job=" + esc(job.job_id) + "'>" + esc(job.applications) + "</a></td><td><span class='badge " + esc(job.status) + "'>" + esc(job.status) + "</span></td><td>" + esc((job.published_at || "").slice(0, 10)) + "</td><td>" + esc(job.closing_date) + "</td><td class='row-actions'>" + actions(job) + "</td></tr>";
      }).join("");
      shell("/admin/recruitment/jobs", "<h1>Jobs</h1><p><a class='btn' data-nav href='/admin/recruitment/jobs/new'>Create Job</a></p><table><thead><tr><th>Job ID</th><th>Job title</th><th>Location</th><th>Employment type</th><th>Shift</th><th>Applications</th><th>Status</th><th>Published</th><th>Closing</th><th>Actions</th></tr></thead><tbody>" + (rows || "<tr><td colspan='10'>No jobs yet.</td></tr>") + "</tbody></table>");
      bindJobActions();
    });
  }
  function actions(job) {
    return "<button data-act='view' data-id='" + esc(job.job_id) + "'>View</button><button data-act='edit' data-id='" + esc(job.job_id) + "'>Edit</button><button data-act='duplicate' data-id='" + esc(job.job_id) + "'>Duplicate</button><button data-act='publish' data-id='" + esc(job.job_id) + "'>Publish</button><button data-act='close' data-id='" + esc(job.job_id) + "'>Close</button><button class='ghost' data-act='archive' data-id='" + esc(job.job_id) + "'>Archive</button>";
  }
  function bindJobActions() {
    app.querySelectorAll("[data-act]").forEach(function (button) {
      button.onclick = function () {
        var id = button.getAttribute("data-id");
        var act = button.getAttribute("data-act");
        if (act === "view" || act === "edit") { go("/admin/recruitment/jobs/" + id); return; }
        api("/admin/jobs/" + id + "/" + act, { method: "POST" }).then(function (res) {
          if (act === "duplicate" && res.ok) go("/admin/recruitment/jobs/" + res.data.job.job_id);
          else jobsView();
        });
      };
    });
  }
  function jobForm(job) {
    var locations = [];
    api("/admin/locations").then(function (res) {
      locations = (res.data && res.data.locations) || [];
      var current = "/admin/recruitment/jobs";
      shell(current, "<h1>" + (job ? "Edit job" : "Create Job") + "</h1><form id='job-form'>" + formFields(job, locations) + "<p class='error' id='err' hidden></p><button type='submit'>" + (job ? "Save" : "Create draft") + "</button></form>");
      document.getElementById("job-form").onsubmit = function (event) {
        event.preventDefault();
        var data = readJobForm(event.target);
        var path = job ? "/admin/jobs/" + job.job_id : "/admin/jobs";
        api(path, { method: job ? "PATCH" : "POST", body: data }).then(function (result) {
          if (!result.ok) {
            document.getElementById("err").hidden = false;
            document.getElementById("err").textContent = (result.data && result.data.error) || "Could not save.";
            return;
          }
          go("/admin/recruitment/jobs/" + result.data.job.job_id);
        });
      };
    });
  }
  function formFields(job, locations) {
    job = job || {};
    return "<div class='grid'><label>Job title<input name='title' required value='" + esc(job.title) + "'></label><label>Location<select name='location_id'>" + locations.filter(function (loc) { return loc.active || loc.id === job.location_id; }).map(function (loc) { return "<option value='" + loc.id + "'" + (loc.id === job.location_id ? " selected" : "") + ">" + esc(loc.name) + "</option>"; }).join("") + "</select></label><label>Employment type<select name='employment_type'>" + employment.map(function (item) { return "<option value='" + item[0] + "'" + (job.employment_type === item[0] ? " selected" : "") + ">" + item[1] + "</option>"; }).join("") + "</select></label><label>Shift<select name='shift_type'><option value=''>Custom / none</option>" + shifts.map(function (item) { return "<option" + (job.shift_type === item ? " selected" : "") + ">" + item + "</option>"; }).join("") + "</select></label></div><label>Shift description<input name='shift_description' placeholder='8:00 PM – 12:00 AM' value='" + esc(job.shift_description) + "'></label><div class='grid'><label>Pay amount<input name='salary_min' inputmode='decimal' value='" + esc(job.salary_min == null ? "" : job.salary_min) + "'></label><label>Pay maximum<input name='salary_max' inputmode='decimal' value='" + esc(job.salary_max == null ? "" : job.salary_max) + "'></label><label>Pay type<select name='pay_type'><option value=''>None</option>" + payTypes.map(function (item) { return "<option value='" + item[0] + "'" + (job.pay_type === item[0] ? " selected" : "") + ">" + item[1] + "</option>"; }).join("") + "</select></label><label>Hide pay<select name='show_pay'><option value='false'" + (job.show_pay ? "" : " selected") + ">Hide pay</option><option value='true'" + (job.show_pay ? " selected" : "") + ">Show pay</option></select></label><label>Positions<input name='positions_available' inputmode='numeric' value='" + esc(job.positions_available == null ? "" : job.positions_available) + "'></label><label>Start date<input type='date' name='start_date' value='" + esc(job.start_date) + "'></label><label>Closing date<input type='date' name='closing_date' value='" + esc(job.closing_date) + "'></label><label>Accepting applications<select name='accepting_applications'><option value='true'" + (job.accepting_applications === false ? "" : " selected") + ">On</option><option value='false'" + (job.accepting_applications === false ? " selected" : "") + ">Off</option></select></label></div><label>Job description<textarea name='description' rows='8'>" + esc(job.description) + "</textarea></label><label>Requirements<textarea name='requirements' rows='6'>" + esc(job.requirements) + "</textarea></label><label>Resume<select name='resume_requirement'><option value='optional'>Resume optional</option><option value='required'" + (job.resume_requirement === "required" ? " selected" : "") + ">Resume required</option><option value='not_required'" + (job.resume_requirement === "not_required" ? " selected" : "") + ">Resume not required</option></select></label><label>Cover letter<select name='cover_letter_requirement'><option value='optional'>Cover letter optional</option><option value='required'" + (job.cover_letter_requirement === "required" || job.require_cover_letter ? " selected" : "") + ">Cover letter required</option><option value='not_required'" + (job.cover_letter_requirement === "not_required" ? " selected" : "") + ">Cover letter not required</option></select></label><label>Work permit upload<select name='work_permit_requirement'><option value='optional'>Optional during application</option><option value='required'" + (job.work_permit_requirement === "required" ? " selected" : "") + ">Required during application</option><option value='later'" + (job.work_permit_requirement === "later" ? " selected" : "") + ">Requested later</option></select></label><label>Driver's licence required<select name='drivers_license_required'><option value='false'>No</option><option value='true'" + (job.drivers_license_required ? " selected" : "") + ">Yes</option></select></label><label>WHMIS required<select name='whmis_required'><option value='false'>No</option><option value='true'" + (job.whmis_required ? " selected" : "") + ">Yes</option></select></label><label>First Aid required<select name='first_aid_required'><option value='false'>No</option><option value='true'" + (job.first_aid_required ? " selected" : "") + ">Yes</option></select></label><label>Internal notes<textarea name='internal_notes' rows='3'>" + esc(job.internal_notes) + "</textarea></label>";
  }
  function readJobForm(form) {
    var data = Object.fromEntries(new FormData(form).entries());
    ["show_pay", "accepting_applications", "require_cover_letter", "drivers_license_required", "whmis_required", "first_aid_required"].forEach(function (key) { data[key] = data[key] === "true"; });
    return data;
  }
  function jobDetail(id) {
    api("/admin/jobs/" + id).then(function (res) {
      if (!res.ok) { shell("/admin/recruitment/jobs", "<h1>Job not found</h1>"); return; }
      var job = res.data.job;
      shell("/admin/recruitment/jobs", "<h1>" + esc(job.title) + "</h1><p>" + esc(job.job_id) + " · <span class='badge " + esc(job.status) + "'>" + esc(job.status) + "</span></p><p>" + esc(job.views) + " views · " + esc(job.applications) + " applications · " + esc(job.conversion_rate) + "% application rate</p><div class='row-actions'>" + actions(job) + "</div><div id='editor'></div>");
      bindJobActions();
      var editor = document.getElementById("editor");
      api("/admin/locations").then(function (locs) {
        editor.innerHTML = "<form id='job-form'>" + formFields(job, (locs.data && locs.data.locations) || []) + "<button type='submit'>Save changes</button></form>";
        document.getElementById("job-form").onsubmit = function (event) {
          event.preventDefault();
          api("/admin/jobs/" + id, { method: "PATCH", body: readJobForm(event.target) }).then(function () { jobDetail(id); });
        };
      });
    });
  }
  function applicationsView() {
    var params = new URLSearchParams(location.search);
    var query = params.toString();
    Promise.all([api("/admin/applications" + (query ? "?" + query : "")), api("/admin/jobs"), api("/admin/locations")]).then(function (results) {
      var apps = (results[0].data && results[0].data.applications) || [];
      var jobs = (results[1].data && results[1].data.jobs) || [];
      var locations = (results[2].data && results[2].data.locations) || [];
      var rows = apps.map(function (item) {
        return "<tr><td><a data-nav href='/admin/recruitment/applications/" + esc(item.application_number) + "'>" + esc(item.applicant) + "</a><div>" + esc(item.application_number) + "</div></td><td>" + esc(item.job_title) + "</td><td>" + esc(item.location) + "</td><td>" + esc(item.phone) + "</td><td>" + esc(item.email) + "</td><td>" + esc((item.applied_at || "").slice(0, 10)) + "</td><td><span class='badge " + esc(item.status) + "'>" + esc(item.status_label) + "</span></td></tr>";
      }).join("");
      shell("/admin/recruitment/applications", "<h1>Applications</h1><form class='filters' id='filters'><input name='q' placeholder='Name, email, phone, or application ID' value='" + esc(params.get("q") || "") + "'><select name='job'><option value=''>All jobs</option>" + jobs.map(function (job) { return "<option value='" + esc(job.job_id) + "'" + (params.get("job") === job.job_id ? " selected" : "") + ">" + esc(job.title) + "</option>"; }).join("") + "</select><select name='location'><option value=''>All locations</option>" + locations.map(function (loc) { return "<option" + (params.get("location") === loc.name ? " selected" : "") + ">" + esc(loc.name) + "</option>"; }).join("") + "</select><select name='status'><option value=''>All statuses</option>" + appStatuses.map(function (item) { return "<option value='" + item[0] + "'" + (params.get("status") === item[0] ? " selected" : "") + ">" + item[1] + "</option>"; }).join("") + "</select><select name='type'><option value=''>All types</option>" + employment.map(function (item) { return "<option value='" + item[0] + "'" + (params.get("type") === item[0] ? " selected" : "") + ">" + item[1] + "</option>"; }).join("") + "</select><input type='date' name='date' value='" + esc(params.get("date") || "") + "'><button type='submit'>Filter</button></form><table><thead><tr><th>Applicant</th><th>Job</th><th>Location</th><th>Phone</th><th>Email</th><th>Applied</th><th>Status</th></tr></thead><tbody>" + (rows || "<tr><td colspan='7'>No applications.</td></tr>") + "</tbody></table>");
      document.getElementById("filters").onsubmit = function (event) {
        event.preventDefault();
        var data = new FormData(event.target);
        var next = new URLSearchParams();
        data.forEach(function (value, key) { if (value) next.set(key, value); });
        go("/admin/recruitment/applications" + (next.toString() ? "?" + next.toString() : ""));
      };
    });
  }
  function yn(value) { return value ? "Yes" : "No"; }
  function availabilityBlock(map) {
    var days = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"];
    return "<div class='avail'>" + days.map(function (day) {
      var slots = (map && map[day]) || [];
      return "<div><strong>" + day + "</strong>" + esc(slots.length ? slots.join(", ") : "Not selected") + "</div>";
    }).join("") + "</div>";
  }
  function applicantPage(item) {
    var person = item.applicant;
    var auth = { citizen: "Canadian Citizen", permanent_resident: "Permanent Resident", work_permit: "Valid Work Permit", study_permit: "Study permit with work authorization", other: "Other", sponsorship: "Requires sponsorship", unspecified: "Prefer not to specify" };
    var docs = (item.documents || []).map(function (doc) {
      return "<tr><td>" + esc(doc.label) + "</td><td>" + esc(doc.filename || "Not uploaded") + "</td><td>" + esc(doc.expiry_date || "—") + (doc.expiry_label ? " <span class='badge'>" + esc(doc.expiry_label) + "</span>" : "") + "</td><td><select data-verify='" + doc.id + "'>" + ["uploaded", "needs_review", "verified", "requested", "expired"].map(function (status) { return "<option" + (doc.verification_status === status ? " selected" : "") + ">" + status + "</option>"; }).join("") + "</select></td><td>" + (doc.has_file ? "<button type='button' data-doc='" + doc.id + "'>View</button>" : "") + "</td></tr>";
    }).join("");
    return "<div class='detail-head'><h1>" + esc(person.first_name + " " + person.last_name) + "</h1><p>" + esc(item.application_number) + " · " + esc(item.job.title) + " · " + esc(item.job.location) + "</p><label>Status<select id='status'>" + appStatuses.map(function (pair) { return "<option value='" + pair[0] + "'" + (item.status === pair[0] ? " selected" : "") + ">" + pair[1] + "</option>"; }).join("") + "</select></label></div><div class='detail-layout'><div><section class='card'><h2>Applicant</h2><dl class='kv'><dt>Email</dt><dd>" + esc(person.email) + "</dd><dt>Phone</dt><dd>" + esc(person.phone) + "</dd><dt>Address</dt><dd>" + esc([person.street_address, person.city, person.province, person.postal_code].filter(Boolean).join(", ")) + "</dd></dl></section><section class='card'><h2>Position</h2><dl class='kv'><dt>Job ID</dt><dd>" + esc(item.job.job_id) + "</dd><dt>Title</dt><dd>" + esc(item.job.title) + "</dd><dt>Location</dt><dd>" + esc(item.job.location) + "</dd><dt>Type</dt><dd>" + esc(item.job.employment_type_label || "") + "</dd></dl></section><section class='card'><h2>Availability</h2>" + availabilityBlock(item.availability) + "<dl class='kv' style='margin-top:12px'><dt>Start</dt><dd>" + esc(item.start_date || "Not set") + "</dd><dt>Preference</dt><dd>" + esc(item.employment_preference || "—") + "</dd><dt>Weekends</dt><dd>" + yn(item.weekends) + "</dd><dt>Evenings</dt><dd>" + yn(item.evenings) + "</dd></dl></section><section class='card'><h2>Experience</h2><p>" + (item.has_cleaning_experience ? esc(item.years_experience || "Yes") : "No professional cleaning experience") + "</p><p>" + esc(item.experience_description || "") + "</p><p>" + (item.no_previous_employment ? "No previous employment" : esc([item.previous_employer, item.previous_position, item.previous_employment_length].filter(Boolean).join(" · ")) || "Previous employment not provided") + "</p></section></div><div><section class='card'><h2>Work authorization</h2><dl class='kv'><dt>Authorized</dt><dd>" + yn(item.eligible_to_work) + "</dd><dt>Status</dt><dd>" + esc(auth[item.work_authorization] || item.work_authorization || "—") + "</dd><dt>Permit</dt><dd>" + esc(item.work_permit_type || "—") + "</dd><dt>Expiry</dt><dd>" + esc(item.work_permit_expiry || item.study_permit_expiry || "—") + " " + esc(item.work_permit_expiry_label || "") + "</dd></dl><p>" + esc(item.authorization_notes || "") + "</p></section><section class='card'><h2>Transportation</h2><dl class='kv'><dt>Licence</dt><dd>" + yn(item.drivers_license) + "</dd><dt>Transportation</dt><dd>" + yn(item.reliable_transportation) + "</dd><dt>Travel</dt><dd>" + yn(item.willing_to_travel) + "</dd></dl></section><section class='card'><h2>Cover letter</h2><p>" + esc(item.cover_letter || "None provided") + "</p></section><section class='card'><h2>References</h2>" + ((item.references || []).map(function (ref) { return "<p><strong>" + esc(ref.name) + "</strong><br>" + esc(ref.relationship) + "<br>" + esc(ref.phone) + " · " + esc(ref.email) + "</p>"; }).join("") || "<p>None provided</p>") + "</section></div></div><section class='card'><h2>Documents</h2><table><thead><tr><th>Type</th><th>File</th><th>Expiry</th><th>Status</th><th></th></tr></thead><tbody>" + (docs || "<tr><td colspan='5'>No documents uploaded.</td></tr>") + "</tbody></table><h3>Request document</h3><form id='doc-request'><div class='grid'><label>Document type<select name='document_type'><option value='work_permit'>Work Permit</option><option value='drivers_license'>Driver's Licence</option><option value='certification'>WHMIS / Certificate</option><option value='reference_letter'>Reference Letter</option><option value='other'>Other</option></select></label><label>Due date<input type='date' name='due_date'></label></div><label>Message<textarea name='message'></textarea></label><button type='submit'>Request Document</button><p id='doc-link'></p></form></section><section class='card'><h2>Internal notes</h2><div id='notes'>" + item.notes.map(function (note) { return "<div class='note'><strong>" + esc(note.created_at) + "</strong><p>" + esc(note.note) + "</p></div>"; }).join("") + "</div><form id='note'><label>Add a private note<textarea name='note' required></textarea></label><button type='submit'>Save note</button></form></section>";
  }
  function dashboardView() {
    api("/admin/summary").then(function (res) {
      if (!res.ok || !res.data || !res.data.summary) {
        shell("/admin/recruitment", "<h1>Overview</h1><p class='error'>The overview could not be loaded. Please refresh the page.</p>");
        return;
      }
      var summary = res.data.summary;
      var alert = "";
      if (summary.new_applications || summary.new_inquiries || summary.new_quotes) {
        var bits = [];
        if (summary.new_applications) bits.push(summary.new_applications + " new application" + (summary.new_applications === 1 ? "" : "s"));
        if (summary.new_inquiries) bits.push(summary.new_inquiries + " new " + (summary.new_inquiries === 1 ? "question" : "questions"));
        if (summary.new_quotes) bits.push(summary.new_quotes + " new quote " + (summary.new_quotes === 1 ? "request" : "requests"));
        alert = "<div class='alert'><strong>Needs attention.</strong> " + bits.join(" and ") + ".</div>";
      }
      var apps = summary.applications.map(function (item) {
        return "<tr><td><a data-nav href='/admin/recruitment/applications/" + esc(item.application_number) + "'>" + esc(item.applicant) + "</a></td><td>" + esc(item.title) + "</td><td><span class='badge " + esc(item.status) + "'>" + esc(item.status) + "</span></td><td>" + esc((item.submitted_at || "").slice(0, 10)) + "</td></tr>";
      }).join("");
      var asks = summary.inquiries.map(function (item) {
        return "<tr class='clickable' data-open-inquiry='" + item.id + "'><td>" + esc(item.name) + "</td><td>" + esc(item.job_public_id || "General") + "</td><td>" + esc((item.message || "").slice(0, 80)) + (item.message && item.message.length > 80 ? "…" : "") + "</td><td>" + esc(item.status) + "</td></tr>";
      }).join("");
      var quoteRows = (summary.quotes || []).map(function (item) {
        return "<tr class='clickable' data-open-quote='" + item.id + "'><td>" + esc(item.name) + "</td><td>" + esc(item.business_name || "") + "</td><td>" + esc(item.city || "") + "</td><td>" + esc(item.service || "") + "</td><td>" + esc(item.status) + "</td></tr>";
      }).join("");
      shell("/admin/recruitment", alert + "<h1>Overview</h1><div class='stats'><a class='stat' data-nav href='/admin/recruitment/applications'><strong>" + summary.new_applications + "</strong><span>New applications</span></a><a class='stat' data-nav href='/admin/recruitment/quotes'><strong>" + (summary.new_quotes || 0) + "</strong><span>New quote requests</span></a><a class='stat' data-nav href='/admin/recruitment/inquiries'><strong>" + summary.new_inquiries + "</strong><span>New questions</span></a><a class='stat' data-nav href='/admin/recruitment/jobs'><strong>" + summary.open_jobs + "</strong><span>Open jobs</span></a></div><h2>Latest quote requests</h2><table><thead><tr><th>Name</th><th>Business</th><th>City</th><th>Service</th><th>Status</th></tr></thead><tbody>" + (quoteRows || "<tr><td colspan='5'>No quote requests yet.</td></tr>") + "</tbody></table><h2>Latest applications</h2><table><thead><tr><th>Applicant</th><th>Job</th><th>Status</th><th>Submitted</th></tr></thead><tbody>" + (apps || "<tr><td colspan='4'>No applications yet.</td></tr>") + "</tbody></table><h2>Latest questions</h2><table><thead><tr><th>Name</th><th>Position</th><th>Question</th><th>Status</th></tr></thead><tbody>" + (asks || "<tr><td colspan='4'>No questions yet.</td></tr>") + "</tbody></table>");
      bindInquiryRows(summary.inquiries || []);
      app.querySelectorAll("[data-open-quote]").forEach(function (row) {
        row.onclick = function () { go("/admin/recruitment/quotes"); };
      });
    });
  }
  function bindInquiryRows(items) {
    var byId = {};
    items.forEach(function (item) { byId[String(item.id)] = item; });
    app.querySelectorAll("[data-open-inquiry]").forEach(function (row) {
      row.onclick = function (event) {
        if (event.target.closest("select")) return;
        openInquiry(byId[row.getAttribute("data-open-inquiry")]);
      };
    });
  }
  function openInquiry(item) {
    if (!item) return;
    var existing = document.getElementById("inquiry-modal");
    if (existing) existing.remove();
    var file = item.attachment_name ? "<p><a href='/api/v1/admin/inquiries/" + item.id + "/attachment' target='_blank' rel='noopener'>Open attachment: " + esc(item.attachment_name) + "</a></p>" : "<p>No attachment.</p>";
    var modal = document.createElement("div");
    modal.id = "inquiry-modal";
    modal.className = "modal";
    modal.innerHTML = "<div class='modal-card' role='dialog' aria-modal='true'><h2>" + esc(item.name) + "</h2><p>" + esc(item.email) + (item.phone ? " · " + esc(item.phone) : "") + "</p><p><strong>" + esc(item.job_public_id || "General question") + "</strong> · " + esc((item.created_at || "").slice(0, 10)) + "</p><p>" + esc(item.message || "") + "</p>" + file + "<button class='btn' type='button' id='close-inquiry'>Close</button></div>";
    document.body.appendChild(modal);
    modal.onclick = function (event) { if (event.target === modal) modal.remove(); };
    document.getElementById("close-inquiry").onclick = function () { modal.remove(); };
  }
  function inquiriesView() {
    api("/admin/inquiries").then(function (res) {
      var items = (res.data && res.data.inquiries) || [];
      var rows = items.map(function (item) {
        var preview = (item.message || "").slice(0, 90);
        return "<tr class='clickable' data-open-inquiry='" + item.id + "'><td>" + esc(item.name) + "<div>" + esc(item.email) + "</div></td><td>" + esc(item.phone || "") + "</td><td>" + esc(item.job_public_id || "General") + "</td><td>" + esc(preview) + (item.message && item.message.length > 90 ? "…" : "") + (item.attachment_name ? " <span class='badge'>File</span>" : "") + "</td><td>" + esc((item.created_at || "").slice(0, 10)) + "</td><td><select data-inquiry='" + item.id + "'><option value='new'" + (item.status === "new" ? " selected" : "") + ">New</option><option value='read'" + (item.status === "read" ? " selected" : "") + ">Read</option><option value='closed'" + (item.status === "closed" ? " selected" : "") + ">Closed</option></select></td></tr>";
      }).join("");
      shell("/admin/recruitment/inquiries", "<h1>Questions</h1><p>Click a question to read the full message and any attachment.</p><table class='questions'><thead><tr><th>Name</th><th>Phone</th><th>Position</th><th>Question</th><th>Date</th><th>Status</th></tr></thead><tbody>" + (rows || "<tr><td colspan='6'>No questions yet.</td></tr>") + "</tbody></table>");
      bindInquiryRows(items);
      app.querySelectorAll("[data-inquiry]").forEach(function (select) {
        select.onclick = function (event) { event.stopPropagation(); };
        select.onchange = function () {
          api("/admin/inquiries/" + select.getAttribute("data-inquiry"), { method: "PATCH", body: { status: select.value } });
        };
      });
    });
  }
  function quotesView() {
    api("/admin/quotes").then(function (res) {
      var items = (res.data && res.data.quotes) || [];
      var rows = items.map(function (item) {
        var preview = (item.message || "").slice(0, 90);
        return "<tr class='clickable' data-open-quote='" + item.id + "'><td>" + esc(item.name) + "<div>" + esc(item.email) + "</div></td><td>" + esc(item.business_name || "") + "</td><td>" + esc(item.city || "") + "</td><td>" + esc(preview) + (item.message && item.message.length > 90 ? "…" : "") + "</td><td>" + esc((item.created_at || "").slice(0, 10)) + "</td><td><select data-quote='" + item.id + "'><option value='new'" + (item.status === "new" ? " selected" : "") + ">New</option><option value='read'" + (item.status === "read" ? " selected" : "") + ">Read</option><option value='closed'" + (item.status === "closed" ? " selected" : "") + ">Closed</option></select></td></tr>";
      }).join("");
      shell("/admin/recruitment/quotes", "<h1>Quote requests</h1><p>Click a request to read the full brief, photos, and video. These are also emailed when mail is connected.</p><table class='questions'><thead><tr><th>Name</th><th>Business</th><th>City</th><th>Brief</th><th>Date</th><th>Status</th></tr></thead><tbody>" + (rows || "<tr><td colspan='6'>No quote requests yet.</td></tr>") + "</tbody></table>");
      var byId = {};
      items.forEach(function (item) { byId[String(item.id)] = item; });
      app.querySelectorAll("[data-open-quote]").forEach(function (row) {
        row.onclick = function (event) {
          if (event.target.closest("select")) return;
          openQuote(byId[row.getAttribute("data-open-quote")]);
        };
      });
      app.querySelectorAll("[data-quote]").forEach(function (select) {
        select.onclick = function (event) { event.stopPropagation(); };
        select.onchange = function () {
          api("/admin/quotes/" + select.getAttribute("data-quote"), { method: "PATCH", body: { status: select.value } });
        };
      });
    });
  }
  function openQuote(item) {
    if (!item) return;
    var existing = document.getElementById("inquiry-modal");
    if (existing) existing.remove();
    var files = (item.files || []).map(function (file) {
      return "<p><a href='/api/v1/admin/quotes/" + item.id + "/files/" + file.id + "' target='_blank' rel='noopener'>" + esc(file.kind === "video" ? "Watch video: " : "Open photo: ") + esc(file.filename) + "</a>" + (file.note ? "<br>" + esc(file.note) : "") + "</p>";
    }).join("") || "<p>No photos or video.</p>";
    var modal = document.createElement("div");
    modal.id = "inquiry-modal";
    modal.className = "modal";
    modal.innerHTML = "<div class='modal-card' role='dialog' aria-modal='true'><h2>" + esc(item.name) + "</h2><p>" + esc(item.email) + (item.phone ? " · " + esc(item.phone) : "") + "</p><p><strong>" + esc(item.business_name || "No business name") + "</strong> · " + esc(item.city || "") + " · " + esc((item.created_at || "").slice(0, 10)) + "</p><p>" + esc(item.facility_type || "") + " · " + esc(item.service || "") + " · " + esc(item.frequency || "") + "</p><p>About " + esc(item.square_feet || "size not given") + " sq ft · " + esc(item.rooms || "rooms not given") + "</p><p>" + esc(item.message || "") + "</p>" + files + "<button class='btn' type='button' id='close-inquiry'>Close</button></div>";
    document.body.appendChild(modal);
    modal.onclick = function (event) { if (event.target === modal) modal.remove(); };
    document.getElementById("close-inquiry").onclick = function () { modal.remove(); };
  }
  function applicationDetail(number) {
    api("/admin/applications/" + number).then(function (res) {
      if (!res.ok) { shell("/admin/recruitment/applications", "<h1>Application not found</h1>"); return; }
      var item = res.data.application;
      var person = item.applicant;
      shell("/admin/recruitment/applications", applicantPage(item));
      app.querySelectorAll("[data-doc]").forEach(function (button) {
        button.onclick = function () {
          api("/admin/documents/" + button.getAttribute("data-doc") + "/link", { method: "POST", body: {} }).then(function (result) {
            if (result.ok && result.data.url) window.open(result.data.url, "_blank");
          });
        };
      });
      app.querySelectorAll("[data-verify]").forEach(function (select) {
        select.onchange = function () {
          api("/admin/documents/" + select.getAttribute("data-verify"), { method: "PATCH", body: { verification_status: select.value } });
        };
      });
      var requestForm = document.getElementById("doc-request");
      if (requestForm) requestForm.onsubmit = function (event) {
        event.preventDefault();
        api("/admin/applications/" + number + "/document-requests", { method: "POST", body: Object.fromEntries(new FormData(event.target).entries()) }).then(function (result) {
          document.getElementById("doc-link").textContent = result.ok ? "Secure link: " + result.data.link : (result.data && result.data.error) || "Could not create the request.";
        });
      };
      document.getElementById("status").onchange = function (event) {
        api("/admin/applications/" + number, { method: "PATCH", body: { status: event.target.value } }).then(function () { applicationDetail(number); });
      };
      document.getElementById("note").onsubmit = function (event) {
        event.preventDefault();
        api("/admin/applications/" + number + "/notes", { method: "POST", body: { note: new FormData(event.target).get("note") } }).then(function () { applicationDetail(number); });
      };
    });
  }
  function locationsView() {
    api("/admin/locations").then(function (res) {
      var rows = ((res.data && res.data.locations) || []).map(function (loc) {
        return "<tr><td>" + esc(loc.name) + "</td><td>" + esc(loc.city) + "</td><td>" + esc(loc.province) + "</td><td>" + (loc.active ? "Active" : "Inactive") + "</td><td><button data-edit='" + loc.id + "'>Edit</button></td></tr>";
      }).join("");
      shell("/admin/recruitment/locations", "<h1>Locations</h1><table><thead><tr><th>Name</th><th>City</th><th>Province</th><th>Status</th><th></th></tr></thead><tbody>" + rows + "</tbody></table><h2>Add location</h2><form id='loc'><div class='grid'><label>Name<input name='name' required></label><label>City<input name='city' required></label><label>Province<input name='province' value='Manitoba'></label><label>Address<input name='address'></label><label>Postal code<input name='postal_code'></label><label>Status<select name='active'><option value='true'>Active</option><option value='false'>Inactive</option></select></label></div><button type='submit'>Save location</button></form>");
      var locForm = document.getElementById("loc");
      locForm.onsubmit = function (event) {
        event.preventDefault();
        var data = Object.fromEntries(new FormData(event.target).entries());
        data.active = data.active === "true";
        var id = locForm.getAttribute("data-id");
        api(id ? "/admin/locations/" + id : "/admin/locations", { method: id ? "PATCH" : "POST", body: data }).then(function () { locationsView(); });
      };
      app.querySelectorAll("[data-edit]").forEach(function (button) {
        button.onclick = function () {
          var loc = ((res.data && res.data.locations) || []).find(function (item) { return String(item.id) === button.getAttribute("data-edit"); });
          if (!loc) return;
          locForm.setAttribute("data-id", loc.id);
          locForm.elements.name.value = loc.name;
          locForm.elements.city.value = loc.city;
          locForm.elements.province.value = loc.province;
          locForm.elements.address.value = loc.address || "";
          locForm.elements.postal_code.value = loc.postal_code || "";
          locForm.elements.active.value = loc.active ? "true" : "false";
        };
      });
    });
  }
  function settingsView() {
    api("/admin/settings").then(function (res) {
      var settings = res.data.settings;
      shell("/admin/recruitment/settings", "<h1>Settings</h1><form id='settings'><h2>Mailgun</h2><p>Quote requests and job messages are sent through Mailgun to the inboxes below.</p><label>Inbox for quote requests<input name='quote_email' type='email' value='" + esc(settings.quote_email || "") + "' placeholder='clean@mastercleaning.ca'></label><label>Careers applications and questions<input name='recruitment_email' type='text' value='" + esc(settings.recruitment_email) + "' placeholder='one@mastercleaning.ca, two@mastercleaning.ca'></label><div class='grid'><label>Mailgun sending domain<input name='mailgun_domain' value='" + esc(settings.mailgun_domain || "") + "' placeholder='mg.mastercleaning.ca'></label><label>Region<select name='mailgun_region'><option value='us'" + (settings.mailgun_region !== "eu" ? " selected" : "") + ">United States</option><option value='eu'" + (settings.mailgun_region === "eu" ? " selected" : "") + ">Europe</option></select></label></div><label>From address<input name='smtp_from' value='" + esc(settings.smtp_from) + "' placeholder='Master Commercial Cleaning <quotes@mg.mastercleaning.ca>'></label><label>Mailgun API key<input name='mailgun_api_key' type='password' autocomplete='off' placeholder='" + (settings.mailgun_api_key_set ? "Saved" : "Not set") + "'></label><h2>Other mail server</h2><div class='grid'><label>SMTP host<input name='smtp_host' value='" + esc(settings.smtp_host) + "'></label><label>SMTP port<input name='smtp_port' value='" + esc(settings.smtp_port) + "'></label><label>SMTP user<input name='smtp_user' value='" + esc(settings.smtp_user) + "'></label></div><label>SMTP password<input name='smtp_password' type='password' placeholder='" + (settings.smtp_password_set ? "Saved" : "Not set") + "'></label><label>New admin password<input name='new_password' type='password' autocomplete='new-password'></label><p class='error' id='err' hidden></p><button type='submit'>Save settings</button></form><p><button type='button' id='email-test'>Send a test email</button></p><p id='email-test-note'></p>");
      document.getElementById("settings").onsubmit = function (event) {
        event.preventDefault();
        api("/admin/settings", { method: "PATCH", body: Object.fromEntries(new FormData(event.target).entries()) }).then(function (result) {
          document.getElementById("err").hidden = false;
          document.getElementById("err").textContent = result.ok ? "Saved." : "Could not save settings.";
        });
      };
      document.getElementById("email-test").onclick = function () {
        var note = document.getElementById("email-test-note");
        note.textContent = "Sending...";
        api("/admin/email-test", { method: "POST", body: {} }).then(function (result) {
          note.textContent = result.ok ? "Test sent to " + result.data.sent_to + "." : ((result.data && result.data.error) || "The test email was not sent.");
        });
      };
    });
  }
  function render() {
    var path = location.pathname.replace(/\/$/, "") || "/admin";
    api("/admin/session").then(function (res) {
      if (!res.ok) { loginView(); return; }
      if (path === "/admin" || path === "/admin/recruitment") return dashboardView();
      if (path === "/admin/recruitment/inquiries") return inquiriesView();
      if (path === "/admin/recruitment/quotes") return quotesView();
      if (path === "/admin/recruitment/jobs") return jobsView();
      if (path === "/admin/recruitment/jobs/new") return jobForm(null);
      var jobMatch = path.match(/^\/admin\/recruitment\/jobs\/(JOB-\d+)$/);
      if (jobMatch) return jobDetail(jobMatch[1]);
      if (path === "/admin/recruitment/applications") return applicationsView();
      var appMatch = path.match(/^\/admin\/recruitment\/applications\/(APP-\d{4}-\d+)$/);
      if (appMatch) return applicationDetail(appMatch[1]);
      if (path === "/admin/recruitment/locations") return locationsView();
      if (path === "/admin/recruitment/settings") return settingsView();
      shell("/admin/recruitment/jobs", "<h1>Not found</h1>");
    });
  }
  window.addEventListener("popstate", render);
  render();
})();
