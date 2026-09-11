# Getting an `IV_RHASH` for Telegram Instant View

Operator runbook for
[UFB-0032](features/UFB-0032-telegram-instant-view-embeds.md).
Leave `IV_RHASH` unset and watch links still get Telegram's native
`og:video` link-preview player. Follow this guide only if you want true
Instant View instead.

## Overview

You create an Instant View template for your `BASE_URL` domain and Telegram
gives you the template's `rhash` as part of the editor's test link. A
`t.me/iv?url=...&rhash=...` link built from that `rhash` opens in Instant
View for anyone immediately — you do not need Telegram to publicly approve
the template first.

## Steps

1. Go to https://instantview.telegram.org/my (sign in with the Telegram
   account you'll manage the template with).
2. Click **Create a new template**.

   Check the **Global Templates** list first — many sites already have
   public templates. Forking a close match is usually faster than starting
   from scratch.
3. Enter the bundled example page as the sample URL:

   ```text
   https://<your-domain>/watch/sample.html
   ```

   This page is produced by the exact same renderer as a real
   `/watch/<file>.html` page (see
   [UFB-0033](features/UFB-0033-static-page-generation.md)), but points at a
   bundled sample clip (`app/assets/sample.mp4`, seeded to
   `/sample.mp4` at startup) instead of a cached download — so it can never
   drift from what a real page looks like, and stays available for
   editing/re-testing at any time between app restarts (see
   [BUGS.md, #BUG-0030](BUGS.md) for the one gap: a restart-free deployment
   running past `FILE_TTL` days loses it until the next restart).
4. Telegram fetches that page and opens the template editor. Map the tags
   with a short template:

   ```text
   ~version: "2.1"
   title: //meta[@property='og:title']/@content
   cover: /html/head/meta[@property="og:image"]/@content[string()]
   body: //body
   ```

   `cover` deliberately reads `og:image`, never the page's `<video>`
   element — a file over `INLINE_VIDEO_MAX_MB` has no `<video>` element at
   all ([UFB-0032](features/UFB-0032-telegram-instant-view-embeds.md)), and
   even below the threshold `og:image` is the right cover: it's the
   article's list thumbnail, not its body content. `og:image` is a per-file
   preview frame when one exists
   ([UFB-0035](features/UFB-0035-per-file-preview-images.md)), otherwise
   the bundled fallback — always present regardless of size. `[string()]`
   guards against ever treating an empty `content=""` as a match.

   The `~version` line matters: a template with no version pragma defaults
   to the long-deprecated `1.0` engine (the editor flags this with
   "Version 1.0 is outdated" in its footer), which is missing rule
   features later templates rely on.

   `title` and `body` are the two properties Instant View requires before it
   will render *any* preview — leaving either unset (or trying to set a
   nonexistent `video` field instead of `cover`) is why the editor shows "no
   instant preview available" instead of a preview.

   Don't add a `query { path: ... }` restriction: this domain only ever
   serves `/watch/*.html` pages (real downloads and the `sample.html`
   example alike), so a path filter buys nothing and, if scoped to
   `/watch/*` only, breaks
   testing outright — the sample page's path never matches it, so the
   rules above never run against it and Instant View has no `body` to
   render for the sample, no matter how the fields themselves are fixed.
   Also note `path` is a regular expression, not a glob — `/watch/*` matches
   "`/watch` + zero-or-more slashes", not "anything under `/watch/`"; you'd
   need `/watch/.*` for that.

   Refine using the live preview pane until `title`/`cover`/`body` resolve
   with no errors — but the preview pane itself never actually plays a
   `<video>`, it only shows a static frame. That's a limitation of the
   editor's browser preview, not a sign the template is wrong.
5. Click **Test IV link** (next to Publish/Save) to get a
   `t.me/iv?url=...&rhash=...` link, and open *that* in the real Telegram
   app (mobile or desktop) — this is the only way to confirm the video
   actually plays, since the browser preview pane can't play it. Once it
   looks right, **Publish**/**Save**. Telegram assigns the template a
   `rhash`, shown in the editor's URL bar or the same "Test IV link"
   button, e.g.:

   ```text
   https://t.me/iv?url=https%3A%2F%2Fyourdomain%2Fwatch%2Ffile.html&rhash=abcdef0123456789
   ```

6. Copy just the `rhash` value into your `.env`:

   ```dotenv
   IV_RHASH=abcdef0123456789
   ```

## Notes

- The `rhash` link works immediately for everyone, even while the template
  is still unapproved/pending Telegram's review — that's why `IV_RHASH` is
  usable without waiting on approval.
- If Telegram later approves the template publicly, plain links to your
  domain start auto-offering Instant View too, but `IV_RHASH` doesn't
  depend on that happening.
- No template created → leave `IV_RHASH` empty. The bot falls back to the
  plain `og:video` page, which still gets Telegram's native inline video
  player.
