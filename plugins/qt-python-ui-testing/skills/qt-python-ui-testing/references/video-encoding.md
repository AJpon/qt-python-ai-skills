# Encoding a PNG Storyboard to Video

Not part of the default workflow — `record_steps()`'s numbered PNG sequence
is the intended output for reviewing an interaction. Reach for this only when
a video/GIF deliverable is explicitly requested; don't add a video/GIF
Python dependency for it, `ffmpeg` (external tool, not a project dependency)
covers it.

SKILL.md's `allowed-tools: Bash(uv *)` only pre-approves `uv`-prefixed Bash
calls for the invoking turn — it doesn't block anything else, it just means a
direct `ffmpeg ...` call below goes through the normal permission flow
(prompt, or whatever your global settings allow) instead of skipping it.

## Recipe

1. `record_steps()` already numbers files with a zero-padded prefix
   (`0000-initial.png`, `0001-loaded.png`, ...), but the trailing label
   differs per step, so `ffmpeg`'s `%04d` pattern can't match the whole
   filename directly. Normalize to a strictly sequential name first:

   ```python
   import shutil, pathlib
   src = pathlib.Path("captures")
   for old in src.glob("frame_*.png"):  # drop any frame_*.png from a prior run first —
       old.unlink()                     # otherwise they get picked up by the glob below
   for i, f in enumerate(sorted(src.glob("*.png"))):
       shutil.copy(f, src / f"frame_{i:04d}.png")
   ```

2. Encode:

   ```bash
   ffmpeg -y -framerate 12 -i captures/frame_%04d.png \
     -c:v libx264 -pix_fmt yuv420p -vf "scale=960:-2" -crf 26 -preset slow \
     out.mp4
   ```

   `-pix_fmt yuv420p` matters for broad player compatibility (browsers,
   `<video>` tags); without it some players show a black frame. `scale=960:-2`
   keeps the file small for embedding; drop it to keep original resolution.

## Gotcha: `-pattern_type glob` isn't universal

`ffmpeg -pattern_type glob -i "captures/*.png"` avoids the renumbering step
above, but not every Windows `ffmpeg` build supports it — the gyan.dev
"full_build" (a common Windows distribution) fails with `Pattern type 'glob'
was selected but globbing is not supported by this libavformat build`. The
sequential `frame_%04d.png` + plain `-i` approach in the recipe above works
everywhere; treat `-pattern_type glob` as an optimization to try, not
something to depend on.

## Embedding in an HTML artifact

For a self-contained page (e.g. a Claude Artifact), base64-encode the mp4
into a `data:` URI rather than linking it — external file URLs aren't loaded
in that sandbox:

```python
import base64, pathlib
video_b64 = base64.b64encode(pathlib.Path("out.mp4").read_bytes()).decode("ascii")
```

```html
<video controls muted loop playsinline>
  <source src="data:video/mp4;base64,BASE64_HERE" type="video/mp4">
</video>
```

A short interaction sequence (tens of frames, 12 fps, `crf 26`) typically
encodes to tens-of-KB, well within the artifact size budget even after
base64's ~33% overhead.
