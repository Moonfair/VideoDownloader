# Bilibili upstream provenance

- Repository: https://github.com/Henryhaohao/Bilibili_video_download
- Reviewed commit: `2e6035d2b2acdc188b713b17f1f9adf9cd5b4067`
- Upstream entry points reviewed: `bilibili_video_download_v1.py`,
  `bilibili_video_download_v3.py`, and `bilibili_video_download_bangumi.py`
- License: Apache License 2.0
- Review date: 2026-08-19

The local implementation is a substantial modernization for private Skill use. It
keeps the upstream project's BV/AV metadata, multi-page, referer-aware download, and
JSON play-url concepts while replacing the obsolete signed API, interactive prompts,
hard-coded SESSDATA, requests, moviepy, and imageio dependencies.

## Behavior changes

- Uses current public `view` and `playurl` endpoints without account cookies.
- Requests the highest anonymously available progressive stream and reports the
  actual quality returned by Bilibili.
- Supports BV, AV, `b23.tv`, one selected page, or all pages.
- Saves legacy multi-segment responses as separate files because no external FFmpeg
  dependency is bundled; it never performs an invalid byte concatenation.

