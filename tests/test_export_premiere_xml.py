from __future__ import annotations

from fractions import Fraction
from pathlib import Path
import json
import sys
import xml.etree.ElementTree as ET

import pytest

from helpers import export_premiere_xml as exporter
from helpers.cli import COMMANDS
from helpers.export_fcpxml import build_fcpxml


def workspace(tmp_path, *, fps=29.97, channels=2, source_fps="30000/1001", ranges=None):
    raw = tmp_path / "raw"
    edit = tmp_path / "edit"
    raw.mkdir()
    edit.mkdir()
    source = raw / "素材 & shot #1.mp4"
    source.touch()
    edl = {
        "version": 1, "project_name": "Premiere Test", "fps": fps,
        "timelines": [{"name": "Main", "resolution": [1920, 1080],
                       "sources": {"A": str(source)},
                       "ranges": ranges or [
                           {"source": "A", "source_start": 1, "source_end": 2, "record_start": 0},
                           {"source": "A", "source_start": 3, "source_end": 4, "record_start": 1},
                       ]}],
    }
    info = {"path": str(source), "duration": 120, "width": 3840, "height": 2160,
            "avg_frame_rate": source_fps, "audio_channels": channels,
            "audio_rate": 44100 if channels else 0}
    path = edit / "edl.json"
    path.write_text(json.dumps(edl), encoding="utf-8")
    (edit / "media_index.json").write_text(json.dumps({"media": [info]}), encoding="utf-8")
    return path, edl, info


def save(path, edl):
    path.write_text(json.dumps(edl), encoding="utf-8")


@pytest.mark.parametrize("fps,base,ntsc", [(23.976, 24, "TRUE"), (29.97, 30, "TRUE"),
                                          (59.94, 60, "TRUE"), (24, 24, "FALSE"),
                                          (25, 25, "FALSE"), (30, 30, "FALSE"), (60, 60, "FALSE")])
def test_sequence_rate_and_native_media_metadata(tmp_path, fps, base, ntsc):
    path, _, _ = workspace(tmp_path, fps=fps)
    root = exporter.build_premiere_xml(path).getroot()
    sequence = root.find("./project/children/sequence")
    assert sequence.findtext("rate/timebase") == str(base)
    assert sequence.findtext("rate/ntsc") == ntsc
    assert sequence.findtext("media/video/format/samplecharacteristics/width") == "1920"
    file = root.find(".//file")
    assert file.findtext("rate/timebase") == "30"
    assert file.findtext("rate/ntsc") == "TRUE"
    assert file.findtext("media/video/samplecharacteristics/width") == "3840"
    assert file.findtext("media/audio/samplecharacteristics/samplerate") == "44100"
    assert sequence.findtext("media/audio/format/samplecharacteristics/samplerate") == "48000"


def test_mixed_rates_use_source_in_out_and_sequence_positions(tmp_path):
    path, _, _ = workspace(tmp_path, fps=23.976, source_fps="60000/1001")
    clip = exporter.build_premiere_xml(path).find(".//video/track/clipitem")
    assert [clip.findtext(tag) for tag in ("start", "end", "in", "out")] == ["0", "24", "60", "120"]
    assert clip.findtext("rate/timebase") == "60"


@pytest.mark.parametrize("channels", [0, 1, 2, 6])
def test_all_channels_link_reciprocally_with_correct_indices(tmp_path, channels):
    path, _, _ = workspace(tmp_path, channels=channels)
    root = exporter.build_premiere_xml(path).getroot()
    clips = {clip.get("id"): clip for clip in root.findall(".//clipitem")}
    assert len(clips) == 2 * (channels + 1)
    for clip in clips.values():
        assert len(clip.findall("link")) == channels + 1
        for link in clip.findall("link"):
            linked = clips[link.findtext("linkclipref")]
            for tag in ("start", "end", "in", "out"):
                assert clip.findtext(tag) == linked.findtext(tag)
            sequence = root.find("./project/children/sequence")
            track = sequence.findall(f"media/{link.findtext('mediatype')}/track")[int(link.findtext("trackindex")) - 1]
            assert track.findall("clipitem")[int(link.findtext("clipindex")) - 1] is linked
    assert len(root.findall(".//file/pathurl")) == 1


