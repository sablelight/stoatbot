import stoat
from stoat.ext import commands
from utils.helpers import success_embed, error_embed, info_embed, is_staff
from utils.db import Database
import aiohttp
import base64
import os
import json
import logging
import re
from datetime import datetime, timezone

log = logging.getLogger("vouches")

GITHUB_API = "https://api.github.com"

SITE_HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Vouches</title>
<meta name="color-scheme" content="dark">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Space+Mono:wght@400;700&family=Syne:wght@700;800;900&display=swap" rel="stylesheet">
<style>
  :root {
    --accent: #FF00FF;
    --accent-dim: rgba(255,0,255,0.13);
    --accent-glow: rgba(255,0,255,0.38);
    --accent-glow2: rgba(255,0,255,0.22);
    --bg: #0a0a0f;
    --bg2: #0e0d16;
    --surface: #141220;
    --surface2: #1a1828;
    --border: rgba(255,0,255,0.18);
    --border-hover: rgba(255,0,255,0.55);
    --text: #e4e0f0;
    --muted: #7a738f;
  }

  * { box-sizing: border-box; margin: 0; padding: 0; }

  body {
    background: var(--bg);
    color: var(--text);
    font-family: 'Space Mono', monospace;
    min-height: 100vh;
    overflow-x: hidden;
  }

  body::before {
    content: '';
    position: fixed;
    inset: 0;
    background:
      radial-gradient(ellipse 80vw 60vh at 15% 10%, rgba(255,0,255,0.15) 0%, transparent 65%),
      radial-gradient(ellipse 60vw 50vh at 85% 85%, rgba(255,0,255,0.14) 0%, transparent 65%);
    pointer-events: none;
    z-index: 0;
  }

  body::after {
    content: '';
    position: fixed;
    inset: 0;
    background-image:
      linear-gradient(rgba(255,0,255,0.025) 1px, transparent 1px),
      linear-gradient(90deg, rgba(255,0,255,0.025) 1px, transparent 1px);
    background-size: 44px 44px;
    pointer-events: none;
    z-index: 0;
  }

  .container {
    max-width: 900px;
    margin: 0 auto;
    padding: 0 20px 80px;
    position: relative;
    z-index: 1;
  }

  .hero {
    text-align: center;
    padding: 52px 0 32px;
  }

  .hero-title {
    font-family: 'Syne', sans-serif;
    font-size: clamp(1.8rem, 5vw, 3.2rem);
    font-weight: 900;
    letter-spacing: -1px;
    color: #fff;
    line-height: 1;
    margin-bottom: 6px;
  }
  .hero-title span { color: var(--accent); }

  .hero-badge {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    font-size: 0.72rem;
    color: #FF00FF;
    letter-spacing: 3px;
    text-transform: uppercase;
    margin-bottom: 20px;
  }
  .hero-badge::before {
    content: '';
    width: 7px; height: 7px;
    border-radius: 50%;
    background: #FF00FF;
    box-shadow: 0 0 8px #FF00FF;
    animation: pulse 2s infinite;
  }
  @keyframes pulse {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.45; }
  }

  .stats {
    display: flex;
    gap: 16px;
    justify-content: center;
    flex-wrap: wrap;
    margin-bottom: 20px;
  }
  .stats span {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 8px 18px;
    font-size: 0.75rem;
    color: var(--muted);
    letter-spacing: 1px;
  }
  .stats b { color: var(--accent); }

  .search-wrap {
    max-width: 600px;
    margin: 0 auto;
  }
  .search-wrap input {
    width: 100%;
    padding: 12px 18px;
    border: 1px solid var(--border);
    border-radius: 8px;
    background: var(--surface);
    color: #fff;
    font-family: 'Space Mono', monospace;
    font-size: 0.82rem;
    outline: none;
    transition: border-color 0.2s, box-shadow 0.2s;
  }
  .search-wrap input::placeholder { color: var(--muted); }
  .search-wrap input:focus {
    border-color: var(--accent);
    box-shadow: 0 0 20px var(--accent-glow);
  }

  .vouch-list { margin-top: 28px; }

  .vouch-card {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 10px;
    padding: 20px;
    margin-bottom: 14px;
    transition: border-color 0.22s, box-shadow 0.22s;
    position: relative;
    overflow: hidden;
  }
  .vouch-card::before {
    content: '';
    position: absolute;
    inset: 0;
    border-radius: 9px;
    background: linear-gradient(135deg, rgba(255,0,255,0.04), rgba(255,0,255,0.02));
    opacity: 0;
    transition: opacity 0.22s;
    pointer-events: none;
  }
  .vouch-card:hover {
    border-color: var(--border-hover);
    box-shadow: 0 0 22px var(--accent-glow), 0 4px 16px rgba(0,0,0,0.4);
  }
  .vouch-card:hover::before { opacity: 1; }

  .vouch-card .meta {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 10px;
    flex-wrap: wrap;
    gap: 6px;
    position: relative;
    z-index: 1;
  }
  .vouch-card .author {
    font-weight: 700;
    color: #fff;
    font-size: 0.85rem;
    letter-spacing: 0.5px;
  }
  .vouch-card .author .badge {
    background: var(--accent);
    color: #fff;
    font-size: 0.6rem;
    padding: 2px 8px;
    border-radius: 10px;
    margin-left: 6px;
    letter-spacing: 1px;
  }
  .vouch-card .date {
    color: var(--muted);
    font-size: 0.7rem;
    letter-spacing: 0.5px;
  }
  .vouch-card .target {
    color: var(--accent);
    font-size: 0.78rem;
    margin-bottom: 8px;
    position: relative;
    z-index: 1;
  }
  .vouch-card .target::before {
    content: '\2192 ';
    opacity: 0.6;
  }
  .vouch-card .content {
    color: var(--text);
    font-size: 0.82rem;
    line-height: 1.6;
    margin-bottom: 12px;
    white-space: pre-wrap;
    position: relative;
    z-index: 1;
  }
  .vouch-card .attachments {
    display: flex;
    gap: 8px;
    flex-wrap: wrap;
    position: relative;
    z-index: 1;
  }
  .vouch-card .attachments a {
    display: block;
    border: 1px solid var(--border);
    border-radius: 8px;
    overflow: hidden;
    max-width: 200px;
    transition: border-color 0.2s, box-shadow 0.2s;
  }
  .vouch-card .attachments a:hover {
    border-color: var(--accent);
    box-shadow: 0 0 14px var(--accent-glow2);
  }
  .vouch-card .attachments img,
  .vouch-card .attachments video {
    width: 100%;
    display: block;
    max-height: 160px;
    object-fit: cover;
  }
  .vouch-card .attachments .file-link {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 6px 12px;
    background: var(--bg2);
    border: 1px solid var(--border);
    border-radius: 6px;
    color: var(--accent);
    text-decoration: none;
    font-size: 0.72rem;
    transition: all 0.2s;
  }
  .vouch-card .attachments .file-link:hover {
    background: var(--accent-dim);
    border-color: var(--accent);
  }
  .vouch-card .issue-link {
    display: inline-block;
    margin-top: 10px;
    color: var(--muted);
    font-size: 0.7rem;
    text-decoration: none;
    transition: color 0.2s;
    position: relative;
    z-index: 1;
  }
  .vouch-card .issue-link:hover {
    color: var(--accent);
    text-decoration: underline;
  }

  .empty {
    text-align: center;
    padding: 60px 20px;
    color: var(--muted);
  }
  .empty h2 {
    font-family: 'Syne', sans-serif;
    font-weight: 900;
    font-size: 1.4rem;
    margin-bottom: 8px;
    color: var(--text);
  }

  .lightbox {
    display: none;
    position: fixed;
    top: 0; left: 0;
    width: 100%; height: 100%;
    background: rgba(5,4,12,0.92);
    z-index: 9999;
    justify-content: center;
    align-items: center;
    padding: 24px;
    cursor: zoom-out;
    backdrop-filter: blur(8px);
  }
  .lightbox.open { display: flex; }
  .lightbox img, .lightbox video {
    max-width: 100%;
    max-height: 90vh;
    border-radius: 8px;
    cursor: default;
    box-shadow: 0 0 40px rgba(255,0,255,0.15);
  }

  .footer {
    text-align: center;
    font-size: 0.7rem;
    color: var(--muted);
    padding: 40px 0 0;
    letter-spacing: 2px;
    opacity: 0.6;
  }

  .loading {
    text-align: center;
    padding: 60px 20px;
    color: var(--muted);
    font-size: 0.85rem;
    letter-spacing: 2px;
  }
  .loading-dot {
    display: inline-block;
    width: 8px; height: 8px;
    border-radius: 50%;
    background: var(--accent);
    margin: 0 3px;
    animation: bounce 1.2s infinite;
    box-shadow: 0 0 8px var(--accent-glow);
  }
  .loading-dot:nth-child(2) { animation-delay: 0.2s; }
  .loading-dot:nth-child(3) { animation-delay: 0.4s; }
  @keyframes bounce {
    0%, 80%, 100% { transform: scale(0.6); opacity: 0.5; }
    40% { transform: scale(1.1); opacity: 1; }
  }

  @media (max-width: 600px) {
    .vouch-card .attachments a { max-width: 100%; }
  }
