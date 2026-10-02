# Install

## Recommended install

Recommended:

This fork uses `polaris-frame/video-timeline-copilot` and the
`feat/premiere-xmeml` branch for both the CLI and skill. The bundled
`install` and `update` commands default to this source; they do not infer the
source from a previously installed package. Use both `--repo` and `--ref` to
select another source. When this branch is merged into the fork's `main`,
update the installer defaults and installation examples together.

```bash
uv tool install "video-timeline-copilot[transcribe] @ git+https://github.com/polaris-frame/video-timeline-copilot.git@feat/premiere-xmeml"
video-timeline-copilot install --agent codex
```

The `uv` command installs the CLI. The bundled installer registers the agent
skill from the same fork and branch. Use the bundled installer for this branch:
`skills add` currently interprets the slash in `feat/premiere-xmeml` as a path
separator when given a GitHub tree URL.

For local unpublished testing, avoid running `npx skills add .` from a checkout
that contains `.venv`, `.pytest_cache`, or other ignored build/cache folders.
The `skills` CLI copies local directories as they exist on disk. Install from
GitHub after pushing, or use the bundled installer, to avoid copying local
environment files into the installed skill.

`skills.sh` does not run post-install hooks from skills. If the helper CLI is
not installed when the skill is first used, the skill tells the agent to ask
before running the bootstrap commands in the "Agent bootstrap" section below.
The skill also tells the agent to refresh PATH after installing `uv`/`vtc` and
verify `vtc --help` in the current shell before continuing. Manual FFmpeg/Python
fallbacks are reserved for cases where the user refuses to install `vtc` or `uv`
and still asks the agent to continue.

## Agent bootstrap

These are the commands the skill instructs an agent to run (after asking the
user for permission) when `vtc` is missing from `PATH` in a new environment.
They install `uv` if needed, install the helper CLI as an isolated tool, and
make `vtc` available in the current shell.

Windows PowerShell:

```powershell
if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
  winget install --id astral-sh.uv -e
}

$machinePath = [Environment]::GetEnvironmentVariable("Path", "Machine")
$userPath = [Environment]::GetEnvironmentVariable("Path", "User")
$env:Path = "$machinePath;$userPath"

$uv = (Get-Command uv -ErrorAction SilentlyContinue).Source
if (-not $uv) {
  $uv = Get-ChildItem "$env:LOCALAPPDATA\Microsoft\WinGet\Packages" -Recurse -Filter uv.exe -ErrorAction SilentlyContinue |
    Select-Object -First 1 -ExpandProperty FullName
}
if (-not $uv) {
  throw "uv is installed or requested, but uv.exe was not found. Reopen PowerShell or install uv from https://docs.astral.sh/uv/"
}

& $uv tool install --force "video-timeline-copilot[transcribe] @ git+https://github.com/polaris-frame/video-timeline-copilot.git@feat/premiere-xmeml"

$toolDir = "$env:USERPROFILE\.local\bin"
if (Test-Path $toolDir) {
  $env:Path = "$toolDir;$env:Path"
  $userPath = [Environment]::GetEnvironmentVariable("Path", "User")
  if ($userPath -notlike "*$toolDir*") {
    [Environment]::SetEnvironmentVariable("Path", "$userPath;$toolDir", "User")
  }
}

vtc --help
```

macOS/Linux:

```bash
if ! command -v uv >/dev/null 2>&1; then
  curl -LsSf https://astral.sh/uv/install.sh | sh
  export PATH="$HOME/.local/bin:$PATH"
fi
uv tool install "video-timeline-copilot[transcribe] @ git+https://github.com/polaris-frame/video-timeline-copilot.git@feat/premiere-xmeml"
export PATH="$HOME/.local/bin:$PATH"
vtc --help
```

If the agent should run helper commands without installing the tool
permanently, `uv tool run` is the approved alternative:

```bash
uv tool run --from "video-timeline-copilot[transcribe] @ git+https://github.com/polaris-frame/video-timeline-copilot.git@feat/premiere-xmeml" vtc
```

## Bundled installer

This repo also ships a convenience installer:

```bash
uv tool install "video-timeline-copilot[transcribe] @ git+https://github.com/polaris-frame/video-timeline-copilot.git@feat/premiere-xmeml"
video-timeline-copilot install
```

This installer:

1. Fetches the configured skill repository and refreshes its selected branch.
2. Registers the skill for Claude, Codex, and Open Agent Skills locations.
3. Checks for `ffmpeg` and `ffprobe`.