def test_differing_channel_counts_keep_link_clipindex_correct(tmp_path):
    path, edl, info = workspace(tmp_path, channels=1)
    second = path.parent.parent / "raw" / "stereo.mp4"
    second.touch()
    edl["timelines"][0]["sources"]["B"] = str(second)
    edl["timelines"][0]["ranges"][1]["source"] = "B"
    save(path, edl)
    other = dict(info, path=str(second), audio_channels=2)
    (path.parent / "media_index.json").write_text(json.dumps({"media": [info, other]}))
    clip = exporter.build_premiere_xml(path).findall(".//video/track/clipitem")[1]
    assert clip.findall("link")[-1].findtext("clipindex") == "1"


def test_encoded_windows_uri_and_xml_roundtrip(tmp_path):
    path, _, _ = workspace(tmp_path)
    output = exporter.default_premiere_xml_path(path)
    exporter.write_premiere_xml(path, output)
    text = output.read_text(encoding="utf-8")
    assert "<!DOCTYPE xmeml>" in text
    root = ET.fromstring(text)
    uri = root.findtext(".//file/pathurl")
    assert "%20" in uri and "%23" in uri and "%E7%B4%A0" in uri
    assert root.findtext(".//file/name") == "素材 & shot #1.mp4"
    if sys.platform == "win32":
        assert uri.startswith("file:///") and ":/" in uri


def test_probe_fallback_and_cache_once_per_source(tmp_path, monkeypatch):
    path, _, info = workspace(tmp_path)
    (path.parent / "media_index.json").unlink()
    calls = []
    monkeypatch.setattr(exporter, "ffprobe", lambda source: calls.append(source) or info)
    exporter.build_premiere_xml(path)
    assert len(calls) == 1


def test_complete_cache_never_invokes_probe(tmp_path, monkeypatch):
    path, _, _ = workspace(tmp_path)
    monkeypatch.setattr(exporter, "ffprobe", lambda _: pytest.fail("cache should avoid ffprobe"))
    exporter.build_premiere_xml(path)


def test_ntsc_long_timeline_has_no_cumulative_rounding_drift(tmp_path):
    ranges = [{"source": "A", "source_start": 0, "source_end": 1, "record_start": i} for i in range(3600)]
    path, _, _ = workspace(tmp_path, ranges=ranges)
    root = exporter.build_premiere_xml(path).getroot()
    clips = root.findall(".//video/track/clipitem")
    assert int(clips[-1].findtext("end")) == 108000
    assert all(int(c.findtext("end")) - int(c.findtext("start")) == 30 for c in clips)
    assert all(a.findtext("end") == b.findtext("start") for a, b in zip(clips, clips[1:]))


@pytest.mark.parametrize("timecode,rate,expected", [("01:00:00:00", "24000/1001", 86400),
                                                   ("01:00:00;00", "30000/1001", 107892),
                                                   ("01:00:00;00", "60000/1001", 215784)])
def test_source_timecode_does_not_offset_source_trims(tmp_path, timecode, rate, expected):
    path, _, info = workspace(tmp_path, source_fps=rate)
    info.update(start_timecode=timecode, timecode_rate=rate)
    (path.parent / "media_index.json").write_text(json.dumps({"media": [info]}))
    root = exporter.build_premiere_xml(path).getroot()
    assert root.findtext(".//file/timecode/frame") == str(expected)
    assert root.findtext(".//video/track/clipitem/in") == str(round(exporter.frame_rate(rate)))


@pytest.mark.parametrize("change,error", [({"speed": 2}, "retimed"), ({"transform": {"zoom": 2}}, "transforms"),
                                         ({"source_end": 121}, "duration"), ({"source_start": -1}, "validation")])
def test_invalid_or_unsupported_edit_preserves_existing_output(tmp_path, change, error):
    path, edl, _ = workspace(tmp_path)
    edl["timelines"][0]["ranges"] = [dict(source="A", source_start=1, source_end=2, record_start=0)]
    edl["timelines"][0]["ranges"][0].update(change)
    if change.get("speed"):
        edl["timelines"][0]["ranges"][0]["source_end"] = 5
    save(path, edl)
    output = path.parent / "existing.xml"
    output.write_text("old valid export")
    with pytest.raises(ValueError, match=error):
        exporter.write_premiere_xml(path, output)
    assert output.read_text() == "old valid export"