</style>
</head>
<body>
<div class="container">
  <div class="hero">
    <h1 class="hero-title"><span>F</span>added <span>V</span>ouches</h1>
    <p class="hero-badge">Customer Feedback</p>
    <div class="stats">
      <span>Total: <b id="total-count">0</b></span>
      <span>With images: <b id="img-count">0</b></span>
    </div>
    <div class="search-wrap">
      <input type="text" id="search" placeholder="??  Search vouches..." oninput="render()">
    </div>
  </div>

  <div class="vouch-list" id="vouch-list">
    <div class="loading">
      <span class="loading-dot"></span>
      <span class="loading-dot"></span>
      <span class="loading-dot"></span>
      <br><br>Loading vouches...
    </div>
  </div>

  <p class="footer">sablelight &copy; 2025</p>
</div>

<div class="lightbox" id="lightbox" onclick="this.classList.remove('open')">
  <img id="lb-img" src="" alt="" style="display:none">
  <video id="lb-vid" src="" controls style="display:none"></video>
</div>

<script>
let vouches = [];

async function load() {
  try {
    const r = await fetch('vouches.json');
    if (!r.ok) throw new Error('Not found');
    const d = await r.json();
    vouches = d.vouches || [];
  } catch (e) {
    document.getElementById('vouch-list').innerHTML = '<div class="empty"><h2>No vouches yet</h2><p>Be the first to leave one!</p></div>';
    return;
  }
  render();
}

