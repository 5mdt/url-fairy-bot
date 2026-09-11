# Features to add

New, not-yet-built behavior — ideas not yet promoted to a feature doc. Cleanups, defects, and
missing coverage on already-shipped behavior go in `docs/BUGS.md` instead. Remove a line once
it's promoted to a feature doc (`docs/features/<PREFIX>-NNNN-slug.md` + `docs/FRD.md`).

- Detect and normalize near-silent audio in downloads: some TikTok videos have a technically valid
  audio stream (passes a plain "audio present" check) that's ~35 dB quieter than normal —
  confirmed (2026-09-10) across h264/h265/mp3-"original sound"/watermarked variants, both mobile
  API hosts, and TikTok's own in-app "Save", so it's baked into the source, not an artifact of a
  particular extraction path; the app itself audibly compensates for it, the downloaded file
  doesn't. Example: https://www.tiktok.com/@kaniakoroomminimalist/video/7682574621010398472
  measured −50.9 LUFS / RMS −52.5 dB vs. −15 LUFS / RMS −18 dB for a normal clip. Fix is
  `ffmpeg -i in.mp4 -c:v copy -af loudnorm=I=-16:TP=-1.5:LRA=11 -c:a aac -b:a 160k out.mp4` (no
  video re-encode needed; two-pass loudnorm — measure first, then pass `measured_*`/`linear=true`
  — gives a more predictable result via constant gain instead of dynamic processing when the
  measured parameters allow it). A loudness check (e.g. below −40 LUFS) could flag which downloads
  need it.
