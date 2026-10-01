# Premiere Pro FCP7 XML export

[日本語の詳しい使い方（Windows）](premiere-xml-ja.md)

```powershell
vtc inventory .\my-video
vtc export-premiere-xml .\my-video\edit\edl.json
# Optional destination:
vtc export-premiere-xml .\my-video\edit\edl.json --out .\my-video\edit\cut.xml
```

Default output: `edit/<project_name>.premiere.xml`. In Premiere Pro use
**File > Import** and select this `.xml` file. It contains one sequence per EDL
timeline. Source media must remain at the exported absolute paths; moving the
workspace requires regenerating XML or relinking media in Premiere.

This command exports Final Cut Pro 7 XML (`xmeml version="5"`), separately from
the existing `export-fcpxml` command, which continues to generate FCPXML 1.13.
No code from `premiere-agent` is included. Its README was consulted only for the
design of an EDL-to-XML handoff. The implementation uses Python's standard
library and the existing MIT-licensed project helpers, without new runtime
dependencies.

## Data and timing contract

- EDL version 1 is unchanged: global numeric `fps`, `timelines`, explicit
  timeline `resolution`, source IDs/paths, and ranges with `source_start`,
  `source_end`, and optional `record_start` in seconds.
- The footage root is the EDL's grandparent (normally `footage/edit/edl.json`).
  Relative source paths resolve against that root. Absolute paths are allowed
  inside it. Existing path containment and file-existence checks run first.
- `edit/media_index.json` supplies native duration, width, height,
  `avg_frame_rate`, `audio_channels`, and `audio_rate`. Missing records or
  incomplete records trigger the existing FFprobe inventory helper once per
  used file. Invalid complete metadata fails clearly instead of inventing it.
  Re-run inventory after replacing a source file: the cache does not detect
  changed files automatically.
- Decimal 23.976, 29.97 and 59.94 map to 24000/1001, 30000/1001 and 60000/1001.
  XMEML encodes these as integer `timebase` plus `ntsc=TRUE`. Other integer
  rates are supported; rates that XMEML cannot represent are rejected.
- Source `in`/`out` and media `duration` are in native source-rate frames.
  Sequence `start`/`end` and sequence `duration` are in sequence-rate frames.
  Endpoints use rational arithmetic with nearest-frame rounding (ties to even).
  Adjacent cuts share an endpoint; durations are not rounded and accumulated
  independently, so long NTSC timelines do not accumulate rounding drift.
- Embedded source timecode is file metadata. It does **not** offset EDL
  source trims, which remain relative to file frame zero. Drop-frame 29.97
  and 59.94 origins are supported independently of the sequence's NDF display.
- Native resolution and audio sample rate are preserved in file metadata.
  Sequence resolution comes from the EDL, and sequence audio uses 48 kHz.
  Each source audio channel becomes one audio clip/track, linked reciprocally
  to video and the other channels through unique `linkclipref` IDs and correct
  one-based track/clip indices. Silent sources create no audio clips.
- Absolute `file:` URIs use Windows drive/UNC handling and URL escaping from
  `pathlib`, including spaces, Japanese filenames, `#`, and XML metacharacters.

## Supported scope and verification

This backend is for contiguous cuts at normal speed on video track 1, including
mixed source FPS, mono/stereo/multichannel audio, silent clips, and multiple
sequences. It checks media bounds and minimum clip length before writing.
Failed generation leaves an existing XML untouched.

Retimes, transforms, visual layers, additional video tracks, and range audio
overrides fail with an explicit error. Subtitles remain separate SRT files;
editorial annotations/markers are not imported into the sequence. The inventory
helper currently describes the first video and first audio stream. For files
with multiple independent audio streams, select/remux the intended audio stream
before inventory. Variable-frame-rate footage should be converted to a constant
frame rate before use; this exporter works with the indexed average frame rate.

Automated tests cover XML generation, NTSC/mixed-rate timing, links, cache/probe
behavior, metadata, paths, source timecode, and preservation of existing FCPXML.
They do not launch Premiere. A successful automated run does not certify an
import in every Premiere version. For an application smoke test, import an XML
with real footage and check sequence FPS/resolution, source in/out, channel
mapping, Linked Selection, the final sequence frame, and audio sync at both the
start and end. Check stereo panning/multichannel routing in Premiere as part of
this review; the exporter preserves channel identities, not a custom mixer.

## References

- [Apple's XMEML encoding and linked clip documentation](https://developer.apple.com/library/archive/documentation/AppleApplications/Reference/FinalCutPro_XML/Basics/Basics.html)
- [Apple's XMEML element catalog](https://developer.apple.com/library/archive/documentation/AppleApplications/Reference/FinalCutPro_XML/Elements/Elements.html)
- [premiere-agent README (design reference only)](https://github.com/Kemerd/premiere-agent/blob/main/README.md)
