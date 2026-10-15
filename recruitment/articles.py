"""GrandRanker article webhook and server-rendered blog pages."""

import hmac
import json
import os
import re
from datetime import datetime
from html import escape
from urllib.parse import quote

from recruitment import db

STATIC_PATHS = (
    "/",
    "/services.html",
    "/janitorial-cleaning.html",
    "/carpet-upholstery-cleaning.html",
    "/floor-care.html",
    "/window-cleaning.html",
    "/post-construction-cleaning.html",
    "/pressure-washing.html",
    "/medical-dental-cleaning.html",
    "/drive-thru-exterior-detailing.html",
    "/industries.html",
    "/about.html",
    "/contact.html",
    "/careers.html",
    "/privacy-policy.html",
)


def keys_match(provided, expected):
    provided = provided or ""
    expected = expected or ""
    if not expected or not provided or len(provided) != len(expected):
        return False
    return hmac.compare_digest(provided, expected)


def as_int(value):
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def slugify(text):
    slug = re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-")
    return slug or "article"


def row_from_item(item):
    """Copy only the columns the articles table stores. Extra payload fields are ignored."""
    if not isinstance(item, dict):
        return None
    external_id = item.get("id")
    if external_id is None or str(external_id).strip() == "":
        return None
    external_id = str(external_id)
    slug = (item.get("slug") or "").strip() or slugify(item.get("title") or external_id)
    return {
        "external_id": external_id,
        "title": item.get("title"),
        "slug": slug,
        "content_html": item.get("content_html"),
        "content_markdown": item.get("content_markdown"),
        "meta_title": item.get("meta_title"),
        "meta_description": item.get("meta_description"),
        "subtitle": item.get("subtitle"),
        "category": item.get("category"),
        "author_name": item.get("author_name"),
        "image_url": item.get("image_url"),
        "read_time": item.get("read_time"),
        "word_count": as_int(item.get("word_count")),
        "tags": item.get("tags"),
        "faqs": item.get("faqs"),
        "json_ld_schema": item.get("json_ld_schema"),
        "language_code": item.get("language_code"),
        "published_at": item.get("publish_date"),
        "updated_at": item.get("updated_at") or db.now_iso(),
    }


