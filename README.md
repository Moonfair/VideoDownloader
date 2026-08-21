# VideoDownloader

A static task workbench plus a self-contained Agent Skill for public Weibo and Bilibili videos.

## Web app

Open `web/index.html`, or use the GitHub Pages deployment. The static app detects supported links, configures resolve/download and Bilibili page options, exports `integrated-video-downloader.task.v1` JSON, generates portable commands, and renders Agent JSON results.

The browser app does not pretend to bypass cross-origin or visitor-page restrictions. Media resolution and file writes belong to the Agent Skill.

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

The upstream `imfenghuang/WeiboVideoDownloader` repository has no declared license, so its adapted implementation is not redistributed here. The public skill instead asks a trusted Agent browser to read the public page's `video.currentSrc`, then downloads only validated official Weibo CDN URLs. It never reads or transmits browser cookies or login state.

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