def test_path_escape_fails_before_probe(tmp_path, monkeypatch):
    path, edl, _ = workspace(tmp_path)
    edl["timelines"][0]["sources"]["A"] = "../outside.mp4"
    save(path, edl)
    monkeypatch.setattr(exporter, "ffprobe", lambda _: pytest.fail("must validate paths first"))
    with pytest.raises(ValueError, match="escapes"):
        exporter.build_premiere_xml(path)


def test_multiple_sequences_have_unique_clip_ids_and_shared_file(tmp_path):
    path, edl, _ = workspace(tmp_path)
    edl["timelines"].append(dict(edl["timelines"][0], name="Second"))
    save(path, edl)
    root = exporter.build_premiere_xml(path).getroot()
    assert len(root.findall("./project/children/sequence")) == 2
    ids = [item.get("id") for item in root.findall(".//clipitem")]
    assert len(ids) == len(set(ids))
    assert len(root.findall(".//file/pathurl")) == 1


def test_cli_registration_and_fcpxml_unchanged(tmp_path, monkeypatch):
    path, _, _ = workspace(tmp_path)
    before = ET.tostring(build_fcpxml(path).getroot())
    monkeypatch.setattr(sys, "argv", ["vtc export-premiere-xml", str(path)])
    exporter.main()
    assert exporter.default_premiere_xml_path(path).exists()
    assert ET.tostring(build_fcpxml(path).getroot()) == before
    assert COMMANDS["export-premiere-xml"][0] == "helpers.export_premiere_xml"


@pytest.mark.parametrize("rate", [0, -1, "0/0", 27.5])
def test_invalid_rates_rejected(rate):
    with pytest.raises((ValueError, ZeroDivisionError)):
        exporter.frame_rate(rate)


def test_ntsc_decimal_alias_is_exact():
    assert exporter.frame_rate("23.976") == Fraction(24000, 1001)


def test_missing_record_positions_accumulate_source_frames(tmp_path):
    ranges = [{"source": "A", "source_start": 0, "source_end": 1} for _ in range(40)]
    path, _, _ = workspace(tmp_path, ranges=ranges)
    root = exporter.build_premiere_xml(path).getroot()
    assert root.findtext("./project/children/sequence/duration") == "1200"


def test_short_clip_and_gap_rejected_by_exact_timing(tmp_path):
    path, edl, _ = workspace(tmp_path)
    edl["timelines"][0]["ranges"] = [{"source": "A", "source_start": 0, "source_end": 0.1}]
    save(path, edl)
    with pytest.raises(ValueError, match="minimum"):
        exporter.build_premiere_xml(path)
    edl["timelines"][0]["ranges"] = [{"source": "A", "source_start": 0, "source_end": 1, "record_start": 2}]
    save(path, edl)
    with pytest.raises(ValueError, match="contiguous"):
        exporter.build_premiere_xml(path)


@pytest.mark.parametrize("info_change", [{"duration": -1}, {"audio_rate": 0}, {"width": 0},
                                       {"avg_frame_rate": "0/0"}, {"start_timecode": "00:01:00;00"}])
def test_bad_media_metadata_fails(tmp_path, info_change):
    path, _, info = workspace(tmp_path)
    info.update(info_change)
    (path.parent / "media_index.json").write_text(json.dumps({"media": [info]}))
    with pytest.raises(ValueError):
        exporter.build_premiere_xml(path)


@pytest.mark.skipif(sys.platform != "win32", reason="Windows UNC path semantics")
def test_unc_uri_escaping():
    from pathlib import Path
    uri = Path(r"\\server\share\素材 #1.mov").as_uri()
    assert uri.startswith("file://server/share/") and "%23" in uri and "%E7%B4%A0" in uri


def test_reported_25_cut_sequence_preserves_all_source_frames(tmp_path):
    rows = json.loads((Path(__file__).parent / "fixtures/premiere/reported-cut-frames.json").read_text())
    assert sum(r["end"] - r["start"] != r["out"] - r["in"] for r in rows) == 12
    rate = Fraction(30000, 1001)
    ranges = [{"source": "A", "source_start": float(r["in"] / rate),
               "source_end": float(r["out"] / rate)} for r in rows]
    path, _, info = workspace(tmp_path, ranges=ranges)
    info["duration"] = 287.8
    (path.parent / "media_index.json").write_text(json.dumps({"media": [info]}))
    root = exporter.build_premiere_xml(path).getroot()
    clips = root.findall(".//sequence/media/video/track/clipitem")
    assert len(clips) == 25
    for clip, row in zip(clips, rows):
        assert int(clip.findtext("in")) == row["in"]
        assert int(clip.findtext("out")) == row["out"]
        assert int(clip.findtext("end")) - int(clip.findtext("start")) == row["out"] - row["in"]
    assert all(a.findtext("end") == b.findtext("start") for a, b in zip(clips, clips[1:]))
    assert int(clips[-1].findtext("end")) - int(clips[-1].findtext("start")) == 47
    assert root.findtext(".//sequence/duration") == clips[-1].findtext("end")


