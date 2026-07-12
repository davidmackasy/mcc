import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";
import sharp from "sharp";

const root = path.dirname(fileURLToPath(import.meta.url));
const photosDir = path.join(root, "images", "photos");
const assetsDir = path.join(
  os.homedir(),
  ".cursor",
  "projects",
  "c-Users-david-OneDrive-Documents-Projects-MCC",
  "assets",
);

const SERVICES = [
  {
    source: "c__Users_david_AppData_Roaming_Cursor_User_workspaceStorage_a49f9818438ee1286017c55892cd6047_images_efdfa06f-64e1-41a6-8d18-c905fe19b724-ee484860-6918-4ca7-8591-90dd6fa344d5.png",
    file: "janitorial-office-cleaning.webp",
    alt: "Professional cleaner mopping inside a modern office",
    oldPaths: ["images/photos/janitorial.jpg"],
  },
  {
    source: "c__Users_david_AppData_Roaming_Cursor_User_workspaceStorage_a49f9818438ee1286017c55892cd6047_images_edbc90b6-b6ba-4936-82bd-32df7d820c10-c0697fdc-8cbe-442d-b21f-283dac632cb3.png",
    file: "carpet-upholstery-cleaning.webp",
    alt: "Professional carpet extractor cleaning carpet in a commercial office lounge",
    oldPaths: ["images/photos/carpet.jpg"],
  },
  {
    source: "c__Users_david_AppData_Roaming_Cursor_User_workspaceStorage_a49f9818438ee1286017c55892cd6047_images_8ba07ffd-a23e-47b1-8887-919c3a712891-b9667a20-088e-4a49-9477-806c6ae9cc2b.png",
    file: "floor-stripping-waxing.webp",
    alt: "Worker operating a commercial floor buffer on a polished hard-surface floor",
    oldPaths: ["images/photos/floor.jpg"],
  },
  {
    source: "c__Users_david_AppData_Roaming_Cursor_User_workspaceStorage_a49f9818438ee1286017c55892cd6047_images_32ef7496-281d-47b7-91a4-43262e093e44-636bbd21-4a40-46cc-8045-8b83042375c4.png",
    file: "window-cleaning.webp",
    alt: "Professional cleaner using a squeegee on large commercial windows",
    oldPaths: ["images/photos/window.jpg"],
  },
  {
    source: "c__Users_david_AppData_Roaming_Cursor_User_workspaceStorage_a49f9818438ee1286017c55892cd6047_images_11bfb27c-2d42-413e-b81d-1d74e286e800-fc5a0d25-1e8f-43b6-976d-d1cd0c236643.png",
    file: "post-construction-cleanup.webp",
    alt: "Worker cleaning dust and construction debris inside a newly renovated commercial space",
    oldPaths: ["images/photos/post-construction.jpg"],
  },
  {
    source: "c__Users_david_AppData_Roaming_Cursor_User_workspaceStorage_a49f9818438ee1286017c55892cd6047_images_6b2dc5a1-d427-4b58-818a-09efe92a012f-e455df8a-8749-43d9-8de3-6169425a4356.png",
    file: "pressure-washing.webp",
    alt: "Worker pressure-washing the exterior wall and walkway of a commercial building",
    oldPaths: ["images/photos/pressure-washing.jpg"],
  },
  {
    source: "c__Users_david_AppData_Roaming_Cursor_User_workspaceStorage_a49f9818438ee1286017c55892cd6047_images_f7daac86-e493-4ae8-8cc1-2064e5b73951-33584c68-03aa-438c-97cd-6ea998dbff9d.png",
    file: "medical-dental-cleaning.webp",
    alt: "Cleaner disinfecting and wiping surfaces inside a modern dental clinic",
    oldPaths: ["images/photos/medical.jpg"],
  },
  {
    source: "c__Users_david_AppData_Roaming_Cursor_User_workspaceStorage_a49f9818438ee1286017c55892cd6047_images_ff1f4f8e-aac6-4eff-8906-a273fe3234ca-9dbbf53c-65f1-45fd-af7b-96ddcbc840ec.png",
    file: "drive-thru-exterior-detailing.webp",
    alt: "Workers cleaning a commercial drive-thru lane and surrounding exterior surfaces",
    oldPaths: ["images/photos/drive-thru.jpg"],
  },
];

const OLD_SERVICE_JPGS = [
  "janitorial.jpg",
  "carpet.jpg",
  "floor.jpg",
  "window.jpg",
  "post-construction.jpg",
  "pressure-washing.jpg",
  "medical.jpg",
  "drive-thru.jpg",
];

async function convertImages() {
  fs.mkdirSync(photosDir, { recursive: true });

  for (const service of SERVICES) {
    const src = path.join(assetsDir, service.source);
    const dest = path.join(photosDir, service.file);

    if (!fs.existsSync(src)) {
      throw new Error(`Source image not found: ${src}`);
    }

    const input = fs.readFileSync(src);
    await sharp(input)
      .resize({ width: 1400, withoutEnlargement: true })
      .webp({ quality: 85, effort: 4 })
      .toFile(dest);

    const stats = fs.statSync(dest);
    console.log(`Created ${service.file} (${Math.round(stats.size / 1024)} KB)`);
  }
}

function updateHtml() {
  const htmlFiles = fs.readdirSync(root).filter((f) => f.endsWith(".html"));

  for (const file of htmlFiles) {
    const filePath = path.join(root, file);
    let html = fs.readFileSync(filePath, "utf8");
    let changed = false;

    for (const service of SERVICES) {
      const newSrc = `images/photos/${service.file}`;
      for (const oldPath of service.oldPaths) {
        if (html.includes(oldPath)) {
          html = html.split(oldPath).join(newSrc);
          changed = true;
        }
      }

      const altRe = new RegExp(
        `(<img src="${newSrc.replace(/\./g, "\\.")}" alt=")[^"]*(")`,
        "g",
      );
      const next = html.replace(altRe, `$1${service.alt}$2`);
      if (next !== html) {
        html = next;
        changed = true;
      }
    }

    if (changed) {
      fs.writeFileSync(filePath, html, "utf8");
      console.log(`Updated ${file}`);
    }
  }
}

function removeOldImages() {
  for (const name of OLD_SERVICE_JPGS) {
    const filePath = path.join(photosDir, name);
    if (fs.existsSync(filePath)) {
      fs.unlinkSync(filePath);
      console.log(`Removed old ${name}`);
    }
  }
}

function verify() {
  const htmlFiles = fs.readdirSync(root).filter((f) => f.endsWith(".html"));
  const issues = [];

  for (const file of htmlFiles) {
    const html = fs.readFileSync(path.join(root, file), "utf8");
    for (const old of OLD_SERVICE_JPGS.map((n) => `images/photos/${n}`)) {
      if (html.includes(old)) issues.push(`${file} still references ${old}`);
    }
  }

  for (const service of SERVICES) {
    const dest = path.join(photosDir, service.file);
    if (!fs.existsSync(dest)) issues.push(`Missing ${service.file}`);
  }

  if (issues.length) {
    throw new Error(issues.join("\n"));
  }

  console.log("Verification passed — all 8 services use shared .webp assets.");
}

await convertImages();
updateHtml();
removeOldImages();
verify();
