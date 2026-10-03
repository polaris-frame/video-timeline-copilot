# Text-based block review

Use this mode for human-controlled interview editing from a full transcript.
Keep the ordinary silence-cut and automatic rough-cut workflows available.

## Full transcript and blocks

Inventory original media and reuse a matching transcript cache. Otherwise
transcribe the complete source, with segment and word timestamps. Check cache
identity against source path, duration and transcription settings. Preserve the
original cache. ASR is fallible: mark unclear speech and uncertain speakers for
human checking, without inventing words or silently discarding it.

Save all review artifacts under `edit/text-review/`. Create a full transcript,
`blocks.json`, and a readable Markdown review. Divide by coherent question/answer,
topic or example rather than individual phrases. Assign stable IDs such as 01,
02; never renumber after selection. Include every transcript segment exactly
once, including preparation, questions, repeated takes and closing remarks.
Keep original source mapping and timestamps when a segment needs splitting.

For each block display its ID, title, source time range, **all recognized speech**,
uncertainty markers, and a separate proposed keep/delete/hold decision with a
reason. A summary must not substitute for full speech. Make the complete review
file available even if it is too long for chat. Match the user's language.

Recommend a coherent interview with complete answers and useful questions,
natural pauses, and few unnecessary jump cuts. Show every block, including
proposed deletions. Do not equate every hesitation or repetition with waste.
If asked to do only transcription, blocking and proposals, stop here.

## Selection ledger

`blocks.json` is a review ledger created by the agent, not a new CLI input schema.
Use a root `sources` map, a `blocks` array, `selected_order`, `deleted_ids`, and
`status`. Each block records `id`, `source_id`, `start`, `end`, `title`, full
`segments`, `recommendation`, `reason`, `check`, and `user_selection`.
Recommendations and user selections are separate; unknown selections stay null.
Store times in seconds on the original source timeline. Keep existing ledgers
readable when their source mapping uses a different field name.

Interpret “delete 06, 25, 29, 34; keep everything else” literally: retain every
other block, including blocks the agent proposed deleting. Persist and show the
resolved selection. Reject unknown or conflicting IDs with a concise clarification;
never silently guess. A partial list without a default leaves other decisions
unresolved. Preserve chronological order unless reordering is requested or accepted.
For partial-block edits create stable child IDs (07-A, 07-B) and retain their
parent/source mapping and full text. Hearing corrections should be recorded
separately from the original ASR text.

## Export after confirmation

When the user asks to export the confirmed selection, translate it to the
existing EDL schema. Reference original media, not generated audio or previews.
Merge adjacent retained blocks into longer source ranges to preserve natural
conversation; do not bridge deleted blocks. Keep internal pauses and questions
within selected blocks. Do not apply an additional silence-cut or discretionary
cleanup pass to the confirmed content.

Allow natural boundary handles, initially around 0.5–0.8 seconds where useful,
then inspect source audio at each cut. Handles must not bring back deleted speech
or preparation; trim or adjust them based on the actual neighboring audio.
A transcript segment may start long before the audible words. Listen to doubtful
boundaries or retranscribe a short original-source excerpt, map excerpt times
back to source time, and record corrections without overwriting the original cache.

Check that each selected block is covered, deleted speech is absent, order agrees
with the ledger, and retained speech is complete. Validate and evaluate using the
existing CLI workflow. Fix real boundary errors; do not bypass failures, rewrite
transcript text to silence warnings, or tighten preserved pauses solely to meet
automatic pacing thresholds. Report any incompatible automatic warning separately.

For Premiere Pro, after validation:

```bash
vtc export-premiere-xml /path/to/footage/edit/edl.json --out /path/to/footage/edit/cut_selected.xml
```

Also export SRT using the existing workflow. Use FCPXML for an editor that needs
it. Check source links and frame-based clip continuity. State whether an actual
editor import or playback was tested; XML generation alone does not establish it.