Update later with:

```bash
video-timeline-copilot update
```

`install` only registers the skill; the preceding `uv tool install` installs
the CLI. `update` reinstalls the CLI in its isolated uv tool environment and
refreshes the skill from the same repository/ref. It includes transcription
dependencies by default; use `video-timeline-copilot update --no-transcribe`
for the basic CLI. Tags and commit SHAs remain pinned; branch updates use
fast-forward only and stop if local Git changes prevent that operation.

An older installation may still default to upstream. To migrate it, first run:

```bash
uv tool install --force --reinstall --refresh --python 3.12 "video-timeline-copilot @ git+https://github.com/polaris-frame/video-timeline-copilot.git@feat/premiere-xmeml"
```

Run diagnostics with:

```bash
video-timeline-copilot doctor
```

## What gets installed

There are two setup steps:

1. Install the **agent skill** with `npx skills add`, the bundled installer, or
   by placing this repo under an agent skill directory.
2. Install the **Python helper CLI** into a Python environment so commands like
   `vtc inventory` and `vtc transcribe` are available.

The installer handles skill registration. `uv tool install` handles the Python
CLI so users do not have to manage a virtual environment manually.

## Skill locations

The installer registers the same `SKILL.md` in the common personal skill
locations:

- Claude: `~/.claude/skills/video-timeline-copilot`
- Codex / Open Agent Skills: `~/.agents/skills/video-timeline-copilot`
- Codex legacy compatibility: `~/.codex/skills/video-timeline-copilot`

## Manual skill install

Windows PowerShell:

```powershell
mkdir $env:USERPROFILE\.codex\skills -ErrorAction SilentlyContinue
git clone --branch feat/premiere-xmeml https://github.com/polaris-frame/video-timeline-copilot.git `
  $env:USERPROFILE\.codex\skills\video-timeline-copilot
cd $env:USERPROFILE\.codex\skills\video-timeline-copilot
```

Do not create a Python virtual environment inside the installed skill folder.
Install the helper CLI separately with `uv tool install`.

macOS/Linux:

```bash
mkdir -p ~/.codex/skills
git clone --branch feat/premiere-xmeml https://github.com/polaris-frame/video-timeline-copilot.git \
  ~/.codex/skills/video-timeline-copilot
cd ~/.codex/skills/video-timeline-copilot
```

## Manual Python helper CLI

Recommended isolated install with uv:

```bash
uv tool install "video-timeline-copilot[transcribe] @ git+https://github.com/polaris-frame/video-timeline-copilot.git@feat/premiere-xmeml"
```

After installation, the `vtc` command is available on `PATH`:

```bash
vtc --help
```

To reinstall from the latest GitHub `feat/premiere-xmeml`:

```bash
uv tool install --force "video-timeline-copilot[transcribe] @ git+https://github.com/polaris-frame/video-timeline-copilot.git@feat/premiere-xmeml"
```

## Dependencies

Python 3.10+ is required.

For transcription:

```bash
pip install -e ".[transcribe]"
```

For media inventory and audio extraction, install `ffmpeg` and ensure both
`ffmpeg` and `ffprobe` are on `PATH`.

Keep FFmpeg updated and run the workflow on media files you trust.

## Platform Compatibility

Windows is the primary tested platform today. Linux and macOS are expected to
work for the CLI/FCPXML workflow, but they have not yet been fully validated end
to end in this repo.

DaVinci Resolve scripting setup is platform-specific. The current Resolve
examples use Windows paths. Use `vtc export-fcpxml` as the portable fallback.

## DaVinci Resolve Setup

Free Resolve users should use the FCPXML fallback:

```bash
vtc export-fcpxml /path/to/footage/edit/edl.json
```

Then import the generated `.fcpxml` manually in Resolve.

The native Resolve builder requires a local Resolve install and external
scripting access. In current Resolve releases, that generally means DaVinci
Resolve Studio. On Windows, these environment variables are typically needed:

```powershell
$env:RESOLVE_SCRIPT_API="C:\ProgramData\Blackmagic Design\DaVinci Resolve\Support\Developer\Scripting"
$env:RESOLVE_SCRIPT_LIB="C:\Program Files\Blackmagic Design\DaVinci Resolve\fusionscript.dll"
$env:PYTHONPATH="$env:PYTHONPATH;$env:RESOLVE_SCRIPT_API\Modules"
```

Start Resolve before running:

```bash
vtc build-resolve-project /path/to/footage/edit/edl.json
```
