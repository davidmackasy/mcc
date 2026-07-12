import fs from "node:fs";
import path from "node:path";
import https from "node:https";
import http from "node:http";
import { fileURLToPath } from "node:url";

const root = path.dirname(fileURLToPath(import.meta.url));
const photosDir = path.join(root, "images", "photos");

// Custom service images — installed via install-service-images.mjs (do not download from stock)
const LOCAL_SERVICES = {
  janitorial: { file: "janitorial-office-cleaning.webp", alt: "Professional cleaner mopping inside a modern office" },
  carpet: { file: "carpet-upholstery-cleaning.webp", alt: "Professional carpet extractor cleaning carpet in a commercial office lounge" },
  floor: { file: "floor-stripping-waxing.webp", alt: "Worker operating a commercial floor buffer on a polished hard-surface floor" },
  window: { file: "window-cleaning.webp", alt: "Professional cleaner using a squeegee on large commercial windows" },
  "post-construction": { file: "post-construction-cleanup.webp", alt: "Worker cleaning dust and construction debris inside a newly renovated commercial space" },
  "pressure-washing": { file: "pressure-washing.webp", alt: "Worker pressure-washing the exterior wall and walkway of a commercial building" },
  medical: { file: "medical-dental-cleaning.webp", alt: "Cleaner disinfecting and wiping surfaces inside a modern dental clinic" },
  "drive-thru": { file: "drive-thru-exterior-detailing.webp", alt: "Workers cleaning a commercial drive-thru lane and surrounding exterior surfaces" },
  "why-choose-us": { file: "why-choose-us.webp", alt: "Master Cleaning manager performing a commercial facility inspection" },
};

// Stock photos for non-service sections
const PHOTOS = {
  "about-staff": {
    url: "https://images.pexels.com/photos/6195950/pexels-photo-6195950.jpeg?auto=compress&cs=tinysrgb&w=1200",
    alt: "Cleaner in protective equipment vacuuming in a modern commercial space",
  },
  "about-vision": {
    url: "https://images.unsplash.com/photo-1600880292203-757bb62b4baf?w=1200&q=80",
    alt: "Clean, well-lit modern office interior after a commercial cleaning visit",
  },
  industries: {
    url: "https://images.unsplash.com/photo-1497366216548-37526070297c?w=1200&q=80",
    alt: "Clean modern lobby of a commercial building",
  },
  "eco-supplies": {
    url: "https://images.unsplash.com/photo-1584464491033-06628f3a6b7b?w=1200&q=80",
    alt: "Eco-friendly green cleaning products and supplies",
  },
};

function download(url, dest) {
  return new Promise((resolve, reject) => {
    const client = url.startsWith("https") ? https : http;
    client
      .get(url, { headers: { "User-Agent": "MCC-site-setup/1.0" } }, (res) => {
        if (res.statusCode && res.statusCode >= 300 && res.statusCode < 400 && res.headers.location) {
          download(res.headers.location, dest).then(resolve).catch(reject);
          return;
        }
        if (res.statusCode !== 200) {
          reject(new Error(`HTTP ${res.statusCode} for ${url}`));
          return;
        }
        const file = fs.createWriteStream(dest);
        res.pipe(file);
        file.on("finish", () => file.close(() => resolve(dest)));
      })
      .on("error", reject);
  });
}

async function main() {
  fs.mkdirSync(photosDir, { recursive: true });

  for (const [name, photo] of Object.entries(PHOTOS)) {
    if (!photo.url) continue;
    const dest = path.join(photosDir, `${name}.jpg`);
    console.log("Downloading", name);
    await download(photo.url, dest);
  }

  // Sync alt text for custom service images
  for (const file of fs.readdirSync(root).filter((f) => f.endsWith(".html"))) {
    let html = fs.readFileSync(path.join(root, file), "utf8");
    let changed = false;
    for (const photo of Object.values(LOCAL_SERVICES)) {
      const src = `images/photos/${photo.file}`;
      const re = new RegExp(`(<img src="${src.replace(/\./g, "\\.")}" alt=")[^"]*(")`, "g");
      const next = html.replace(re, `$1${photo.alt}$2`);
      if (next !== html) {
        html = next;
        changed = true;
      }
    }
    for (const [name, photo] of Object.entries(PHOTOS)) {
      const src = `images/photos/${name}.jpg`;
      const re = new RegExp(`(<img src="${src}" alt=")[^"]*(")`, "g");
      const next = html.replace(re, `$1${photo.alt}$2`);
      if (next !== html) {
        html = next;
        changed = true;
      }
    }
    if (changed) {
      fs.writeFileSync(path.join(root, file), html, "utf8");
      console.log("Updated alt text in", file);
    }
  }

  console.log("All photos downloaded.");
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