function openLightbox(url, isVideo) {
  const lb = document.getElementById('lightbox');
  const img = document.getElementById('lb-img');
  const vid = document.getElementById('lb-vid');
  img.style.display = isVideo ? 'none' : 'block';
  vid.style.display = isVideo ? 'block' : 'none';
  if (isVideo) { vid.src = url; vid.play(); }
  else { img.src = url; }
  lb.classList.add('open');
}

function render() {
  const q = document.getElementById('search').value.toLowerCase();
  const list = document.getElementById('vouch-list');

  let filtered = vouches;
  if (q) {
    filtered = vouches.filter(v =>
      (v.author?.name || '').toLowerCase().includes(q) ||
      (v.target?.name || '').toLowerCase().includes(q) ||
      (v.content || '').toLowerCase().includes(q)
    );
  }

  if (!filtered.length) {
    list.innerHTML = '<div class="empty"><h2>No matches</h2><p>Try a different search term.</p></div>';
    updateStats();
    return;
  }

  list.innerHTML = filtered.map(v => {
    let attachments = '';
    if (v.attachments && v.attachments.length) {
      attachments = '<div class="attachments">' +
        v.attachments.map(a => {
          const u = a.url || a;
          const isImg = a.type === 'image' || /\.(png|jpg|jpeg|gif|webp|bmp)(\?.*)?$/i.test(u);
          const isVid = a.type === 'video' || /\.(mp4|webm|mov|avi)(\?.*)?$/i.test(u);
          if (isImg) return '<a href="javascript:openLightbox(\'' + u.replace(/'/g,"\\'") + '\',false)"><img src="' + u + '" loading="lazy" alt="Attachment"></a>';
          if (isVid) return '<a href="javascript:openLightbox(\'' + u.replace(/'/g,"\\'") + '\',true)"><video src="' + u + '" preload="metadata"></video></a>';
          return '<a class="file-link" href="' + u + '" target="_blank" rel="noopener">' + (a.filename || 'Download') + ' ↗</a>';
        }).join('') + '</div>';
    }

    const target = v.target ? '<div class="target">' + esc(v.target.name || 'User') + '</div>' : '';
    const issueLink = v.issue_url
      ? '<a class="issue-link" href="' + v.issue_url + '" target="_blank" rel="noopener">View on GitHub ↗</a>'
      : '';

    return '<div class="vouch-card">' +
      '<div class="meta">' +
        '<span class="author">' + esc(v.author?.name || 'Anonymous') + ' <span class="badge">vouched</span></span>' +
        '<span class="date">' + (v.created_at || '') + '</span>' +
      '</div>' +
      target +
      '<div class="content">' + esc(v.content || '') + '</div>' +
      attachments + issueLink +
    '</div>';
  }).join('');

  updateStats();
}

function updateStats() {
  document.getElementById('total-count').textContent = vouches.length;
  document.getElementById('img-count').textContent = vouches.filter(v =>
    v.attachments && v.attachments.some(a => {
      const u = a.url || a;
      return /\.(png|jpg|jpeg|gif|webp)(\?.*)?$/i.test(u);
    })
  ).length;
}

function esc(s) {
  const d = document.createElement('div');
  d.textContent = s;
  return d.innerHTML;
}

load();
</script>
</body>
</html>"""


def parse_issue_body(body):
    data = {"author_id": None, "target_id": None, "content": "", "attachments": [], "created_at": ""}
    if not body:
        return data
    m = re.search(r'\*\*Vouched by:\*\*.*?`(\d+)`', body)
    if m:
        data["author_id"] = m.group(1)
    m = re.search(r'\*\*Vouched for:\*\*.*?`(\d+)`', body)
    if m:
        data["target_id"] = m.group(1)
    m = re.search(r'\*\*Reason:\*\*\s*(.*)', body)
    if m:
        data["content"] = m.group(1).strip()
    m = re.search(r'\*\*Date:\*\*\s*(.*)', body)
    if m:
        data["created_at"] = m.group(1).strip()
    attachment_urls = re.findall(r'!\[(.*?)\]\((.*?)\)|-\s+\[(.*?)\]\((.*?)\)', body)
    for m in attachment_urls:
        if m[1]:
            data["attachments"].append({"type": "image", "url": m[1], "filename": m[0]})
        elif m[3]:
            fname = m[2]
            url = m[3]
            is_vid = bool(re.search(r'\.(mp4|webm|mov|avi)(\?.*)?$', url.lower()))
            data["attachments"].append({"type": "video" if is_vid else "file", "url": url, "filename": fname})
    return data


class Vouches(commands.Gear):
    def __init__(self, bot):
        self.bot = bot
        self.token = os.getenv("GITHUB_TOKEN")
        self.repo = os.getenv("GITHUB_REPO")
        self._session = None

    @property
    def db(self) -> Database:
        return self.bot.db

    async def _get_session(self):
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session

    async def _gh(self, method, path, **kwargs):
        s = await self._get_session()
        headers = {
            "Authorization": f"Bearer {self.token}",
            "User-Agent": "stoat-bot",
            "Accept": "application/vnd.github.v3+json",
        }
        if "headers" in kwargs:
            headers.update(kwargs.pop("headers"))
        url = f"{GITHUB_API}/{path}"
        async with s.request(method, url, headers=headers, **kwargs) as resp:
            if resp.status >= 400:
                text = await resp.text()
                log.error(f"GitHub API {resp.status} on {method} {path}: {text[:500]}")
                return None
            if resp.status in (204, 201):
                try:
                    return await resp.json()
                except Exception:
                    return True
            return await resp.json()

    async def _upload_attachment(self, file_data, filename):
        safe = re.sub(r'[^a-zA-Z0-9._-]', '_', filename)
        path = f"attachments/{int(datetime.now(timezone.utc).timestamp())}_{safe}"
        encoded = base64.b64encode(file_data).decode()
        body = {"message": f"Upload vouch attachment: {safe}", "content": encoded}
        result = await self._gh("PUT", f"repos/{self.repo}/contents/{path}", json=body)
        if result and "content" in result:
            return result["content"]["download_url"]
        return None

    async def _create_issue(self, title, body, labels=None):
        data = {"title": title, "body": body}
        if labels:
            data["labels"] = labels
        return await self._gh("POST", f"repos/{self.repo}/issues", json=data)

    async def _close_issue(self, issue_number):
        return await self._gh("PATCH", f"repos/{self.repo}/issues/{issue_number}",
                               json={"state": "closed"})

    async def _list_issues(self, labels=None, state="open", per_page=100):
        params = {"state": state, "per_page": str(per_page)}
        if labels:
            params["labels"] = labels
        qs = "&".join(f"{k}={v}" for k, v in params.items())
        result = await self._gh("GET", f"repos/{self.repo}/issues?{qs}")
        return result if isinstance(result, list) else []

    async def _get_file_sha(self, path):
        result = await self._gh("GET", f"repos/{self.repo}/contents/{path}")
        if result and "sha" in result:
            return result["sha"]
        return None

    async def _push_json_file(self, content, message="Update vouches data"):
        """Push/update vouches.json in the repo."""
        encoded = base64.b64encode(json.dumps(content, indent=2).encode()).decode()
        sha = await self._get_file_sha("vouches.json")
        body = {"message": message, "content": encoded}
        if sha:
            body["sha"] = sha
        return await self._gh("PUT", f"repos/{self.repo}/contents/vouches.json", json=body)

    async def _push_html_file(self, content, message="Update website"):
        """Push/update index.html in the repo."""
        encoded = base64.b64encode(content.encode()).decode()
        sha = await self._get_file_sha("index.html")
        body = {"message": message, "content": encoded}
        if sha:
            body["sha"] = sha
        return await self._gh("PUT", f"repos/{self.repo}/contents/index.html", json=body)

    async def _enable_pages(self):
        """Enable GitHub Pages on the repo if not already enabled."""
        site = await self._gh("GET", f"repos/{self.repo}/pages")
        if site is None:
            body = {"source": {"branch": "main", "path": "/"}}
            return await self._gh("POST", f"repos/{self.repo}/pages", json=body)
        return site

    async def _build_vouches_json(self, issues):
        """Convert a list of GitHub issues into the vouches.json structure."""
        vouches_list = []
        for issue in issues:
            body = issue.get("body", "")
            parsed = parse_issue_body(body)
            entry = {
                "id": issue["number"],
                "author": {
                    "id": parsed.get("author_id"),
                    "name": issue["user"]["login"] if issue.get("user") else "Unknown",
                },
                "content": parsed.get("content", ""),
                "attachments": parsed.get("attachments", []),
                "issue_url": issue["html_url"],
                "created_at": parsed.get("created_at") or issue.get("created_at", ""),
            }
            target_id = parsed.get("target_id")
            if target_id:
                entry["target"] = {"id": target_id, "name": f"User {target_id}"}
            if entry["content"] or entry["attachments"]:
                vouches_list.append(entry)
        return {"vouches": vouches_list}

    async def _push_vouch_and_site(self, ctx, issues):
        """Rebuild vouches.json from issues and push, then return the site URL."""
        data = await self._build_vouches_json(issues)
        await self._push_json_file(data, "Rebuild vouches from issues")
        site_data = await self._enable_pages()
        site_url = None
        if site_data and isinstance(site_data, dict):
            site_url = site_data.get("html_url")
        return site_url

    # ── Commands ──────────────────────────────────────────────────────────

    @commands.group(invoke_without_command=True)
    async def vouch(self, ctx, *, reason: str = None):
        """Leave a vouch. !vouch @user reason (attachments supported)."""
        cfg = await self.db.get_guild_config(ctx.server.id)
        buyer_role = cfg.get("buyer_role")
        if buyer_role:
            has_role = buyer_role in [r.id for r in ctx.author.roles]
            is_staff_user = ctx.author.id == ctx.server.owner_id
            if not has_role and not is_staff_user:
                for key in ("staff_role", "mod_role"):
                    rid = cfg.get(key)
                    if rid and rid in [r.id for r in ctx.author.roles]:
                        is_staff_user = True
                        break
            if not has_role and not is_staff_user:
                return await ctx.send(embeds=[error_embed("Permission Denied",
                    "You need the buyer role to use this command.")])

        if not reason and not ctx.message.attachments:
            return await ctx.send(embeds=[error_embed("Missing Info",
                "Usage: `!vouch @user What they bought` with optional attachments.")])

        target_id = None
        target_name = None
        vouch_text = reason or ""

        mentions = getattr(ctx.message, "mentions", [])
        if mentions:
            target = mentions[0]
            target_id = target.id
            target_name = target.name
            vouch_text = vouch_text.replace(target.mention, "").strip()

        if not vouch_text and not ctx.message.attachments:
            return await ctx.send(embeds=[error_embed("Missing Info",
                "Please add what you're vouching for or attach files.")])

        attachment_urls = []
        for att in (ctx.message.attachments or []):
            try:
                async with aiohttp.ClientSession() as s:
                    async with s.get(att.url) as resp:
                        if resp.status == 200:
                            data = await resp.read()
                            url = await self._upload_attachment(data, att.filename or "file")
                            if url:
                                attachment_urls.append(url)
            except Exception as e:
                log.warning(f"Failed to upload attachment {att.filename}: {e}")

        author_name = ctx.author.name
        issue_title = f"Vouch for {target_name}" if target_id else f"Vouch by {author_name}"

        body_parts = [f"**Vouched by:** {ctx.author.mention} (`{ctx.author.id}`)"]
        if target_id:
            body_parts.append(f"**Vouched for:** {target.mention} (`{target_id}`)")
        body_parts.append(f"**Reason:** {vouch_text}")
        body_parts.append(f"**Date:** {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")
        if attachment_urls:
            body_parts.append("\n**Attachments:**")
            for u in attachment_urls:
                if any(u.lower().endswith(ext) for ext in (".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp")):
                    body_parts.append(f"![{os.path.basename(u)}]({u})")
                else:
                    body_parts.append(f"- [{os.path.basename(u)}]({u})")

        issue_body = "\n".join(body_parts)
        issue = await self._create_issue(issue_title, issue_body, labels=["vouch"])
        if not issue:
            return await ctx.send(embeds=[error_embed("Error", "Failed to create GitHub issue.")])

        record = await self.db.add_vouch(
            guild_id=ctx.server.id,
            author_id=ctx.author.id,
            target_id=target_id,
            content=vouch_text,
            attachments=attachment_urls,
            issue_number=issue["number"]
        )
        await self.db.update_vouch_message(record["id"], ctx.channel.id, str(ctx.message.id))

        all_issues = await self._list_issues(labels="vouch", per_page=100)
        site_url = await self._push_vouch_and_site(ctx, all_issues) if all_issues else None

        vouch_link = f"https://github.com/{self.repo}/issues/{issue['number']}"
        desc = f"✅ Vouch #{issue['number']} recorded!"
        if attachment_urls:
            desc += f"\n📎 {len(attachment_urls)} file(s) uploaded"
        desc += f"\n🔗 [View on GitHub]({vouch_link})"
        if site_url:
            desc += f"\n🌐 [View on Website]({site_url})"

        await ctx.send(embeds=[success_embed(
            f"Vouch for {target_name if target_id else author_name}",
            desc
        )])

    @vouch.command()
    @is_staff()
    async def role(self, ctx, role_id: str = None):
        """Set the buyer role allowed to use !vouch. !vouch role @Role or role_id."""
        if not role_id:
            cfg = await self.db.get_guild_config(ctx.server.id)
            current = cfg.get("buyer_role")
            if current:
                await ctx.send(embeds=[info_embed("Buyer Role",
                    f"Current buyer role: <@&{current}> (`{current}`)\n"
                    "To change it: `!vouch role @NewRole` or `!vouch role role_id`")])
            else:
                await ctx.send(embeds=[info_embed("Buyer Role",
                    "No buyer role set. Usage: `!vouch role @Role` or `!vouch role role_id`")])
            return
        clean = role_id.strip("<@&>")
        await self.db.set_guild_config(ctx.server.id, buyer_role=clean)
        await ctx.send(embeds=[success_embed("Buyer Role Set",
            f"Buyer role set to <@&{clean}>. Only members with this role can use `!vouch`.")])

    @vouch.command()
    @is_staff()
    async def remove(self, ctx, issue_number: int):
        """Remove a vouch by issue number. Closes the GitHub issue + rebuilds site."""
        issue = await self._get_issue(issue_number)
        if not issue:
            return await ctx.send(embeds=[error_embed("Not Found",
                f"No issue #{issue_number} found on GitHub.")])

        await self._close_issue(issue_number)

        vouches = await self.db.get_vouches_by_issue(issue_number)
        for v in vouches:
            await self.db._exec("DELETE FROM vouches WHERE id=?", (v["id"],))

        all_issues = await self._list_issues(labels="vouch", per_page=100)
        site_url = await self._push_vouch_and_site(ctx, all_issues) if all_issues else None

        msg = f"✅ Vouch #{issue_number} removed (issue closed)."
        if site_url:
            msg += f"\n🌐 Site updated: {site_url}"
        await ctx.send(embeds=[success_embed("Vouch Removed", msg)])

    @vouch.command()
    @is_staff()
    async def restore(self, ctx, count: int = 100):
        """Rebuild vouches.json from GitHub Issues and post in this channel."""
        issues = await self._list_issues(labels="vouch", per_page=min(count, 100))
        if not issues:
            return await ctx.send(embeds=[info_embed("No Issues", "No vouch issues found on GitHub.")])

        site_url = await self._push_vouch_and_site(ctx, issues)
        posted = 0
        for issue in reversed(issues):
            try:
                desc = issue.get("body", "No content")[:2000]
                await ctx.send(embeds=[stoat.SendableEmbed(
                    title=issue["title"],
                    description=desc,
                    color="#57F287",
                    url=issue["html_url"],
                )])
                posted += 1
            except Exception as e:
                log.warning(f"Failed to post issue #{issue['number']}: {e}")

        msg = f"Posted **{posted}** vouch(es) from GitHub."
        if site_url:
            msg += f"\n🌐 Website: {site_url}"
        await ctx.send(embeds=[success_embed("Restore Complete", msg)])

    @vouch.command()
    @is_staff()
    async def site(self, ctx):
        """Deploy or update the GitHub Pages website for vouches."""
        status_msg = await ctx.send(embeds=[info_embed("Deploying", "Setting up the vouch website...")])

        result = await self._push_html_file(SITE_HTML, "Deploy vouch website")
        if not result:
            return await status_msg.edit(embeds=[error_embed("Error", "Failed to push index.html")])

        site = await self._enable_pages()
        site_url = site.get("html_url") if site and isinstance(site, dict) else None

        issues = await self._list_issues(labels="vouch", per_page=100)
        if issues:
            await self._push_vouch_and_site(ctx, issues)

        desc = "✅ Website deployed!"
        if site_url:
            desc += f"\n🌐 {site_url}"
        desc += "\n\nIt may take a minute or two for GitHub Pages to go live."
        await status_msg.edit(embeds=[success_embed("Vouch Website", desc)])

    @commands.command()
    async def vouches(self, ctx, member: stoat.Member = None):
        """Show recent vouches from local DB."""
        if member:
            records = await self.db.get_vouches_by_author(ctx.server.id, member.id)
        else:
            records = await self.db.get_all_vouches(ctx.server.id)
        if not records:
            return await ctx.send(embeds=[info_embed("No Vouches", "No vouches found.")])
        lines = []
        for r in records[:10]:
            line = f"**#{r['issue_number']}** — {r['content'][:80]}"
            if r.get("target_id"):
                line += f" → <@{r['target_id']}>"
            line += f" — <@{r['author_id']}>"
            lines.append(line)
        title = f"Recent Vouches ({len(records)} total)"
        await ctx.send(embeds=[info_embed(title, "\n".join(lines))])


async def setup(bot):
    token = os.getenv("GITHUB_TOKEN")
    repo = os.getenv("GITHUB_REPO")
    if not token or not repo:
        log.warning("GITHUB_TOKEN or GITHUB_REPO not set — vouch cog not loaded")
        return
    await bot.add_gear(Vouches(bot))
