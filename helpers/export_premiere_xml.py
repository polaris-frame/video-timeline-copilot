from __future__ import annotations

import argparse
from fractions import Fraction
import math
from pathlib import Path
import subprocess
import xml.etree.ElementTree as ET

from helpers.common import ensure_within, read_json, resolve_relative, safe_filename
from helpers.export_fcpxml import fps_fraction, load_media_index
from helpers.inventory import ffprobe
from helpers.timecode import timecode_to_seconds
from helpers.timing import range_effective_speed, range_playback_speed
from helpers.validate_edl import minimum_clip_duration, validate


def frame_rate(value: str | float | int) -> Fraction:
    """Accept ffprobe rationals and conventional decimal NTSC aliases."""
    raw = Fraction(str(value))
    if raw <= 0:
        raise ValueError("frame rate must be positive")
    rate = fps_fraction(float(raw))
    nominal = round(float(rate))
    if rate not in (Fraction(nominal), Fraction(nominal * 1000, 1001)):
        raise ValueError(f"XMEML cannot represent frame rate {value}")
    return rate


def frames(seconds: float | str, rate: Fraction) -> int:
    return round(Fraction(str(seconds)) * rate)


def add(parent: ET.Element, tag: str, value: object) -> ET.Element:
    element = ET.SubElement(parent, tag)
    element.text = str(value)
    return element


def add_rate(parent: ET.Element, rate: Fraction) -> None:
    element = ET.SubElement(parent, "rate")
    add(element, "timebase", round(float(rate)))
    add(element, "ntsc", "FALSE" if rate.denominator == 1 else "TRUE")


def video_format(parent: ET.Element, rate: Fraction, info: dict) -> None:
    sample = ET.SubElement(parent, "samplecharacteristics")
    add_rate(sample, rate)
    for key in ("width", "height"):
        add(sample, key, info[key])
    add(sample, "anamorphic", "FALSE")
    add(sample, "pixelaspectratio", "square")
    add(sample, "fielddominance", "none")


def metadata(path: Path, cached: dict | None) -> dict:
    required = ("duration", "width", "height", "avg_frame_rate", "audio_channels", "audio_rate")
    info = dict(cached or {})
    if not all(info.get(key) is not None for key in required) or info.get("error"):
        info = ffprobe(path)
    try:
        info["rate"] = frame_rate(info["avg_frame_rate"])
        duration = float(info["duration"])
        if not math.isfinite(duration) or duration <= 0:
            raise ValueError("duration must be positive and finite")
        for key in ("width", "height", "audio_channels", "audio_rate"):
            value = int(info[key])
            if value != float(info[key]) or value < 0:
                raise ValueError(f"invalid {key}")
            info[key] = value
        if not info["width"] or not info["height"]:
            raise ValueError("video dimensions must be positive")
        if info["audio_channels"] and not info["audio_rate"]:
            raise ValueError("audio sample rate must be positive")
    except (KeyError, TypeError, ValueError, ZeroDivisionError) as exc:
        raise ValueError(f"Invalid media metadata for {path}: {exc}") from exc
    info["duration_frames"] = frames(duration, info["rate"])
    return info


def add_file(parent: ET.Element, file_id: str, path: Path, info: dict, defined: set[str]) -> None:
    file = ET.SubElement(parent, "file", {"id": file_id})
    if file_id in defined:
        return
    defined.add(file_id)
    add(file, "name", path.name)
    add(file, "pathurl", path.resolve().as_uri())
    add_rate(file, info["rate"])
    add(file, "duration", info["duration_frames"])
    timecode = info.get("start_timecode")
    if timecode:
        rate = frame_rate(info.get("timecode_rate") or info["avg_frame_rate"])
        if rate != info["rate"]:
            raise ValueError(f"Timecode rate differs from video rate: {path}")
        drop = ";" in timecode or "." in timecode
        if drop and rate not in (Fraction(30000, 1001), Fraction(60000, 1001)):
            raise ValueError(f"Invalid drop-frame timecode rate: {path}")
        if drop:
            parts = timecode.replace(";", ":").replace(".", ":").split(":")
            _, minute, second, frame = map(int, parts)
            if minute % 10 and second == 0 and frame < round(float(rate) * 0.0666666667):
                raise ValueError(f"Invalid dropped timecode label: {timecode}")
        tc = ET.SubElement(file, "timecode")
        add_rate(tc, rate)
        add(tc, "string", timecode)
        add(tc, "frame", frames(timecode_to_seconds(timecode, str(rate)), rate))
        add(tc, "displayformat", "DF" if drop else "NDF")
    media = ET.SubElement(file, "media")
    video_format(ET.SubElement(media, "video"), info["rate"], info)
    if info["audio_channels"]:
        audio = ET.SubElement(media, "audio")
        sample = ET.SubElement(audio, "samplecharacteristics")
        add(sample, "samplerate", info["audio_rate"])
        add(audio, "channelcount", info["audio_channels"])


