# VideoDownloader

A static task workbench plus a self-contained Agent Skill for public Weibo and Bilibili videos.

## Web app

Open `web/index.html`, or use the GitHub Pages deployment. The static app detects supported links, configures resolve/download and Bilibili page options, exports `integrated-video-downloader.task.v1` JSON, generates portable commands, and renders Agent JSON results.

For direct browser downloads, clone the repository and start the standard-library local bridge:

```powershell
py -3 -S "agent-skill\integrated-video-downloader\scripts\server.py"
```

The service opens `http://127.0.0.1:8765/`. The published GitHub Pages app also detects this loopback service and enables the same direct-download button. No package installation is required.

GitHub Pages cannot resolve platform links by JavaScript alone because both platform APIs reject cross-origin browser requests. The local bridge keeps the interface in JavaScript while performing metadata requests and file streaming outside the browser CORS boundary.

## Agent Skill

The complete distributable skill is at `agent-skill/integrated-video-downloader/`. It uses only the Python standard library.

Run an exported task:

```powershell
py -3 -S "agent-skill\integrated-video-downloader\scripts\video_downloader.py" --task-file "<task.json>"
```

Resolve a Bilibili video:

```powershell
py -3 -S "agent-skill\integrated-video-downloader\scripts\video_downloader.py" "BV1xx411c7mD" --resolve-only
```

Install by copying or linking `agent-skill/integrated-video-downloader` into a supported personal skill root:

| Harness | Skill root |
| --- | --- |
| Claude | `~/.claude/skills/` |
| Codex | `~/.codex/skills/` |
| DeepSeek Harness | `~/.agents/skills/` |
| OpenClaw | `~/.agents/skills/` or `~/.openclaw/skills/` |

## Weibo boundary

The upstream `imfenghuang/WeiboVideoDownloader` repository has no declared license, so its adapted implementation is not redistributed here. The public skill instead asks a trusted Agent browser to read the public page's `video.currentSrc`, then downloads only validated official Weibo CDN URLs. A validated CDN URL can be pasted into the web app for direct browser download. The service never reads or transmits browser cookies or login state.

## GitHub Pages

`.github/workflows/pages.yml` runs JavaScript syntax checks and all offline Python tests before uploading only `web/` as the Pages artifact. In repository settings, the Pages source must be **GitHub Actions**. The expected project URL is:

`https://moonfair.github.io/VideoDownloader/`

## Development

```powershell
$env:PYTHONDONTWRITEBYTECODE = "1"
py -3.14 -S -m unittest discover -s agent-skill/integrated-video-downloader/tests -p "test_*.py" -v
node --check web/app.js
```

## License

Apache License 2.0. See `LICENSE` and `NOTICE`.
