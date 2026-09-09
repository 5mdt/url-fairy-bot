# Features to add

New, not-yet-built behavior — ideas not yet promoted to a feature doc. Cleanups, defects, and
missing coverage on already-shipped behavior go in `docs/BUGS.md` instead. Remove a line once
it's promoted to a feature doc (`docs/features/<PREFIX>-NNNN-slug.md` + `docs/FRD.md`).

- Better `/watch/<file>` preview image: instead of the one static bundled `app/assets/preview.png`
  used for every file, generate a per-file preview — a frame extracted from the video, the source
  image itself, or a rendered card from title/text — for `og:image`