def test_stereo_structure_matches_premiere_export(tmp_path):
    reference = ET.parse(Path(__file__).parent / "fixtures/premiere/premiere-stereo-reference.xml").getroot()
    path, _, _ = workspace(tmp_path)
    sequence = exporter.build_premiere_xml(path).find(".//sequence")
    assert sequence.get("explodedTracks") == reference.get("explodedTracks")
    audio = sequence.find("media/audio")
    expected = reference.find("media/audio")
    assert audio.findtext("numOutputChannels") == expected.findtext("numOutputChannels")
    assert ET.tostring(audio.find("outputs")).split() == ET.tostring(expected.find("outputs")).split()
    for track, ref in zip(audio.findall("track"), expected.findall("track")):
        assert track.attrib == ref.attrib
        assert track.findtext("outputchannelindex") == ref.findtext("outputchannelindex")
        assert all(c.get("premiereChannelType") == "stereo" for c in track.findall("clipitem"))


def test_mixed_mono_stereo_use_separate_track_groups(tmp_path):
    path, edl, info = workspace(tmp_path, channels=1)
    second = path.parent.parent / "raw/stereo.mp4"
    second.touch()
    edl["timelines"][0]["sources"]["B"] = str(second)
    edl["timelines"][0]["ranges"][1]["source"] = "B"
    save(path, edl)
    (path.parent / "media_index.json").write_text(json.dumps({"media": [info, dict(info, path=str(second), audio_channels=2)]}))
    root = exporter.build_premiere_xml(path).getroot()
    tracks = root.findall(".//sequence/media/audio/track")
    assert [t.get("premiereTrackType") for t in tracks] == ["Mono", "Stereo", "Stereo"]
    stereo = root.findall(".//sequence/media/video/track/clipitem")[1]
    assert [link.findtext("trackindex") for link in stereo.findall("link")[1:]] == ["2", "3"]


@pytest.mark.parametrize("fps,source_fps", [(29.97, "30000/1001"), (23.976, "24000/1001"), (25, "25")])
def test_fractional_source_boundaries_define_clip_length(tmp_path, fps, source_fps):
    ranges = [{"source": "A", "source_start": 1.017, "source_end": 2.603},
              {"source": "A", "source_start": 3.219, "source_end": 4.821}]
    path, _, _ = workspace(tmp_path, fps=fps, source_fps=source_fps, ranges=ranges)
    clips = exporter.build_premiere_xml(path).findall(".//sequence/media/video/track/clipitem")
    assert all(int(c.findtext("end")) - int(c.findtext("start")) ==
               int(c.findtext("out")) - int(c.findtext("in")) for c in clips)


def test_draft_omits_rounded_record_start_and_exports_contiguously(tmp_path, monkeypatch):
    from helpers.draft_silence_cut import build_edl
    from helpers.validate_edl import validate

    path, edl, info = workspace(tmp_path)
    video = Path(edl["timelines"][0]["sources"]["A"])
    monkeypatch.setattr("helpers.draft_silence_cut.ffprobe", lambda _: info)
    draft = build_edl(video, tmp_path, path.parent,
                      [{"start": i * 2 + 0.017, "end": i * 2 + 1.603} for i in range(50)],
                      project_name="Draft", timeline_name="Cut", style="documentary", settings={})
    assert all("record_start" not in r for r in draft["timelines"][0]["ranges"])
    save(path, draft)
    assert validate(path) == []
    clips = exporter.build_premiere_xml(path).findall(".//sequence/media/video/track/clipitem")
    assert all(a.findtext("end") == b.findtext("start") for a, b in zip(clips, clips[1:]))
    assert build_fcpxml(path).find(".//sequence") is not None
