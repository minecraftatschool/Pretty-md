# Blocky Puzzle

A block puzzle game made with Godot 3.6 (GDScript). One codebase runs on Android 4.4+,
Wear OS style small/round screens, and the web.

- 8×8 board, three pieces per hand, full rows and columns clear
- Modes: Classic, Rush (2 minutes), 30 Moves, Rubble (stones drop in every 4 moves)
- Hands are always solvable; fuller boards are likelier to get a line-clearing piece
- Main menu, settings (sound, music, vibration, reset scores), how-to-play
- Music and sound effects are synthesized by `game/tools/gen_audio.py`

## Layout

| Path | What it is |
| --- | --- |
| `game/` | The Godot 3.6 project. All game logic and drawing is in `main.gd`. |
| `game/audio/` | Rendered music (`music.ogg`) and sound effects (`*.wav`). |
| `game/tools/gen_audio.py` | Regenerates the audio (needs Python 3 with NumPy; `ffmpeg` for the OGG). |
| `web/crazygames/index.html` | HTML shell for the CrazyGames build (SDK v3 events, no ads). |
| `web/playhop/index.html` | HTML shell for the Playhop build (v1.9-playhop): Yandex Games SDK, player-data saves, pause and mute handling. |
| `scratch/` | The Scratch 3 edition (v1.9-scratch): the `.sb3` project and `gen_sb3.py`, the script that builds it. |
| `web/artifact/blocky-puzzle.html` | HTML shell used for the claude.ai artifact (engine split into two files). |

## Building

Open `game/` in Godot 3.6 and use Project → Export, or from the command line:

```sh
godot --path game --export Android BlockyPuzzle.apk
godot --path game --export HTML5 build/index.html
```

- **Android:** set your own keystore in the Android preset (`keystore/release*` are left blank here),
  and point the editor settings at an Android SDK. The preset targets `armeabi-v7a` and `arm64-v8a`, min SDK 19.
- **Web:** the HTML5 export produces `index.js`, `index.wasm`, `index.pck` and `index.audio.worklet.js`.
- **Playhop:** export HTML5, replace the exported `index.html` with `web/playhop/index.html`, update its `fileSizes`,
  and zip the files with `index.html` at the root. The shell hides the author credit and shows one ad between games.
- **CrazyGames:** export HTML5, then replace the exported `index.html` with `web/crazygames/index.html`
  and update the two numbers in its `fileSizes` to the byte sizes of your `index.pck` and `index.wasm`.

## Scratch edition

`scratch/BlockyPuzzle-v1.9-scratch.sb3` opens in Scratch 3 or TurboWarp. It is generated, not hand-built:

```sh
ffmpeg -i game/audio/music.ogg -ac 1 -ar 22050 -c:a pcm_s16le music.wav
python3 scratch/gen_sb3.py game/audio music.wav BlockyPuzzle-v1.9-scratch.sb3
```

One hidden sprite draws everything with pen stamps. It has the four modes, scoring, combos and sounds;
it does not have saved scores, the guaranteed-solvable dealing or the phone and watch layouts.

## Self-test

`main.gd` has a built-in test player. Run the project with `BP_TEST=<dir>` (and optionally `BP_MODE=0..3`,
`BP_WEB=1` for the browser layouts): it walks the menus, plays a game through the engine's input events,
saves screenshots to `<dir>` and quits.

## Credits

Made by sehrn.xyz. Built with Godot Engine (MIT). Typeface: Lilita One (SIL Open Font License 1.1).