def build_premiere_xml(edl_path: Path) -> ET.ElementTree:
    edl_path = edl_path.resolve()
    errors = validate(edl_path, check_timing=False)
    if errors:
        raise ValueError("EDL validation failed: " + "; ".join(errors))
    edl = read_json(edl_path)
    root_dir = edl_path.parent.parent
    rate = frame_rate(edl["fps"])
    cache = load_media_index(edl_path.parent, root_dir)
    root = ET.Element("xmeml", {"version": "5"})
    project = ET.SubElement(root, "project")
    add(project, "name", edl["project_name"])
    children = ET.SubElement(project, "children")
    assets: dict[Path, tuple[str, dict]] = {}
    defined: set[str] = set()
    for ti, timeline in enumerate(edl["timelines"], 1):
        if timeline.get("transform") or timeline.get("visual_layers"):
            raise ValueError("Premiere XML does not yet support timeline transforms/visual layers")
        width, height = timeline["resolution"]
        if any(int(v) != v or int(v) <= 0 for v in (width, height)):
            raise ValueError("Timeline resolution must contain positive integers")
        sequence = ET.SubElement(children, "sequence", {"id": f"sequence-{ti}", "explodedTracks": "true"})
        add(sequence, "name", timeline.get("name", f"Timeline {ti}"))
        duration_element = add(sequence, "duration", 0)
        add_rate(sequence, rate)
        tc = ET.SubElement(sequence, "timecode")
        add_rate(tc, rate)
        add(tc, "string", "00:00:00:00")
        add(tc, "frame", 0)
        add(tc, "displayformat", "NDF")
        media = ET.SubElement(sequence, "media")
        video = ET.SubElement(media, "video")
        video_format(ET.SubElement(video, "format"), rate, {"width": width, "height": height})
        video_track = ET.SubElement(video, "track")
        audio = ET.SubElement(media, "audio")
        add(audio, "numOutputChannels", 2)
        sample = ET.SubElement(ET.SubElement(audio, "format"), "samplecharacteristics")
        add(sample, "samplerate", 48000)
        outputs = ET.SubElement(audio, "outputs")
        for channel in (1, 2):
            group = ET.SubElement(outputs, "group")
            add(group, "index", channel)
            add(group, "numchannels", 1)
            add(group, "downmix", 0)
            add(ET.SubElement(group, "channel"), "index", channel)
        audio_tracks: list[ET.Element] = []
        track_groups: dict[str, list[tuple[ET.Element, int]]] = {}
        cursor = Fraction(0)
        frame_cursor = Fraction(0)
        previous_end = 0
        ordered = sorted(timeline["ranges"], key=lambda item: float(item.get("record_start", 0)))
        for ri, item in enumerate(ordered, 1):
            if abs(range_effective_speed(item) - 1) > 1e-9 or abs(range_playback_speed(item) - 1) > 1e-9:
                raise ValueError("Premiere XML does not yet support retimed ranges")
            if item.get("transform") or item.get("visual_layers") or item.get("audio"):
                raise ValueError("Premiere XML does not yet support transforms, visual layers or audio overrides")
            if item.get("track", 1) != 1:
                raise ValueError("Premiere XML currently supports video track 1 only")
            path = ensure_within(resolve_relative(timeline["sources"][item["source"]], root_dir), root_dir)
            if path not in assets:
                assets[path] = (f"file-{len(assets) + 1}", metadata(path, cache.get(path)))
            file_id, info = assets[path]
            start_seconds = Fraction(str(item.get("record_start", cursor)))
            # Explicit positions may describe the original seconds-based EDL or
            # the already quantized timeline. Preserve contiguity in either case.
            if "record_start" in item and round(start_seconds * rate) not in (round(cursor * rate), previous_end):
                raise ValueError("Ranges must be contiguous and nonempty at the exact sequence frame rate")
            source_in = frames(item["source_start"], info["rate"])
            source_out = frames(item["source_end"], info["rate"])
            if source_in < 0 or source_out <= source_in or source_out > info["duration_frames"]:
                raise ValueError(f"Source range is outside media duration: {path}")
            # Source endpoints define the available frames. Equal rates must
            # retain exactly that length; mixed rates convert the rational span.
            frame_cursor += Fraction(source_out - source_in) * rate / info["rate"]
            start, end = previous_end, round(frame_cursor)
            minimum = minimum_clip_duration(edl)
            if end - start < max(1, frames(minimum, rate)):
                raise ValueError(f"Range is shorter than the minimum {minimum}s")
            stereo = info["audio_channels"] == 2
            layout = "stereo" if stereo else "mono"
            group_tracks = track_groups.setdefault(layout, [])
            while len(group_tracks) < info["audio_channels"]:
                index = len(group_tracks)
                track = ET.SubElement(audio, "track", {
                    "currentExplodedTrackIndex": str(index if stereo else 0),
                    "totalExplodedTrackCount": "2" if stereo else "1",
                    "premiereTrackType": "Stereo" if stereo else "Mono",
                })
                add(track, "outputchannelindex", index + 1 if stereo else 1)
                audio_tracks.append(track)
                group_tracks.append((track, len(audio_tracks)))
            entries = [(video_track, "video", 1, 1)] + [
                (track, "audio", ch, track_index)
                for ch, (track, track_index) in enumerate(group_tracks[:info["audio_channels"]], 1)
            ]
            refs = [(f"clip-{ti}-{ri}-{kind}-{ch}", kind, track_index, len(track.findall("clipitem")) + 1)
                    for track, kind, ch, track_index in entries]
            for (track, kind, ch, _), (clip_id, _, _, _) in zip(entries, refs):
                attributes = {"id": clip_id}
                if kind == "audio":
                    attributes["premiereChannelType"] = "stereo" if stereo else "mono"
                clip = ET.SubElement(track, "clipitem", attributes)
                add(clip, "name", path.name)
                add(clip, "enabled", "TRUE")
                add(clip, "duration", info["duration_frames"])
                add_rate(clip, info["rate"])
                for key, value in (("start", start), ("end", end), ("in", source_in), ("out", source_out)):
                    add(clip, key, value)
                add_file(clip, file_id, path, info, defined)
                source = ET.SubElement(clip, "sourcetrack")
                add(source, "mediatype", kind)
                add(source, "trackindex", ch)
                for ref, ref_kind, ref_ch, clip_index in refs:
                    link = ET.SubElement(clip, "link")
                    for key, value in (("linkclipref", ref), ("mediatype", ref_kind), ("trackindex", ref_ch), ("clipindex", clip_index)):
                        add(link, key, value)
                    if ref_kind == "audio" and info["audio_channels"] == 2:
                        add(link, "groupindex", 1)
            cursor += Fraction(str(item["source_end"])) - Fraction(str(item["source_start"]))
            previous_end = end
        duration_element.text = str(previous_end)
        for track in [video_track, *audio_tracks]:
            add(track, "enabled", "TRUE")
            add(track, "locked", "FALSE")
    ET.indent(root, space="  ")
    return ET.ElementTree(root)


