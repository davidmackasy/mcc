import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const root = path.dirname(fileURLToPath(import.meta.url));

const CSS_LINK = '<link rel="stylesheet" href="css/whatsapp-widget.css">';
const JS_SCRIPT = '<script src="js/whatsapp-widget.js" defer></script>';

const WIDGET_HTML = `
<button id="wa-fab" class="wa-fab" aria-label="Chat with us on WhatsApp">
  <span class="wa-ping" aria-hidden="true"></span>
  <svg viewBox="0 0 32 32" aria-hidden="true"><path d="M16.001 3C9.107 3 3.5 8.607 3.5 15.5c0 2.348.65 4.545 1.777 6.42L3 29l7.256-2.234A12.44 12.44 0 0 0 16.001 28C22.895 28 28.5 22.393 28.5 15.5S22.895 3 16.001 3zm7.29 17.61c-.31.87-1.53 1.6-2.51 1.81-.67.14-1.54.25-4.47-.96-3.75-1.55-6.17-5.35-6.36-5.6-.19-.25-1.52-2.02-1.52-3.86 0-1.84.96-2.74 1.31-3.12.31-.34.83-.5 1.32-.5.16 0 .3.01.43.01.38.02.57.04.82.63.31.75 1.06 2.59 1.15 2.78.09.19.15.41.03.66-.11.25-.17.4-.34.61-.17.21-.36.47-.51.63-.17.18-.35.37-.15.72.19.35.86 1.42 1.85 2.3 1.27 1.13 2.34 1.48 2.69 1.65.35.17.55.14.75-.08.2-.22.86-1 1.09-1.35.23-.35.46-.29.77-.17.31.11 1.99.94 2.33 1.11.34.17.57.25.65.39.09.14.09.83-.22 1.7z"/></svg>
</button>

<div id="wa-overlay" class="wa-overlay">
  <div class="wa-modal" role="dialog" aria-modal="true" aria-label="Chat with us on WhatsApp">
    <div class="wa-modal-head">
      <span class="wa-avatar">
        <svg viewBox="0 0 32 32" aria-hidden="true"><path d="M16.001 3C9.107 3 3.5 8.607 3.5 15.5c0 2.348.65 4.545 1.777 6.42L3 29l7.256-2.234A12.44 12.44 0 0 0 16.001 28C22.895 28 28.5 22.393 28.5 15.5S22.895 3 16.001 3zm7.29 17.61c-.31.87-1.53 1.6-2.51 1.81-.67.14-1.54.25-4.47-.96-3.75-1.55-6.17-5.35-6.36-5.6-.19-.25-1.52-2.02-1.52-3.86 0-1.84.96-2.74 1.31-3.12.31-.34.83-.5 1.32-.5.16 0 .3.01.43.01.38.02.57.04.82.63.31.75 1.06 2.59 1.15 2.78.09.19.15.41.03.66-.11.25-.17.4-.34.61-.17.21-.36.47-.51.63-.17.18-.35.37-.15.72.19.35.86 1.42 1.85 2.3 1.27 1.13 2.34 1.48 2.69 1.65.35.17.55.14.75-.08.2-.22.86-1 1.09-1.35.23-.35.46-.29.77-.17.31.11 1.99.94 2.33 1.11.34.17.57.25.65.39.09.14.09.83-.22 1.7z"/></svg>
      </span>
      <div>
        <h3>Master Commercial Cleaning</h3>
        <p>Typically replies within a few hours</p>
      </div>
      <button id="wa-close" class="wa-close" type="button" aria-label="Close"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg></button>
    </div>
    <div class="wa-modal-body">
      <div class="wa-note">Tell us a bit about what you need and we'll open WhatsApp with your message ready to send.</div>
      <form id="wa-form">
        <label for="wa-name">Your name</label>
        <input type="text" id="wa-name" required placeholder="Full name">
        <label for="wa-phone">Phone number</label>
        <input type="tel" id="wa-phone" required placeholder="(204) 000-0000">
        <label for="wa-service">What do you need?</label>
        <select id="wa-service">
          <option>Janitorial &amp; Office Cleaning</option>
          <option>Carpet &amp; Upholstery Cleaning</option>
          <option>Floor Stripping &amp; Waxing</option>
          <option>Window Cleaning</option>
          <option>Post-Construction Cleanup</option>
          <option>Pressure Washing</option>
          <option>Medical &amp; Dental Facility Cleaning</option>
          <option>Drive-Thru &amp; Exterior Detailing</option>
          <option>General question</option>
        </select>
        <label for="wa-message">Anything else? (optional)</label>
        <textarea id="wa-message" rows="3" placeholder="Square footage, schedule, or other details"></textarea>
        <button type="submit" class="wa-send-btn">
          <svg viewBox="0 0 32 32" fill="#fff" aria-hidden="true"><path d="M16.001 3C9.107 3 3.5 8.607 3.5 15.5c0 2.348.65 4.545 1.777 6.42L3 29l7.256-2.234A12.44 12.44 0 0 0 16.001 28C22.895 28 28.5 22.393 28.5 15.5S22.895 3 16.001 3zm7.29 17.61c-.31.87-1.53 1.6-2.51 1.81-.67.14-1.54.25-4.47-.96-3.75-1.55-6.17-5.35-6.36-5.6-.19-.25-1.52-2.02-1.52-3.86 0-1.84.96-2.74 1.31-3.12.31-.34.83-.5 1.32-.5.16 0 .3.01.43.01.38.02.57.04.82.63.31.75 1.06 2.59 1.15 2.78.09.19.15.41.03.66-.11.25-.17.4-.34.61-.17.21-.36.47-.51.63-.17.18-.35.37-.15.72.19.35.86 1.42 1.85 2.3 1.27 1.13 2.34 1.48 2.69 1.65.35.17.55.14.75-.08.2-.22.86-1 1.09-1.35.23-.35.46-.29.77-.17.31.11 1.99.94 2.33 1.11.34.17.57.25.65.39.09.14.09.83-.22 1.7z"/></svg>
          Send via WhatsApp
        </button>
      </form>
    </div>
  </div>
</div>
`.trim();

for (const file of fs.readdirSync(root).filter((f) => f.endsWith(".html"))) {
  const filePath = path.join(root, file);
  let html = fs.readFileSync(filePath, "utf8");

  if (html.includes('id="wa-fab"')) {
    console.log("Skip (already injected):", file);
    continue;
  }

  if (!html.includes(CSS_LINK)) {
    html = html.replace(
      /<link href="https:\/\/fonts\.googleapis\.com[^>]+>/,
      (match) => `${match}\n${CSS_LINK}`,
    );
  }

  html = html.replace("</footer>", `</footer>\n${WIDGET_HTML}`);

  if (!html.includes(JS_SCRIPT)) {
    html = html.replace("<script>", `${JS_SCRIPT}\n<script>`);
  }

  fs.writeFileSync(filePath, html, "utf8");
  console.log("Injected:", file);
}

console.log("Done.");
