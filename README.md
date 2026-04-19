# Fighter

Fighter is a Python remake inspired by Hikou no mizu.

It reuses the bundled art, music, fonts, and configuration data from that app to
build a softer-feeling local fighting game with:

- Rounded, modern menu UI
- Character select based on the original three fighters
- Arena select based on the original stage data
- Local single-player fights against a CPU opponent
- Local two-player versus support
- Round-based matches with configurable rounds to win
- Fullscreen toggle, resizable window, and persistent settings
- Editable player 1 and player 2 keybinds
- Melee, kicking, blocking, crouching, jumping, and shuriken throws
- Original bundled music and UI sounds when available

## Controls

### Menu

- `Up` / `Down`: move between menu buttons
- `Enter`: activate the focused button
- `Escape`: go back / quit
- `F11`: toggle fullscreen

### Fight

Default player 1 controls:

- `A` / `D`: move
- `W`: jump
- `F`: punch
- `R`: kick
- `G`: throw shuriken
- `H`: block
- `S`: crouch

Default player 2 controls:

- `Left` / `Right`: move
- `Up`: jump
- `I`: punch
- `O`: kick
- `P`: throw shuriken
- `'`: block
- `Down`: crouch

All of these can be changed in the in-game options screen.

## Run

```bash
cd ~/Documents/Fighter
python3 -m pip install -r requirements.txt
python3 main.py
```

## Notes

- Assets are copied from the Flatpak payload under `assets/original/`.
- A local desktop launcher is included at `Fighter.desktop`.
- This is a Python reinterpretation, not a source port of the original C++ game.
- The original bundled metadata describes Hikou no mizu as GPL-3.0-only together
  with several content licenses. Keep that in mind if you plan to redistribute this remake.