def default_premiere_xml_path(edl_path: Path) -> Path:
    return edl_path.parent / f"{safe_filename(read_json(edl_path)['project_name'], 'timeline')}.premiere.xml"


def write_premiere_xml(edl_path: Path, out_path: Path) -> Path:
    tree = build_premiere_xml(edl_path)
    # Build before writing so failures never replace a previously valid export.
    out_path.parent.mkdir(parents=True, exist_ok=True)
    text = '<?xml version="1.0" encoding="utf-8"?>\n<!DOCTYPE xmeml>\n'
    text += ET.tostring(tree.getroot(), encoding="unicode")
    out_path.write_text(text, encoding="utf-8")
    return out_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Export Premiere Pro FCP7 XML (XMEML) from an EDL")
    parser.add_argument("edl", type=Path)
    parser.add_argument("--out", type=Path, help="Output .xml path (default: edit/<project>.premiere.xml)")
    args = parser.parse_args()
    edl_path = args.edl.resolve()
    try:
        result = write_premiere_xml(edl_path, args.out or default_premiere_xml_path(edl_path))
    except (ValueError, OSError, KeyError, TypeError, ZeroDivisionError, subprocess.CalledProcessError) as exc:
        parser.exit(2, f"Premiere XML export failed: {exc}\n")
    print(f"Premiere XML -> {result}")


if __name__ == "__main__":
    main()
