from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from helpers import installer


def test_package_spec_uses_tool_name_extra_repo_and_ref() -> None:
    assert installer.package_spec("https://example.test/repo.git", "v1.2.3", True) == (
        "video-timeline-copilot[transcribe] @ git+https://example.test/repo.git@v1.2.3"
    )


def test_skill_targets_include_claude_and_codex_locations(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(installer.Path, "home", lambda: tmp_path)

    assert installer.skill_targets("all") == [
        tmp_path / ".claude" / "skills" / "video-timeline-copilot",
        tmp_path / ".agents" / "skills" / "video-timeline-copilot",
        tmp_path / ".codex" / "skills" / "video-timeline-copilot",
    ]


def test_register_skills_copies_managed_skill_without_git_or_venv(tmp_path: Path, monkeypatch) -> None:
    source = tmp_path / "source"
    source.mkdir()
    (source / "SKILL.md").write_text("---\nname: video-timeline-copilot\n---\n", encoding="utf-8")
    (source / ".git").mkdir()
    (source / ".venv").mkdir()
    (source / ".pytest_cache").mkdir()
    (source / "plans").mkdir()
    monkeypatch.setattr(installer.Path, "home", lambda: tmp_path / "home")

    installer.register_skills(source, "claude", copy=True, force=False)

    target = tmp_path / "home" / ".claude" / "skills" / "video-timeline-copilot"
    assert (target / "SKILL.md").exists()
    assert (target / installer.MANAGED_MARKER).exists()
    assert not (target / ".git").exists()
    assert not (target / ".venv").exists()
    assert not (target / ".pytest_cache").exists()
    assert not (target / "plans").exists()


def test_register_skills_leaves_unmanaged_existing_target_without_force(tmp_path: Path, monkeypatch) -> None:
    source = tmp_path / "source"
    source.mkdir()
    (source / "SKILL.md").write_text("new", encoding="utf-8")
    target = tmp_path / "home" / ".claude" / "skills" / "video-timeline-copilot"
    target.mkdir(parents=True)
    (target / "SKILL.md").write_text("existing", encoding="utf-8")
    monkeypatch.setattr(installer.Path, "home", lambda: tmp_path / "home")

    installer.register_skills(source, "claude", copy=True, force=False)

    assert (target / "SKILL.md").read_text(encoding="utf-8") == "existing"


@pytest.mark.parametrize("command", ["install", "update"])
def test_installer_defaults_keep_premiere_fork(command):
    args = installer.build_parser().parse_args([command])
    assert args.repo == "https://github.com/polaris-frame/video-timeline-copilot.git"
    assert args.ref == "feat/premiere-xmeml"


@pytest.mark.parametrize("transcribe", [True, False])
def test_update_installs_cli_and_skill_from_same_fork(tmp_path, monkeypatch, transcribe):
    args = installer.build_parser().parse_args(["update", "--home", str(tmp_path)] +
                                               ([] if transcribe else ["--no-transcribe"]))
    calls = []
    registered = []
    monkeypatch.setattr(installer, "command_exists", lambda _: True)
    monkeypatch.setattr(installer, "run", lambda command: calls.append(command))
    monkeypatch.setattr(installer, "install", lambda options: registered.append((options.repo, options.ref)))
    installer.update(args)
    extra = "[transcribe]" if transcribe else ""
    assert calls == [["uv", "tool", "install", "--force",
                      f"video-timeline-copilot{extra} @ git+https://github.com/polaris-frame/video-timeline-copilot.git@feat/premiere-xmeml"]]
    assert registered == [(args.repo, args.ref)]


def test_install_preserves_explicit_source_and_does_not_reinstall_cli(tmp_path, monkeypatch):
    args = installer.build_parser().parse_args(["install", "--repo", "https://example.test/custom.git",
                                               "--ref", "v2", "--home", str(tmp_path), "--agent", "none"])
    calls = []
    monkeypatch.setattr(installer, "sync_repo", lambda *values: calls.append(values) or tmp_path)
    monkeypatch.setattr(installer, "register_skills", lambda *values, **kwargs: None)
    monkeypatch.setattr(installer, "check_ffmpeg", lambda _: None)
    monkeypatch.setattr(installer, "run", lambda _: pytest.fail("install must not reinstall CLI"))
    installer.install(args)
    assert calls == [(tmp_path, "https://example.test/custom.git", "v2")]


@pytest.mark.parametrize("existing,ref,branch", [(False, "feat/premiere-xmeml", "feat/premiere-xmeml"),
                                               (True, "feat/premiere-xmeml", "feat/premiere-xmeml"),
                                               (True, "main", "main"), (True, "v1.2.3", "HEAD"),
                                               (True, "abcdef123", "HEAD")])
def test_sync_repo_refreshes_branches_but_keeps_tags_and_commits_pinned(tmp_path, monkeypatch, existing, ref, branch):
    destination = tmp_path / "repo"
    destination.mkdir()
    (destination / "SKILL.md").write_text("skill")
    if existing:
        (destination / ".git").mkdir()
    calls = []
    monkeypatch.setattr(installer, "command_exists", lambda _: True)

    def fake_run(command, **kwargs):
        calls.append(command)
        return SimpleNamespace(stdout=branch + "\n")

    monkeypatch.setattr(installer, "run", fake_run)
    assert installer.sync_repo(tmp_path, installer.REPO_URL, ref) == destination
    if existing:
        assert ["git", "-C", str(destination), "remote", "set-url", "origin", installer.REPO_URL] in calls
        assert ["git", "-C", str(destination), "fetch", "origin"] in calls
    else:
        assert calls[0] == ["git", "clone", installer.REPO_URL, str(destination)]
    assert ["git", "-C", str(destination), "checkout", ref] in calls
    pulls = [command for command in calls if "pull" in command]
    assert pulls == ([["git", "-C", str(destination), "pull", "--ff-only", "origin", ref]] if branch == ref else [])


def test_bare_installer_invocation_uses_install_defaults(monkeypatch):
    import sys

    calls = []
    monkeypatch.setattr(sys, "argv", ["video-timeline-copilot"])
    monkeypatch.setattr(installer, "install", lambda args: calls.append((args.repo, args.ref)))
    installer.main()
    assert calls == [(installer.REPO_URL, installer.DEFAULT_REF)]
