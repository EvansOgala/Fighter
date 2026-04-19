from __future__ import annotations

import json
from pathlib import Path

import pygame

SETTINGS_DIR = Path.home() / ".config" / "fighter"
SETTINGS_PATH = SETTINGS_DIR / "settings.json"

DEFAULT_SETTINGS = {
    "window_size": [1280, 720],
    "fullscreen": False,
    "player_count": 1,
    "rounds_to_win": 2,
    "keybindings": {
        "player1": {
            "left": pygame.K_a,
            "right": pygame.K_d,
            "jump": pygame.K_w,
            "punch": pygame.K_f,
            "kick": pygame.K_r,
            "block": pygame.K_h,
            "weapon": pygame.K_g,
            "crouch": pygame.K_s,
        },
        "player2": {
            "left": pygame.K_LEFT,
            "right": pygame.K_RIGHT,
            "jump": pygame.K_UP,
            "punch": pygame.K_i,
            "kick": pygame.K_o,
            "block": pygame.K_QUOTE,
            "weapon": pygame.K_p,
            "crouch": pygame.K_DOWN,
        },
    },
}


def load_settings() -> dict:
    if not SETTINGS_PATH.exists():
        return json.loads(json.dumps(DEFAULT_SETTINGS))
    try:
        data = json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return json.loads(json.dumps(DEFAULT_SETTINGS))

    merged = json.loads(json.dumps(DEFAULT_SETTINGS))
    merged.update({k: v for k, v in data.items() if k != "keybindings"})
    if isinstance(data.get("keybindings"), dict):
        for player in ("player1", "player2"):
            if isinstance(data["keybindings"].get(player), dict):
                merged["keybindings"][player].update(data["keybindings"][player])

    width, height = merged.get("window_size", [1280, 720])
    merged["window_size"] = [max(960, int(width)), max(540, int(height))]
    merged["rounds_to_win"] = max(1, min(5, int(merged.get("rounds_to_win", 2))))
    merged["player_count"] = 1 if int(merged.get("player_count", 1)) != 2 else 2
    merged["fullscreen"] = bool(merged.get("fullscreen", False))
    return merged


def save_settings(settings: dict) -> None:
    SETTINGS_DIR.mkdir(parents=True, exist_ok=True)
    SETTINGS_PATH.write_text(json.dumps(settings, indent=2), encoding="utf-8")