def webhook(method, api_key, raw):
    if method in ("GET", "HEAD"):
        return 200, {"ok": True}
    if method != "POST":
        return 405, {"error": "Method not allowed."}
    if not keys_match(api_key, os.environ.get("GRANDRANKER_SECRET")):
        return 401, {"error": "Unauthorized"}
    try:
        payload = json.loads((raw or b"").decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return 400, {"error": "Invalid JSON."}
    if not isinstance(payload, dict):
        return 400, {"error": "Invalid JSON."}
    event = payload.get("event_type")
    data = payload.get("data") if isinstance(payload.get("data"), dict) else {}
    if event == "publish_articles":
        items = data.get("articles") if isinstance(data.get("articles"), list) else []
        rows = [row for row in (row_from_item(item) for item in items) if row]
        return 200, {"ok": True, "upserted": db.publish_articles(rows)}
    if event == "unpublish_article":
        external_id = data.get("id")
        if external_id is None or str(external_id).strip() == "":
            return 400, {"error": "Missing article id."}
        db.delete_article(external_id)
        return 200, {"ok": True}
    return 200, {"ok": True}


def xml_escape(value):
    return (
        str(value)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def display_date(value):
    if not value:
        return ""
    text = str(value).strip().replace("Z", "")
    for fmt, size in (("%Y-%m-%dT%H:%M:%S", 19), ("%Y-%m-%d", 10)):
        try:
            return datetime.strptime(text[:size], fmt).strftime("%B %d, %Y").replace(" 0", " ")
        except ValueError:
            continue
    return str(value)


def lastmod(value):
    if not value:
        return ""
    return str(value).strip().replace(" ", "T")


def article_url(origin, slug):
    return origin.rstrip("/") + "/blog/" + quote(slug or "", safe="-._~")


def absolute_url(origin, url):
    if not url:
        return origin.rstrip("/") + "/images/logo.png"
    if url.startswith("http://") or url.startswith("https://"):
        return url
    if url.startswith("/"):
        return origin.rstrip("/") + url
    return origin.rstrip("/") + "/" + url


def json_ld_tag(value):
    if not value:
        return ""
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except json.JSONDecodeError:
            return ""
    if not isinstance(value, (dict, list)):
        return ""
    payload = json.dumps(value, ensure_ascii=False).replace("<", "\\u003c")
    return '<script type="application/ld+json">%s</script>' % payload


def faq_html(faqs):
    if not isinstance(faqs, list) or not faqs:
        return ""
    blocks = []
    for item in faqs:
        if not isinstance(item, dict):
            continue
        question = item.get("question") or item.get("q") or ""
        answer = item.get("answer") or item.get("a") or ""
        if not question and not answer:
            continue
        blocks.append("<h3>%s</h3><p>%s</p>" % (escape(str(question)), escape(str(answer))))
    if not blocks:
        return ""
    return '<section class="post-body"><h2>Questions</h2>%s</section>' % "".join(blocks)


def chrome(origin, head_title, description, canonical, main, *, image=None, json_ld="", og_type="website", lang="en", robots=""):
    image = absolute_url(origin, image)
    robots_tag = ('<meta name="robots" content="%s">' % escape(robots)) if robots else ""
    return """<!doctype html>
<html lang="%s">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1, minimum-scale=1">
<title>%s</title>
<meta name="description" content="%s">
<link rel="canonical" href="%s">
<meta property="og:type" content="%s">
<meta property="og:title" content="%s">
<meta property="og:description" content="%s">
<meta property="og:url" content="%s">
<meta property="og:image" content="%s">
%s
%s
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@500;600;700&family=Inter:wght@400;500;600&family=IBM+Plex+Mono:wght@400;500&display=swap" rel="stylesheet">
<link rel="stylesheet" href="/css/blog.css">
</head>
<body>
<header class="site-header">
  <div class="wrap">
    <a href="/" class="brand"><img src="/images/logo.png" alt="Master Commercial Cleaning" class="brand-logo" width="300" height="218"></a>
    <nav class="main-nav">
      <ul>
        <li><a href="/">Home</a></li>
        <li><a href="/about.html">About</a></li>
        <li><a href="/services.html">Services</a></li>
        <li><a href="/industries.html">Industries</a></li>
        <li><a href="/careers.html">Careers</a></li>
        <li><a href="/blog" aria-current="page">Blog</a></li>
        <li><a href="/contact.html">Contact</a></li>
      </ul>
      <a class="header-call" href="tel:+12046981133"><span class="txt">+1 (204) 698-1133</span></a>
      <button class="nav-toggle" aria-label="Toggle menu" aria-expanded="false"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="3" y1="6" x2="21" y2="6"/><line x1="3" y1="12" x2="21" y2="12"/><line x1="3" y1="18" x2="21" y2="18"/></svg></button>
    </nav>
  </div>
</header>
<main>
%s
  <section class="cta-band">
    <div class="wrap">
      <h2>Take back your time. Leave the cleaning to us.</h2>
      <span class="phone-big">+1 (204) 698-1133</span>
      <div class="actions">
        <a href="/contact.html" class="btn btn-primary">Request a free estimate</a>
        <a href="mailto:clean@mastercleaning.ca" class="btn btn-on-dark">Email clean@mastercleaning.ca</a>
      </div>
    </div>
  </section>
</main>
<footer class="site-footer">
  <div class="wrap">
    <div class="footer-grid">
      <div class="footer-brand">
        <a href="/" class="brand"><img src="/images/logo.png" alt="Master Commercial Cleaning" class="brand-logo" width="300" height="218"></a>
        <p>Commercial cleaning and building maintenance for Winnipeg, Selkirk, Oakbank, Beausejour, and part of Manitoba since 2015.</p>
      </div>
      <div class="footer-col"><h4>Site</h4><ul>
        <li><a href="/">Home</a></li>
        <li><a href="/about.html">About</a></li>
        <li><a href="/services.html">Services</a></li>
        <li><a href="/blog">Blog</a></li>
        <li><a href="/contact.html">Contact</a></li>
      </ul></div>
      <div class="footer-col"><h4>Contact</h4><ul>
        <li><a href="tel:+12046981133">+1 (204) 698-1133</a></li>
        <li><a href="mailto:clean@mastercleaning.ca">clean@mastercleaning.ca</a></li>
        <li><a href="https://maps.google.com/?q=Unit+7,+1599+Dugald+Rd,+Winnipeg,+MB">Unit 7, 1599 Dugald Rd, Winnipeg, MB</a></li>
      </ul></div>
    </div>
    <div class="footer-bottom"><span>&copy; <span id="year">2026</span> Master Commercial Cleaning Services &amp; Building Maintenance Ltd. &middot; <a href="/privacy-policy.html">Privacy Policy</a></span></div>
  </div>
</footer>
<script>
document.addEventListener("DOMContentLoaded", function () {
  var header = document.querySelector(".site-header");
  var toggle = document.querySelector(".nav-toggle");
  if (toggle && header) {
    toggle.addEventListener("click", function () {
      header.classList.toggle("nav-open");
      toggle.setAttribute("aria-expanded", header.classList.contains("nav-open") ? "true" : "false");
    });
  }
  var yearEl = document.querySelector("#year");
  if (yearEl) yearEl.textContent = new Date().getFullYear();
});
</script>
</body>
</html>
""" % (
        escape(lang or "en"),
        escape(head_title),
        escape(description or ""),
        escape(canonical),
        escape(og_type),
        escape(head_title),
        escape(description or ""),
        escape(canonical),
        escape(image),
        robots_tag,
        json_ld,
        main,
    )


def blog_index(origin):
    posts = db.list_articles()
    if posts:
        cards = []
        for post in posts:
            href = article_url(origin, post.get("slug"))
            path = href[len(origin.rstrip("/")):]
            when = escape(display_date(post.get("published_at") or post.get("updated_at")))
            title = escape(post.get("title") or "Untitled")
            summary = escape(post.get("subtitle") or post.get("meta_description") or "")
            meta_bits = [bit for bit in (post.get("category"), post.get("read_time"), when) if bit]
            meta = escape(" · ".join(str(bit) for bit in meta_bits))
            cards.append(
                "<article><p class=\"meta\">%s</p><h2><a href=\"%s\">%s</a></h2><p>%s</p><a class=\"read\" href=\"%s\">Read article</a></article>"
                % (meta, escape(path), title, summary, escape(path))
            )
        listing = "".join(cards)
    else:
        listing = "<article><h2>No articles yet</h2><p>New posts will show up here.</p></article>"
    main = """
  <section class="page-banner">
    <div class="wrap">
      <span class="crumbs">Home / Blog</span>
      <h1>Blog</h1>
      <p>Notes on commercial cleaning for offices, retail, medical, and other facilities in Winnipeg, Selkirk, Oakbank, and Beausejour.</p>
    </div>
  </section>
  <section class="blog-list"><div class="wrap">%s</div></section>
""" % listing
    return chrome(
        origin,
        "Blog | Master Commercial Cleaning",
        "Articles on commercial and janitorial cleaning for businesses in Winnipeg, Selkirk, Oakbank, and Beausejour.",
        origin.rstrip("/") + "/blog",
        main,
    )


def blog_article(origin, slug):
    post = db.get_article_by_slug(slug)
    if not post:
        return None
    title = post.get("meta_title") or post.get("title") or "Article"
    description = post.get("meta_description") or post.get("subtitle") or ""
    canonical = article_url(origin, post.get("slug") or slug)
    when = escape(display_date(post.get("published_at")))
    author = escape(post.get("author_name") or "Master Commercial Cleaning")
    image = ""
    if post.get("image_url"):
        image = '<img src="%s" alt="%s">' % (escape(absolute_url(origin, post["image_url"])), escape(post.get("title") or ""))
    main = """
  <section class="page-banner">
    <div class="wrap">
      <span class="crumbs"><a href="/blog">Blog</a>%s</span>
      <h1>%s</h1>
      <p class="meta" style="color:rgba(255,255,255,0.55)">%s%s</p>
    </div>
  </section>
  <article class="post"><div class="wrap post-body">%s%s</div></article>
  %s
""" % (
        (" / " + escape(post.get("category"))) if post.get("category") else "",
        escape(post.get("title") or title),
        author,
        (" · " + when) if when else "",
        ("<p>%s</p>" % escape(post.get("subtitle"))) if post.get("subtitle") else "",
        image + (post.get("content_html") or ""),
        faq_html(post.get("faqs")),
    )
    return chrome(
        origin,
        title,
        description,
        canonical,
        main,
        image=post.get("image_url"),
        json_ld=json_ld_tag(post.get("json_ld_schema")),
        og_type="article",
        lang=post.get("language_code") or "en",
    )


def not_found(origin):
    main = """
  <section class="page-banner">
    <div class="wrap">
      <span class="crumbs"><a href="/blog">Blog</a></span>
      <h1>This article is not available</h1>
      <p>The page may have been removed. The current posts are on the blog.</p>
    </div>
  </section>
"""
    return chrome(
        origin,
        "Article not found | Master Commercial Cleaning",
        "This article is not on the Master Commercial Cleaning blog.",
        origin.rstrip("/") + "/blog",
        main,
        robots="noindex",
    )


def sitemap_xml(origin):
    origin = origin.rstrip("/")
    posts = db.list_articles()
    urls = []
    for path in STATIC_PATHS:
        urls.append("<url><loc>%s</loc></url>" % xml_escape(origin + path))
    blog_last = ""
    if posts:
        blog_last = lastmod(posts[0].get("updated_at") or posts[0].get("published_at"))
    blog = "<url><loc>%s</loc>" % xml_escape(origin + "/blog")
    if blog_last:
        blog += "<lastmod>%s</lastmod>" % xml_escape(blog_last)
    blog += "</url>"
    urls.append(blog)
    for post in posts:
        slug = post.get("slug")
        if not slug:
            continue
        loc = article_url(origin, slug)
        stamp = lastmod(post.get("updated_at") or post.get("published_at"))
        entry = "<url><loc>%s</loc>" % xml_escape(loc)
        if stamp:
            entry += "<lastmod>%s</lastmod>" % xml_escape(stamp)
        entry += "</url>"
        urls.append(entry)
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n  '
        + "\n  ".join(urls)
        + "\n</urlset>\n"
    )
