# Premiere import regression references

`reported-cut-frames.json` contains only the 25 video clip start/end/in/out
values from the user-supplied `test.xml`. Twelve spans disagree by one frame;
the last is timeline 1298–1346 (48f), source 7307–7354 (47f).
The regression reconstructs source trims from these frame values, without
claiming to recover the original pre-rounding EDL seconds.

`premiere-stereo-reference.xml` is a minimal structural excerpt from the
user-supplied Premiere export `C0019.xml`: exploded sequence flag, stereo
track/clip attributes, two output groups, and left/right track routing.
Source paths, names, UUIDs, editing UI state, media, and effect data are omitted.
