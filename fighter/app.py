from __future__ import annotations

import json
import math
import random
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path

import pygame

from fighter.settings import DEFAULT_SETTINGS, load_settings, save_settings

VIRTUAL_W = 1280
VIRTUAL_H = 720
FPS = 60
GRAVITY = 3600.0

ASSET_ROOT = Path(__file__).resolve().parent.parent / "assets" / "original"
GFX_ROOT = ASSET_ROOT / "gfx"
AUDIO_ROOT = ASSET_ROOT / "audio"
CFG_ROOT = ASSET_ROOT / "cfg"
FONT_ROOT = ASSET_ROOT / "fonts"

BG = (13, 19, 34)
PANEL = (50, 92, 156)
PANEL_SOFT = (86, 125, 183)
CARD = (45, 84, 142)
BORDER = (170, 198, 234)
TEXT = (245, 247, 252)
MUTED = (205, 221, 243)
ACCENT = (222, 56, 60)
ACCENT_SOFT = (84, 160, 255)
SUCCESS = (55, 214, 70)
WARN = (245, 102, 102)
SHADOW = (0, 0, 0, 115)

ACTIONS = ["left", "right", "jump", "punch", "kick", "block", "weapon", "crouch"]
ACTION_LABELS = {
    "left": "Move left",
    "right": "Move right",
    "jump": "Jump",
    "punch": "Punch",
    "kick": "Kick",
    "block": "Block",
    "weapon": "Weapon",
    "crouch": "Crouch",
}


@dataclass
class Platform:
    x: float
    y: float
    width: float
    height: float


@dataclass
class ArenaDef:
    key: str
    name: str
    width: int
    height: int
    ground: int
    platforms: list[Platform]
    background_path: Path


@dataclass
class SpriteFrame:
    surface: pygame.Surface
    body_width: float
    body_height: float


@dataclass
class CharacterDef:
    name: str
    strength: float
    speed: float
    jump_energy: float
    color: tuple[int, int, int]
    portrait: pygame.Surface
    sprite_frames: dict[str, SpriteFrame]


@dataclass
class Projectile:
    owner_id: int
    x: float
    y: float
    vx: float
    radius: float = 24.0
    ttl: float = 1.8


@dataclass
class FighterState:
    fighter_id: int
    character: CharacterDef
    x: float
    y: float
    body_w: float
    body_h: float
    human: bool
    control_map: dict[str, int]
    facing: int = 1
    vx: float = 0.0
    vy: float = 0.0
    on_ground: bool = False
    crouching: bool = False
    blocking: bool = False
    health: float = 100.0
    rounds_won: int = 0
    attack_timer: float = 0.0
    attack_kind: str = ""
    attack_cooldown: float = 0.0
    special_cooldown: float = 0.0
    hit_flash: float = 0.0
    stun_timer: float = 0.0
    ai_timer: float = 0.0

    @property
    def move_speed(self) -> float:
        return 520.0 + self.character.speed * 0.35

    @property
    def jump_velocity(self) -> float:
        return -(1100.0 + self.character.jump_energy * 0.35)

    def rect(self) -> pygame.Rect:
        height = self.body_h * (0.68 if self.crouching else 1.0)
        return pygame.Rect(int(self.x), int(self.y + self.body_h - height), int(self.body_w), int(height))

    def center(self) -> tuple[float, float]:
        body = self.rect()
        return body.centerx, body.centery


@dataclass
class Button:
    rect: pygame.Rect
    label: str
    action: str
    primary: bool = False
    hovered: bool = False

    def draw(self, screen: pygame.Surface, font: pygame.font.Font) -> None:
        base = ACCENT if self.primary else PANEL
        fill = ACCENT_SOFT if self.hovered and self.primary else (PANEL_SOFT if self.hovered else base)
        draw_soft_rect(screen, self.rect.move(0, 8), SHADOW, radius=26)
        draw_soft_rect(screen, self.rect, fill, radius=26)
        pygame.draw.rect(screen, BORDER, self.rect, 2, border_radius=26)
        text = font.render(self.label, True, TEXT)
        screen.blit(text, text.get_rect(center=self.rect.center))


class AssetBank:
    def __init__(self) -> None:
        self.font_name = FONT_ROOT / "murecho.otf"
        self.display_font_name = FONT_ROOT / "mochiypop.ttf"
        self.icon = self._load_image(GFX_ROOT / "icon.png")
        self.title = self._load_image(GFX_ROOT / "ui" / "title.png")
        self.ui_title_bg = self._load_image(GFX_ROOT / "ui" / "title.png")
        self.menu_backdrops = [
            self._load_image(GFX_ROOT / "ui" / "nagano.png"),
            self._load_image(GFX_ROOT / "ui" / "nikko.png"),
            self._load_image(GFX_ROOT / "ui" / "himeji.png"),
        ]
        self.backgrounds = {p.stem: self._load_image(p) for p in sorted((GFX_ROOT / "arenas").glob("*.png"))}
        self.shuriken = self._load_image(GFX_ROOT / "weapons" / "shuriken.png")
        self.ui_click = self._load_sound(AUDIO_ROOT / "ui" / "menuClick.ogg")
        self.ui_focus = self._load_sound(AUDIO_ROOT / "ui" / "menuFocus.ogg")
        self.ui_fight = self._load_sound(AUDIO_ROOT / "ui" / "fight.ogg")
        self.block_sound = self._load_sound(AUDIO_ROOT / "sfx" / "block" / "block.ogg")
        self.perfect_block_sound = self._load_sound(AUDIO_ROOT / "sfx" / "block" / "perfect_block.ogg")
        self.menu_music = self._pick_music(
            [
                AUDIO_ROOT / "music" / "teaser_background_music.ogg",
                AUDIO_ROOT / "music" / "blueberries.ogg",
                AUDIO_ROOT / "music" / "cool_cool_mountain.ogg",
            ]
        )
        self.fight_music = self._pick_music(
            [
                AUDIO_ROOT / "music" / "underwater_battle.ogg",
                AUDIO_ROOT / "music" / "outer_space.ogg",
                AUDIO_ROOT / "music" / "winter_wind.ogg",
            ]
        )

    def _load_image(self, path: Path) -> pygame.Surface | None:
        if not path.exists():
            return None
        return pygame.image.load(path.as_posix()).convert_alpha()

    def _load_sound(self, path: Path):
        if not path.exists() or not pygame.mixer.get_init():
            return None
        try:
            return pygame.mixer.Sound(path.as_posix())
        except pygame.error:
            return None

    def _pick_music(self, choices: list[Path]) -> Path | None:
        for path in choices:
            if path.exists():
                return path
        return None


class GameApp:
    def __init__(self) -> None:
        pygame.init()
        try:
            pygame.mixer.init()
        except pygame.error:
            pass

        self.settings = load_settings()
        self.window_size = tuple(self.settings["window_size"])
        self.fullscreen = bool(self.settings["fullscreen"])
        self.screen = self._create_window()
        self.virtual = pygame.Surface((VIRTUAL_W, VIRTUAL_H), pygame.SRCALPHA)
        self.clock = pygame.time.Clock()
        self.assets = AssetBank()
        if self.assets.icon is not None:
            pygame.display.set_icon(self.assets.icon)
        pygame.display.set_caption("Fighter")

        self.title_font = self._font(56, display=True)
        self.header_font = self._font(28, display=True)
        self.body_font = self._font(24)
        self.small_font = self._font(18)

        self.characters = self._load_characters()
        self.arenas = self._load_arenas()
        self.running = True
        self.scene = "menu"
        self.menu_focus = 0
        self.menu_buttons: list[Button] = []
        self.select_character_index = 0
        self.select_stage_index = 0
        self.selection_slots: list[int] = []
        self.selection_step = 0
        self.selection_player_count = int(self.settings["player_count"])
        self.selection_rounds = int(self.settings["rounds_to_win"])
        self.match: MatchState | None = None
        self.options_tab = "general"
        self.rebinding: tuple[str, str] | None = None

        self._rebuild_menu_buttons()
        self._play_music(self.assets.menu_music)

    def _create_window(self) -> pygame.Surface:
        flags = pygame.RESIZABLE
        if self.fullscreen:
            flags |= pygame.FULLSCREEN
            info = pygame.display.Info()
            return pygame.display.set_mode((info.current_w, info.current_h), flags)
        return pygame.display.set_mode(self.window_size, flags)

    def _font(self, size: int, display: bool = False) -> pygame.font.Font:
        path = self.assets.display_font_name if display else self.assets.font_name
        if path.exists():
            return pygame.font.Font(path.as_posix(), size)
        return pygame.font.SysFont("arial", size)

    def _play_music(self, path: Path | None) -> None:
        if path is None or not pygame.mixer.get_init():
            return
        try:
            pygame.mixer.music.load(path.as_posix())
            pygame.mixer.music.set_volume(0.35)
            pygame.mixer.music.play(-1)
        except pygame.error:
            pass

    def _play_sound(self, sound) -> None:
        if sound is not None:
            try:
                sound.play()
            except pygame.error:
                pass

    def _load_characters(self) -> list[CharacterDef]:
        root = ET.parse(CFG_ROOT / "characters.xml").getroot()
        colors = [(89, 158, 252), (179, 121, 205), (251, 132, 103)]
        out: list[CharacterDef] = []
        for index, node in enumerate(root.findall("character")):
            name = node.attrib["name"]
            char_dir = GFX_ROOT / "characters" / name
            frame_data = self._parse_character_frames(char_dir)
            portrait = scale_to_box(frame_data["idle"].surface, 240, 260)
            out.append(
                CharacterDef(
                    name=name,
                    strength=float(node.attrib.get("strength", 8)),
                    speed=float(node.attrib.get("speed", 750)),
                    jump_energy=float(node.attrib.get("jumpEnergy", 1750)),
                    color=colors[index % len(colors)],
                    portrait=portrait,
                    sprite_frames=frame_data,
                )
            )
        return out

    def _parse_character_frames(self, char_dir: Path) -> dict[str, SpriteFrame]:
        tree = ET.parse(char_dir / "data.xml").getroot()
        wanted = {
            "idle": "default",
            "run": "moving",
            "jump": "jumping",
            "block": "standing_block",
            "crouch": "crouched",
            "punch": "default_punch",
            "kick": "default_kick",
            "hit": "default_hit",
        }
        out: dict[str, SpriteFrame] = {}
        for state, path_name in wanted.items():
            frame = self._extract_first_frame(tree, path_name)
            image = pygame.image.load((char_dir / f"{path_name}.png").as_posix()).convert_alpha()
            x, y, w, h, body_w, body_h = frame
            surf = image.subsurface(pygame.Rect(x, y, w, h)).copy()
            out[state] = SpriteFrame(surf, body_w, body_h)
        return out

    def _extract_first_frame(self, root: ET.Element, path_name: str) -> tuple[int, int, int, int, float, float]:
        for animation in root.iter("animation"):
            if animation.attrib.get("path") == path_name:
                frame = animation.find("frame")
                if frame is None:
                    break
                return (
                    int(float(frame.attrib["x"])),
                    int(float(frame.attrib["y"])),
                    int(float(frame.attrib["width"])),
                    int(float(frame.attrib["height"])),
                    float(frame.attrib.get("bodyWidth", frame.attrib["width"])),
                    float(frame.attrib.get("bodyHeight", frame.attrib["height"])),
                )
        raise ValueError(f"Missing animation path {path_name}")

    def _load_arenas(self) -> list[ArenaDef]:
        root = ET.parse(CFG_ROOT / "arenas.xml").getroot()
        arenas: list[ArenaDef] = []
        for node in root.findall("arena"):
            platforms: list[Platform] = []
            platform_root = node.find("platforms")
            if platform_root is not None:
                for platform in platform_root.findall("platform"):
                    platforms.append(
                        Platform(
                            x=float(platform.attrib.get("x", 0)),
                            y=float(platform.attrib.get("y", 0)),
                            width=float(platform.attrib.get("width", 0)),
                            height=max(20.0, float(platform.attrib.get("height", 0))),
                        )
                    )
            arenas.append(
                ArenaDef(
                    key=node.attrib["pathname"],
                    name=node.attrib["name"],
                    width=int(node.attrib.get("width", 1920)),
                    height=int(node.attrib.get("height", 1080)),
                    ground=int(node.attrib.get("ground", 920)),
                    platforms=platforms,
                    background_path=GFX_ROOT / "arenas" / f"{node.attrib['pathname']}.png",
                )
            )
        return arenas

    def _rebuild_menu_buttons(self) -> None:
        self.menu_buttons = [
            Button(pygame.Rect(104, 250, 250, 62), "Play", "play", True),
            Button(pygame.Rect(104, 330, 250, 62), "Versus", "versus"),
            Button(pygame.Rect(104, 410, 250, 62), "Options", "options"),
            Button(pygame.Rect(104, 490, 250, 62), "Exit", "exit"),
        ]

    def run(self) -> int:
        while self.running:
            dt = self.clock.tick(FPS) / 1000.0
            self._handle_events()
            self._update(dt)
            self._draw_current_scene()
            pygame.display.flip()
        pygame.quit()
        return 0

    def _handle_events(self) -> None:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
            elif event.type == pygame.VIDEORESIZE and not self.fullscreen:
                self.window_size = (max(960, event.w), max(540, event.h))
                self.screen = pygame.display.set_mode(self.window_size, pygame.RESIZABLE)
                self.settings["window_size"] = list(self.window_size)
                save_settings(self.settings)
            elif event.type == pygame.KEYDOWN:
                if self.rebinding is not None:
                    self._apply_rebind(event.key)
                    continue
                if event.key == pygame.K_F11:
                    self._toggle_fullscreen()
                    continue
                if event.key == pygame.K_ESCAPE:
                    self._handle_escape()
                    continue
                self._handle_scene_keydown(event.key)
            elif event.type == pygame.MOUSEMOTION:
                self._handle_mouse_motion(self._to_virtual(event.pos))
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                self._handle_mouse_click(self._to_virtual(event.pos))

    def _to_virtual(self, pos: tuple[int, int]) -> tuple[int, int]:
        sw, sh = self.screen.get_size()
        return int(pos[0] * VIRTUAL_W / sw), int(pos[1] * VIRTUAL_H / sh)

    def _handle_escape(self) -> None:
        if self.scene == "match":
            self.match = None
            self.scene = "menu"
            self._play_music(self.assets.menu_music)
        elif self.scene in {"arena_select", "character_select", "options"}:
            self.scene = "menu"
        else:
            self.running = False

    def _toggle_fullscreen(self) -> None:
        self.fullscreen = not self.fullscreen
        self.settings["fullscreen"] = self.fullscreen
        self.screen = self._create_window()
        save_settings(self.settings)

    def _handle_scene_keydown(self, key: int) -> None:
        if self.scene == "menu":
            self._handle_menu_keys(key)
        elif self.scene == "character_select":
            self._handle_character_select_keys(key)
        elif self.scene == "arena_select":
            self._handle_arena_select_keys(key)
        elif self.scene == "options":
            self._handle_options_keys(key)

    def _handle_menu_keys(self, key: int) -> None:
        if key in (pygame.K_DOWN, pygame.K_s):
            self.menu_focus = (self.menu_focus + 1) % len(self.menu_buttons)
            self._play_sound(self.assets.ui_focus)
        elif key in (pygame.K_UP, pygame.K_w):
            self.menu_focus = (self.menu_focus - 1) % len(self.menu_buttons)
            self._play_sound(self.assets.ui_focus)
        elif key in (pygame.K_RETURN, pygame.K_SPACE):
            self._activate_menu_action(self.menu_buttons[self.menu_focus].action)

    def _activate_menu_action(self, action: str) -> None:
        if action == "play":
            self.selection_player_count = 1
            self._begin_character_selection()
        elif action == "versus":
            self.selection_player_count = 2
            self._begin_character_selection()
        elif action == "options":
            self.scene = "options"
        elif action == "exit":
            self.running = False
        self._play_sound(self.assets.ui_click)

    def _begin_character_selection(self) -> None:
        self.selection_slots = []
        self.selection_step = 0
        self.scene = "character_select"

    def _handle_character_select_keys(self, key: int) -> None:
        if key == pygame.K_LEFT:
            self.select_character_index = (self.select_character_index - 1) % len(self.characters)
            self._play_sound(self.assets.ui_focus)
        elif key == pygame.K_RIGHT:
            self.select_character_index = (self.select_character_index + 1) % len(self.characters)
            self._play_sound(self.assets.ui_focus)
        elif key in (pygame.K_MINUS, pygame.K_KP_MINUS):
            self.selection_rounds = max(1, self.selection_rounds - 1)
        elif key in (pygame.K_EQUALS, pygame.K_PLUS, pygame.K_KP_PLUS):
            self.selection_rounds = min(5, self.selection_rounds + 1)
        elif key in (pygame.K_p,):
            self.selection_player_count = 1 if self.selection_player_count == 2 else 2
        elif key in (pygame.K_RETURN, pygame.K_SPACE):
            self._confirm_character_selection(self.select_character_index)

    def _confirm_character_selection(self, index: int) -> None:
        if self.selection_step == 0:
            self.selection_slots = [index]
            if self.selection_player_count == 1:
                enemy = (index + 1) % len(self.characters)
                self.selection_slots.append(enemy)
                self.scene = "arena_select"
            else:
                self.selection_step = 1
        else:
            self.selection_slots.append(index)
            self.scene = "arena_select"
        self._play_sound(self.assets.ui_click)

    def _handle_arena_select_keys(self, key: int) -> None:
        if key == pygame.K_UP:
            self.select_stage_index = (self.select_stage_index - 1) % len(self.arenas)
            self._play_sound(self.assets.ui_focus)
        elif key == pygame.K_DOWN:
            self.select_stage_index = (self.select_stage_index + 1) % len(self.arenas)
            self._play_sound(self.assets.ui_focus)
        elif key in (pygame.K_RETURN, pygame.K_SPACE):
            self._start_match()

    def _handle_options_keys(self, key: int) -> None:
        if key == pygame.K_TAB:
            self.options_tab = "controls" if self.options_tab == "general" else "general"
        elif self.options_tab == "general":
            if key == pygame.K_LEFT:
                self.settings["rounds_to_win"] = max(1, self.settings["rounds_to_win"] - 1)
            elif key == pygame.K_RIGHT:
                self.settings["rounds_to_win"] = min(5, self.settings["rounds_to_win"] + 1)
            elif key == pygame.K_f:
                self._toggle_fullscreen()
            save_settings(self.settings)

    def _handle_mouse_motion(self, pos: tuple[int, int]) -> None:
        if self.scene == "menu":
            for idx, button in enumerate(self.menu_buttons):
                hovered = button.rect.collidepoint(pos)
                if hovered and not button.hovered:
                    self.menu_focus = idx
                    self._play_sound(self.assets.ui_focus)
                button.hovered = hovered

    def _handle_mouse_click(self, pos: tuple[int, int]) -> None:
        if self.scene == "menu":
            for idx, button in enumerate(self.menu_buttons):
                if button.rect.collidepoint(pos):
                    self.menu_focus = idx
                    self._activate_menu_action(button.action)
                    return
        elif self.scene == "character_select":
            for idx, rect in self._character_card_rects():
                if rect.collidepoint(pos):
                    self.select_character_index = idx
                    self._confirm_character_selection(idx)
                    return
        elif self.scene == "arena_select":
            for idx, rect in self._arena_row_rects():
                if rect.collidepoint(pos):
                    self.select_stage_index = idx
                    self._play_sound(self.assets.ui_focus)
                    return
            if pygame.Rect(980, 620, 220, 56).collidepoint(pos):
                self._start_match()
        elif self.scene == "options":
            self._handle_options_click(pos)

    def _handle_options_click(self, pos: tuple[int, int]) -> None:
        tab_general = pygame.Rect(110, 170, 180, 54)
        tab_controls = pygame.Rect(308, 170, 180, 54)
        if tab_general.collidepoint(pos):
            self.options_tab = "general"
            return
        if tab_controls.collidepoint(pos):
            self.options_tab = "controls"
            return
        if self.options_tab == "general":
            if pygame.Rect(220, 300, 220, 54).collidepoint(pos):
                self._toggle_fullscreen()
            elif pygame.Rect(220, 378, 220, 54).collidepoint(pos):
                self.settings["window_size"] = [1280, 720]
                self.window_size = (1280, 720)
                self.fullscreen = False
                self.settings["fullscreen"] = False
                self.screen = pygame.display.set_mode(self.window_size, pygame.RESIZABLE)
                save_settings(self.settings)
            elif pygame.Rect(730, 300, 64, 54).collidepoint(pos):
                self.settings["rounds_to_win"] = max(1, self.settings["rounds_to_win"] - 1)
                save_settings(self.settings)
            elif pygame.Rect(900, 300, 64, 54).collidepoint(pos):
                self.settings["rounds_to_win"] = min(5, self.settings["rounds_to_win"] + 1)
                save_settings(self.settings)
        else:
            for player_idx, action, rect in self._control_binding_rects():
                if rect.collidepoint(pos):
                    self.rebinding = (player_idx, action)
                    return

    def _apply_rebind(self, key: int) -> None:
        if self.rebinding is None:
            return
        player_idx, action = self.rebinding
        self.settings["keybindings"][player_idx][action] = key
        save_settings(self.settings)
        self.rebinding = None

    def _start_match(self) -> None:
        self.settings["player_count"] = self.selection_player_count
        self.settings["rounds_to_win"] = self.selection_rounds
        save_settings(self.settings)
        p1 = self.characters[self.selection_slots[0]]
        p2 = self.characters[self.selection_slots[1]]
        arena = self.arenas[self.select_stage_index]
        self.match = MatchState(
            self.assets,
            arena,
            p1,
            p2,
            self.selection_player_count,
            self.selection_rounds,
            self.settings["keybindings"],
            self.small_font,
            self.body_font,
        )
        self.scene = "match"
        self._play_music(self.assets.fight_music)
        self._play_sound(self.assets.ui_fight)

    def _update(self, dt: float) -> None:
        if self.scene == "menu":
            for idx, button in enumerate(self.menu_buttons):
                button.hovered = idx == self.menu_focus
        elif self.scene == "match" and self.match is not None:
            result = self.match.update(dt)
            if result == "finished":
                self.match = None
                self.scene = "menu"
                self._play_music(self.assets.menu_music)

    def _draw_current_scene(self) -> None:
        self.virtual.fill(BG)
        if self.scene == "menu":
            self._draw_menu()
        elif self.scene == "character_select":
            self._draw_character_select()
        elif self.scene == "arena_select":
            self._draw_arena_select()
        elif self.scene == "options":
            self._draw_options()
        elif self.scene == "match" and self.match is not None:
            self.match.draw(self.virtual, self.header_font, self.body_font, self.title_font)

        final = pygame.transform.smoothscale(self.virtual, self.screen.get_size())
        self.screen.blit(final, (0, 0))

    def _draw_menu(self) -> None:
        bg = self.assets.menu_backdrops[0] or next((b for b in self.assets.backgrounds.values() if b is not None), None)
        if bg is not None:
            self.virtual.blit(scale_cover(bg, (VIRTUAL_W, VIRTUAL_H)), (0, 0))
        veil = pygame.Surface((VIRTUAL_W, VIRTUAL_H), pygame.SRCALPHA)
        veil.fill((7, 10, 20, 80))
        self.virtual.blit(veil, (0, 0))

        if self.assets.title is not None:
            title = scale_to_box(self.assets.title, 700, 180)
            self.virtual.blit(title, title.get_rect(center=(700, 110)))
        else:
            surf = self.title_font.render("Fighter", True, TEXT)
            self.virtual.blit(surf, surf.get_rect(center=(700, 110)))

        for button in self.menu_buttons:
            button.draw(self.virtual, self.body_font)

        hint_panel = pygame.Rect(74, 590, 340, 92)
        draw_panel(self.virtual, hint_panel)
        lines = [
            f"Window: {'Fullscreen' if self.fullscreen else f'{self.window_size[0]}x{self.window_size[1]}'}",
            f"Rounds to win: {self.settings['rounds_to_win']}",
            "F11 toggles fullscreen",
        ]
        y = hint_panel.y + 14
        for line in lines:
            self.virtual.blit(self.small_font.render(line, True, MUTED), (hint_panel.x + 18, y))
            y += 24

        feature_panel = pygame.Rect(900, 220, 320, 380)
        draw_panel(self.virtual, feature_panel, tint=(42, 72, 122))
        self.virtual.blit(self.header_font.render("This Version Adds", True, TEXT), (feature_panel.x + 22, feature_panel.y + 18))
        items = [
            "Real character sprites",
            "1P vs CPU or 2-player local",
            "Rounds and arena setup",
            "Resizable window",
            "Fullscreen toggle",
            "Editable keybindings",
        ]
        y = feature_panel.y + 70
        for item in items:
            self.virtual.blit(self.body_font.render(f"• {item}", True, MUTED), (feature_panel.x + 22, y))
            y += 42

    def _draw_character_select(self) -> None:
        bg = self.assets.menu_backdrops[(self.selection_step + 1) % len(self.assets.menu_backdrops)]
        if bg is not None:
            self.virtual.blit(scale_cover(bg, (VIRTUAL_W, VIRTUAL_H)), (0, 0))
        overlay = pygame.Surface((VIRTUAL_W, VIRTUAL_H), pygame.SRCALPHA)
        overlay.fill((14, 18, 34, 60))
        self.virtual.blit(overlay, (0, 0))

        draw_header_bar(self.virtual, "Characters selection", "Select the fighters that will be fighting!", self.title_font, self.header_font)
        info = f"Players: {self.selection_player_count}    Rounds to win: {self.selection_rounds}"
        self.virtual.blit(self.body_font.render(info, True, TEXT), (78, 140))
        controls = "Left/Right choose fighter   Enter confirms   P toggles 1P/2P   +/- changes rounds"
        self.virtual.blit(self.small_font.render(controls, True, MUTED), (78, 176))

        for idx, rect in self._character_card_rects():
            char = self.characters[idx]
            active = idx == self.select_character_index
            selected = idx in self.selection_slots
            draw_panel(self.virtual, rect, tint=(65, 105, 164) if active else PANEL, border=char.color if selected or active else BORDER)
            portrait = scale_to_box(char.portrait, rect.width - 42, 260)
            self.virtual.blit(portrait, portrait.get_rect(center=(rect.centerx, rect.y + 150)))
            label = char.name
            if self.selection_player_count == 1 and len(self.selection_slots) == 1 and idx == self.selection_slots[1] if len(self.selection_slots) > 1 else False:
                label += " - AI"
            self.virtual.blit(self.header_font.render(label, True, TEXT), (rect.x + 18, rect.y + 298))
            meta = f"Power {char.strength:.0f}  Speed {char.speed:.0f}  Jump {char.jump_energy:.0f}"
            self.virtual.blit(self.small_font.render(meta, True, MUTED), (rect.x + 18, rect.y + 340))
            if self.selection_step == 1 and idx == self.selection_slots[0]:
                tag = self.small_font.render("Player 1", True, TEXT)
                self.virtual.blit(tag, (rect.right - tag.get_width() - 16, rect.y + 18))
            elif idx in self.selection_slots:
                slot_ix = self.selection_slots.index(idx) + 1
                tag = self.small_font.render(f"Player {slot_ix}", True, TEXT)
                self.virtual.blit(tag, (rect.right - tag.get_width() - 16, rect.y + 18))

        prompt = "Choose Player 1" if self.selection_step == 0 else "Choose Player 2"
        self.virtual.blit(self.header_font.render(prompt, True, TEXT), (78, 626))

    def _character_card_rects(self) -> list[tuple[int, pygame.Rect]]:
        rects = []
        card_w = 320
        gap = 36
        total = len(self.characters) * card_w + (len(self.characters) - 1) * gap
        start_x = (VIRTUAL_W - total) // 2
        for idx in range(len(self.characters)):
            rects.append((idx, pygame.Rect(start_x + idx * (card_w + gap), 220, card_w, 396)))
        return rects

    def _draw_arena_select(self) -> None:
        arena = self.arenas[self.select_stage_index]
        bg = self.assets.backgrounds.get(arena.key)
        if bg is not None:
            self.virtual.blit(scale_cover(bg, (VIRTUAL_W, VIRTUAL_H)), (0, 0))
        veil = pygame.Surface((VIRTUAL_W, VIRTUAL_H), pygame.SRCALPHA)
        veil.fill((10, 12, 26, 50))
        self.virtual.blit(veil, (0, 0))

        draw_header_bar(self.virtual, "Arena selection", "Select the arena where the fight will take place!", self.title_font, self.header_font)

        for idx, rect in self._arena_row_rects():
            active = idx == self.select_stage_index
            label_rect = rect
            draw_panel(self.virtual, label_rect, tint=ACCENT if active else PANEL, border=BORDER)
            text = self.header_font.render(self.arenas[idx].name, True, TEXT)
            self.virtual.blit(text, text.get_rect(center=label_rect.center))

        preview = pygame.Rect(560, 210, 650, 370)
        draw_panel(self.virtual, preview, tint=(55, 95, 155))
        if bg is not None:
            img = scale_cover(bg, preview.size)
            self.virtual.blit(img, preview)
        pygame.draw.rect(self.virtual, BORDER, preview, 4, border_radius=26)

        meta_panel = pygame.Rect(560, 596, 650, 72)
        draw_panel(self.virtual, meta_panel)
        meta = f"{arena.name}  |  Platforms {len(arena.platforms)}  |  World {arena.width}x{arena.height}"
        self.virtual.blit(self.body_font.render(meta, True, TEXT), (meta_panel.x + 20, meta_panel.y + 20))

        select_button = Button(pygame.Rect(980, 620, 220, 56), "Select", "confirm", True)
        select_button.draw(self.virtual, self.body_font)

    def _arena_row_rects(self) -> list[tuple[int, pygame.Rect]]:
        rects = []
        for idx in range(len(self.arenas)):
            rects.append((idx, pygame.Rect(86, 208 + idx * 58, 350, 50)))
        return rects

    def _draw_options(self) -> None:
        bg = self.assets.menu_backdrops[2] or self.assets.backgrounds.get("dojo")
        if bg is not None:
            self.virtual.blit(scale_cover(bg, (VIRTUAL_W, VIRTUAL_H)), (0, 0))
        veil = pygame.Surface((VIRTUAL_W, VIRTUAL_H), pygame.SRCALPHA)
        veil.fill((14, 18, 34, 95))
        self.virtual.blit(veil, (0, 0))
        draw_header_bar(self.virtual, "Options", "Change game parameters and key bindings!", self.title_font, self.header_font)

        panel = pygame.Rect(78, 170, 1120, 480)
        draw_panel(self.virtual, panel)
        tab_general = pygame.Rect(110, 170, 180, 54)
        tab_controls = pygame.Rect(308, 170, 180, 54)
        draw_panel(self.virtual, tab_general, tint=PANEL_SOFT if self.options_tab == "general" else PANEL)
        draw_panel(self.virtual, tab_controls, tint=PANEL_SOFT if self.options_tab == "controls" else PANEL)
        self.virtual.blit(self.header_font.render("General", True, TEXT), (tab_general.x + 40, tab_general.y + 12))
        self.virtual.blit(self.header_font.render("Controls", True, TEXT), (tab_controls.x + 34, tab_controls.y + 12))

        if self.options_tab == "general":
            self._draw_general_options(panel)
        else:
            self._draw_control_options(panel)

    def _draw_general_options(self, panel: pygame.Rect) -> None:
        left = pygame.Rect(panel.x + 48, panel.y + 74, 450, 320)
        right = pygame.Rect(panel.x + 584, panel.y + 74, 460, 320)
        draw_panel(self.virtual, left, tint=(64, 104, 164))
        draw_panel(self.virtual, right, tint=(64, 104, 164))
        self.virtual.blit(self.header_font.render("Display", True, TEXT), (left.x + 24, left.y + 18))
        self.virtual.blit(self.header_font.render("Match Defaults", True, TEXT), (right.x + 24, right.y + 18))

        fullscreen = "Fullscreen" if self.fullscreen else "Windowed"
        self.virtual.blit(self.body_font.render(f"Mode: {fullscreen}", True, TEXT), (left.x + 24, left.y + 72))
        self.virtual.blit(self.small_font.render(f"Window: {self.window_size[0]} x {self.window_size[1]}", True, MUTED), (left.x + 24, left.y + 112))
        Button(pygame.Rect(left.x + 24, left.y + 160, 220, 54), "Toggle Fullscreen", "fullscreen", True).draw(self.virtual, self.small_font)
        Button(pygame.Rect(left.x + 24, left.y + 238, 220, 54), "Reset To 1280x720", "reset").draw(self.virtual, self.small_font)
        self.virtual.blit(self.small_font.render("Drag the window border to resize at any time.", True, MUTED), (left.x + 24, left.y + 300))

        rounds = self.settings["rounds_to_win"]
        self.virtual.blit(self.body_font.render(f"Rounds to win: {rounds}", True, TEXT), (right.x + 24, right.y + 80))
        Button(pygame.Rect(right.x + 146, right.y + 70, 64, 54), "-", "rounds_down").draw(self.virtual, self.body_font)
        Button(pygame.Rect(right.x + 316, right.y + 70, 64, 54), "+", "rounds_up").draw(self.virtual, self.body_font)

        p1 = self.settings["keybindings"]["player1"]
        sample = [
            f"P1 Move: {pygame.key.name(p1['left'])} / {pygame.key.name(p1['right'])}",
            f"P1 Punch / Kick: {pygame.key.name(p1['punch'])} / {pygame.key.name(p1['kick'])}",
            f"P1 Block / Weapon: {pygame.key.name(p1['block'])} / {pygame.key.name(p1['weapon'])}",
            f"P1 Jump / Crouch: {pygame.key.name(p1['jump'])} / {pygame.key.name(p1['crouch'])}",
        ]
        y = right.y + 160
        for line in sample:
            self.virtual.blit(self.small_font.render(line, True, MUTED), (right.x + 24, y))
            y += 34

    def _draw_control_options(self, panel: pygame.Rect) -> None:
        left = pygame.Rect(panel.x + 38, panel.y + 74, 500, 360)
        right = pygame.Rect(panel.x + 580, panel.y + 74, 500, 360)
        draw_panel(self.virtual, left, tint=(64, 104, 164))
        draw_panel(self.virtual, right, tint=(64, 104, 164))
        self.virtual.blit(self.header_font.render("Player #1 key binder", True, TEXT), (left.x + 24, left.y + 18))
        self.virtual.blit(self.header_font.render("Player #2 key binder", True, TEXT), (right.x + 24, right.y + 18))

        for player_idx, action, rect in self._control_binding_rects():
            side = left if player_idx == "player1" else right
            if action == ACTIONS[0]:
                pass
            key_name = pygame.key.name(self.settings["keybindings"][player_idx][action])
            if self.rebinding == (player_idx, action):
                key_name = "Press a key..."
            label = self.small_font.render(ACTION_LABELS[action], True, TEXT)
            self.virtual.blit(label, (rect.x - 130, rect.y + 10))
            tint = PANEL_SOFT if self.rebinding == (player_idx, action) else PANEL
            draw_panel(self.virtual, rect, tint=tint)
            text = self.small_font.render(key_name.title(), True, TEXT)
            self.virtual.blit(text, text.get_rect(center=rect.center))

        self.virtual.blit(self.small_font.render("Click a binding, then press the new key.", True, MUTED), (left.x + 24, left.bottom - 32))
        self.virtual.blit(self.small_font.render("Player 2 becomes active automatically in Versus mode.", True, MUTED), (right.x + 24, right.bottom - 32))

    def _control_binding_rects(self) -> list[tuple[str, str, pygame.Rect]]:
        rects: list[tuple[str, str, pygame.Rect]] = []
        start_y = 280
        for side, player_idx, x in (("left", "player1", 255), ("right", "player2", 797)):
            for idx, action in enumerate(ACTIONS):
                rects.append((player_idx, action, pygame.Rect(x, start_y + idx * 38, 188, 30)))
        return rects


class MatchState:
    def __init__(
        self,
        assets: AssetBank,
        arena: ArenaDef,
        player1: CharacterDef,
        player2: CharacterDef,
        player_count: int,
        rounds_to_win: int,
        keybindings: dict[str, dict[str, int]],
        small_font: pygame.font.Font,
        body_font: pygame.font.Font,
    ) -> None:
        self.assets = assets
        self.arena = arena
        self.player_count = player_count
        self.rounds_to_win = rounds_to_win
        self.small_font = small_font
        self.body_font = body_font
        self.projectiles: list[Projectile] = []
        self.round_over_timer = 0.0
        self.banner = "Fight!"
        self.banner_timer = 1.2
        self.end_timer = 0.0
        self.background = assets.backgrounds.get(arena.key)
        self.platforms = arena.platforms
        self.scale = (VIRTUAL_H - 90) / arena.height
        self.view_width = VIRTUAL_W / self.scale
        self.camera_x = 0.0

        p1_idle = player1.sprite_frames["idle"]
        p2_idle = player2.sprite_frames["idle"]
        self.fighters = [
            FighterState(0, player1, 220, arena.ground - p1_idle.body_height, p1_idle.body_width, p1_idle.body_height, True, keybindings["player1"]),
            FighterState(1, player2, arena.width - 420, arena.ground - p2_idle.body_height, p2_idle.body_width, p2_idle.body_height, player_count == 2, keybindings["player2"], facing=-1),
        ]

    def update(self, dt: float):
        if self.end_timer > 0:
            self.end_timer -= dt
            return "finished" if self.end_timer <= 0 else None

        keys = pygame.key.get_pressed()
        if self.round_over_timer > 0:
            self.round_over_timer -= dt
            if self.round_over_timer <= 0:
                winner = max(self.fighters, key=lambda f: f.health)
                if winner.rounds_won >= self.rounds_to_win:
                    self.banner = f"{winner.character.name} wins!"
                    self.banner_timer = 2.0
                    self.end_timer = 2.0
                else:
                    self._reset_round()
            self._tick_banner(dt)
            return None

        self._update_human(self.fighters[0], self.fighters[1], keys, dt)
        if self.player_count == 2:
            self._update_human(self.fighters[1], self.fighters[0], keys, dt)
        else:
            self._update_ai(self.fighters[1], self.fighters[0], dt)

        for fighter in self.fighters:
            fighter.attack_cooldown = max(0.0, fighter.attack_cooldown - dt)
            fighter.special_cooldown = max(0.0, fighter.special_cooldown - dt)
            fighter.hit_flash = max(0.0, fighter.hit_flash - dt)
            fighter.attack_timer = max(0.0, fighter.attack_timer - dt)
            fighter.stun_timer = max(0.0, fighter.stun_timer - dt)
            if fighter.stun_timer <= 0:
                fighter.vy += GRAVITY * dt
                fighter.x += fighter.vx * dt
                fighter.y += fighter.vy * dt
                self._solve_collisions(fighter)
                fighter.x = max(0.0, min(self.arena.width - fighter.body_w, fighter.x))

        self._update_projectiles(dt)
        self._resolve_melee()
        self._face_each_other()
        self._update_camera()
        self._tick_banner(dt)
        self._check_round_end()
        return None

    def _tick_banner(self, dt: float) -> None:
        self.banner_timer = max(0.0, self.banner_timer - dt)

    def _reset_round(self) -> None:
        for idx, fighter in enumerate(self.fighters):
            fighter.health = 100.0
            fighter.vx = fighter.vy = 0.0
            fighter.attack_cooldown = 0.0
            fighter.special_cooldown = 0.0
            fighter.attack_timer = 0.0
            fighter.stun_timer = 0.0
            fighter.crouching = False
            fighter.blocking = False
            frame = fighter.character.sprite_frames["idle"]
            fighter.body_w = frame.body_width
            fighter.body_h = frame.body_height
            fighter.y = self.arena.ground - fighter.body_h
            fighter.x = 220 if idx == 0 else self.arena.width - 420
        self.projectiles.clear()
        self.banner = "Fight!"
        self.banner_timer = 1.2
        if self.assets.ui_fight is not None:
            self.assets.ui_fight.play()

    def _update_human(self, fighter: FighterState, opponent: FighterState, keys, dt: float) -> None:
        if fighter.stun_timer > 0:
            return
        fighter.vx = 0.0
        fighter.crouching = keys[fighter.control_map["crouch"]]
        fighter.blocking = keys[fighter.control_map["block"]]
        if keys[fighter.control_map["left"]]:
            fighter.vx -= fighter.move_speed
        if keys[fighter.control_map["right"]]:
            fighter.vx += fighter.move_speed
        if fighter.crouching:
            fighter.vx *= 0.35
        if keys[fighter.control_map["jump"]] and fighter.on_ground:
            fighter.vy = fighter.jump_velocity
            fighter.on_ground = False
        if keys[fighter.control_map["punch"]] and fighter.attack_cooldown <= 0:
            fighter.attack_kind = "punch"
            fighter.attack_timer = 0.18
            fighter.attack_cooldown = 0.38
        if keys[fighter.control_map["kick"]] and fighter.attack_cooldown <= 0:
            fighter.attack_kind = "kick"
            fighter.attack_timer = 0.20
            fighter.attack_cooldown = 0.46
        if keys[fighter.control_map["weapon"]] and fighter.special_cooldown <= 0:
            fighter.attack_kind = "weapon"
            fighter.attack_timer = 0.16
            fighter.special_cooldown = 0.95
            self._spawn_projectile(fighter)
        fighter.facing = 1 if opponent.center()[0] > fighter.center()[0] else -1

    def _update_ai(self, fighter: FighterState, opponent: FighterState, dt: float) -> None:
        if fighter.stun_timer > 0:
            return
        fighter.blocking = False
        fighter.crouching = False
        dx = opponent.center()[0] - fighter.center()[0]
        fighter.vx = 0.0
        if abs(dx) > 180:
            fighter.vx = fighter.move_speed * 0.85 * (1 if dx > 0 else -1)
        elif abs(dx) < 100:
            fighter.vx = -fighter.move_speed * 0.3 * (1 if dx > 0 else -1)
        if opponent.attack_timer > 0 and abs(dx) < 180 and random.random() < 0.08:
            fighter.blocking = True
        if fighter.on_ground and opponent.y + 80 < fighter.y and random.random() < 0.02:
            fighter.vy = fighter.jump_velocity
            fighter.on_ground = False
        if fighter.attack_cooldown <= 0 and abs(dx) < 130 and random.random() < 0.05:
            fighter.attack_kind = "punch" if random.random() < 0.6 else "kick"
            fighter.attack_timer = 0.20
            fighter.attack_cooldown = 0.48
        elif fighter.special_cooldown <= 0 and 180 < abs(dx) < 460 and random.random() < 0.025:
            fighter.attack_kind = "weapon"
            fighter.attack_timer = 0.15
            fighter.special_cooldown = 1.05
            self._spawn_projectile(fighter)
        fighter.facing = 1 if dx > 0 else -1

    def _spawn_projectile(self, fighter: FighterState) -> None:
        cx, cy = fighter.center()
        self.projectiles.append(Projectile(fighter.fighter_id, cx + fighter.facing * 40, cy - 40, fighter.facing * 1100))

    def _solve_collisions(self, fighter: FighterState) -> None:
        fighter.on_ground = False
        body = fighter.rect()
        if body.bottom >= self.arena.ground:
            body.bottom = self.arena.ground
            fighter.y = body.bottom - fighter.body_h
            fighter.vy = 0.0
            fighter.on_ground = True
        for platform in self.platforms:
            plat = pygame.Rect(int(platform.x), int(platform.y), int(platform.width), int(platform.height))
            current = fighter.rect()
            if fighter.vy >= 0 and current.colliderect(plat) and current.bottom - fighter.vy / FPS <= plat.top + 14:
                current.bottom = plat.top
                fighter.y = current.bottom - fighter.body_h
                fighter.vy = 0.0
                fighter.on_ground = True

    def _resolve_melee(self) -> None:
        self._try_hit(self.fighters[0], self.fighters[1])
        self._try_hit(self.fighters[1], self.fighters[0])

    def _try_hit(self, attacker: FighterState, defender: FighterState) -> None:
        if attacker.attack_timer <= 0 or attacker.attack_kind not in {"punch", "kick"}:
            return
        reach = 150 if attacker.attack_kind == "punch" else 190
        damage = 10 if attacker.attack_kind == "punch" else 14
        hitbox = pygame.Rect(int(attacker.x + attacker.body_w / 2), int(attacker.y + 60), reach, int(attacker.body_h - 90))
        if attacker.facing < 0:
            hitbox.x -= reach
        if hitbox.colliderect(defender.rect()):
            attacker.attack_timer = 0.0
            self._deal_damage(attacker, defender, damage, 360 * attacker.facing)

    def _deal_damage(self, attacker: FighterState, defender: FighterState, amount: float, knockback_x: float) -> None:
        if defender.blocking and attacker.facing != defender.facing:
            perfect = defender.attack_timer <= 0 and defender.stun_timer <= 0 and random.random() < 0.35
            defender.health = max(0.0, defender.health - (1.5 if perfect else 4.0))
            defender.vx += knockback_x * (0.08 if perfect else 0.16)
            if perfect:
                self.banner = "Perfect block!"
                self.banner_timer = 0.9
                self._play_block(perfect=True)
            else:
                self._play_block(perfect=False)
            return
        defender.health = max(0.0, defender.health - amount)
        defender.hit_flash = 0.18
        defender.stun_timer = 0.10
        defender.vx += knockback_x
        defender.vy = min(defender.vy, -650.0)

    def _play_block(self, perfect: bool) -> None:
        sound = self.assets.perfect_block_sound if perfect else self.assets.block_sound
        if sound is not None:
            sound.play()

    def _update_projectiles(self, dt: float) -> None:
        alive: list[Projectile] = []
        for projectile in self.projectiles:
            projectile.ttl -= dt
            projectile.x += projectile.vx * dt
            if projectile.ttl <= 0 or projectile.x < -150 or projectile.x > self.arena.width + 150:
                continue
            hit = False
            for fighter in self.fighters:
                if fighter.fighter_id == projectile.owner_id:
                    continue
                if fighter.rect().colliderect(
                    pygame.Rect(int(projectile.x - projectile.radius), int(projectile.y - projectile.radius), int(projectile.radius * 2), int(projectile.radius * 2))
                ):
                    self._deal_damage(self.fighters[projectile.owner_id], fighter, 9.0, projectile.vx * 0.24)
                    hit = True
                    break
            if not hit:
                alive.append(projectile)
        self.projectiles = alive

    def _face_each_other(self) -> None:
        if self.fighters[0].center()[0] < self.fighters[1].center()[0]:
            self.fighters[0].facing = 1
            self.fighters[1].facing = -1
        else:
            self.fighters[0].facing = -1
            self.fighters[1].facing = 1

    def _update_camera(self) -> None:
        midpoint = (self.fighters[0].center()[0] + self.fighters[1].center()[0]) / 2
        self.camera_x = max(0.0, min(self.arena.width - self.view_width, midpoint - self.view_width / 2))

    def _check_round_end(self) -> None:
        losers = [fighter for fighter in self.fighters if fighter.health <= 0]
        if not losers:
            return
        winner = max(self.fighters, key=lambda fighter: fighter.health)
        winner.rounds_won += 1
        self.banner = f"{winner.character.name} takes the round"
        self.banner_timer = 1.3
        self.round_over_timer = 1.5

    def draw(self, screen: pygame.Surface, header_font: pygame.font.Font, body_font: pygame.font.Font, title_font: pygame.font.Font) -> None:
        if self.background is not None:
            crop = crop_world_background(self.background, self.camera_x / max(1.0, self.arena.width - self.view_width), (VIRTUAL_W, VIRTUAL_H))
            screen.blit(crop, (0, 0))
        veil = pygame.Surface((VIRTUAL_W, VIRTUAL_H), pygame.SRCALPHA)
        veil.fill((14, 18, 30, 18))
        screen.blit(veil, (0, 0))

        for platform in self.platforms:
            rect = self.world_rect(platform.x, platform.y, platform.width, platform.height)
            draw_soft_rect(screen, rect, (140, 106, 70), radius=10)
            pygame.draw.rect(screen, (243, 219, 178), rect, 2, border_radius=10)

        for projectile in self.projectiles:
            center = self.world_point(projectile.x, projectile.y)
            if self.assets.shuriken is not None:
                angle = (pygame.time.get_ticks() * 0.9) % 360
                image = pygame.transform.rotozoom(self.assets.shuriken, angle, 0.28)
                screen.blit(image, image.get_rect(center=center))
            else:
                pygame.draw.circle(screen, TEXT, center, 12)

        for fighter in self.fighters:
            self._draw_fighter(screen, fighter)

        self._draw_hud(screen, header_font, body_font, title_font)

    def world_point(self, x: float, y: float) -> tuple[int, int]:
        return int((x - self.camera_x) * self.scale), int(y * self.scale)

    def world_rect(self, x: float, y: float, w: float, h: float) -> pygame.Rect:
        sx, sy = self.world_point(x, y)
        return pygame.Rect(sx, sy, max(2, int(w * self.scale)), max(2, int(h * self.scale)))

    def _draw_fighter(self, screen: pygame.Surface, fighter: FighterState) -> None:
        state = "idle"
        if fighter.stun_timer > 0:
            state = "hit"
        elif fighter.blocking:
            state = "block"
        elif fighter.attack_timer > 0 and fighter.attack_kind == "punch":
            state = "punch"
        elif fighter.attack_timer > 0 and fighter.attack_kind == "kick":
            state = "kick"
        elif not fighter.on_ground:
            state = "jump"
        elif fighter.crouching:
            state = "crouch"
        elif abs(fighter.vx) > 80:
            state = "run"

        frame = fighter.character.sprite_frames[state]
        target_h = 240 * self.scale * 1.9
        scale = target_h / frame.surface.get_height()
        sprite = pygame.transform.smoothscale(frame.surface, (max(1, int(frame.surface.get_width() * scale)), max(1, int(frame.surface.get_height() * scale))))
        if fighter.facing < 0:
            sprite = pygame.transform.flip(sprite, True, False)
        body = fighter.rect()
        sx, sy = self.world_point(body.x, body.bottom)
        draw_x = sx - (sprite.get_width() - int(body.width * self.scale)) // 2
        draw_y = sy - sprite.get_height()
        if fighter.hit_flash > 0:
            tint = sprite.copy()
            tint.fill((255, 255, 255, 90), special_flags=pygame.BLEND_RGBA_ADD)
            sprite = tint
        shadow = pygame.Rect(sx - 32, sy - 12, 64, 18)
        pygame.draw.ellipse(screen, (0, 0, 0, 90), shadow)
        screen.blit(sprite, (draw_x, draw_y))

    def _draw_hud(self, screen: pygame.Surface, header_font: pygame.font.Font, body_font: pygame.font.Font, title_font: pygame.font.Font) -> None:
        left_box = pygame.Rect(28, 20, 430, 86)
        right_box = pygame.Rect(VIRTUAL_W - 458, 20, 430, 86)
        draw_panel(screen, left_box, tint=(44, 74, 122), border=self.fighters[0].character.color)
        draw_panel(screen, right_box, tint=(44, 74, 122), border=self.fighters[1].character.color)
        self._draw_health_box(screen, left_box, self.fighters[0], align="left")
        self._draw_health_box(screen, right_box, self.fighters[1], align="right")
        center_text = body_font.render(f"First to {self.rounds_to_win}", True, MUTED)
        screen.blit(center_text, center_text.get_rect(center=(VIRTUAL_W // 2, 52)))
        score = header_font.render(f"{self.fighters[0].rounds_won}  -  {self.fighters[1].rounds_won}", True, TEXT)
        screen.blit(score, score.get_rect(center=(VIRTUAL_W // 2, 88)))
        if self.banner_timer > 0 and self.banner:
            surf = title_font.render(self.banner, True, TEXT)
            ribbon = surf.get_rect(center=(VIRTUAL_W // 2, 150)).inflate(58, 28)
            draw_panel(screen, ribbon, tint=(58, 92, 146), border=ACCENT_SOFT)
            screen.blit(surf, surf.get_rect(center=ribbon.center))

    def _draw_health_box(self, screen: pygame.Surface, box: pygame.Rect, fighter: FighterState, align: str) -> None:
        name = self.body_font.render(fighter.character.name, True, TEXT)
        portrait = scale_to_box(fighter.character.portrait, 80, 70)
        if align == "left":
            screen.blit(portrait, (box.x + 12, box.y + 8))
            screen.blit(name, (box.x + 104, box.y + 10))
            bar = pygame.Rect(box.x + 104, box.y + 48, 300, 20)
        else:
            screen.blit(portrait, (box.right - 92, box.y + 8))
            screen.blit(name, (box.right - 104 - name.get_width(), box.y + 10))
            bar = pygame.Rect(box.x + 24, box.y + 48, 300, 20)
        draw_soft_rect(screen, bar, (32, 42, 60), radius=10)
        fill = bar.copy()
        fill.width = int(bar.width * max(0.0, fighter.health) / 100.0)
        draw_soft_rect(screen, fill, SUCCESS if fighter.health > 35 else WARN, radius=10)
        pygame.draw.rect(screen, BORDER, bar, 2, border_radius=10)


def crop_world_background(background: pygame.Surface, progress: float, size: tuple[int, int]) -> pygame.Surface:
    progress = max(0.0, min(1.0, progress))
    scale = max(size[0] / background.get_width(), size[1] / background.get_height())
    scaled = pygame.transform.smoothscale(background, (max(1, int(background.get_width() * scale)), max(1, int(background.get_height() * scale))))
    if scaled.get_width() <= size[0]:
        crop_x = 0
    else:
        crop_x = int((scaled.get_width() - size[0]) * progress)
    crop_y = max(0, (scaled.get_height() - size[1]) // 2)
    return scaled.subsurface(pygame.Rect(crop_x, crop_y, size[0], size[1])).copy()


def scale_to_box(surface: pygame.Surface | None, max_w: int, max_h: int) -> pygame.Surface:
    if surface is None:
        fallback = pygame.Surface((max_w, max_h), pygame.SRCALPHA)
        draw_soft_rect(fallback, fallback.get_rect(), PANEL_SOFT, radius=18)
        return fallback
    sw, sh = surface.get_size()
    scale = min(max_w / sw, max_h / sh)
    return pygame.transform.smoothscale(surface, (max(1, int(sw * scale)), max(1, int(sh * scale))))


def scale_cover(surface: pygame.Surface, size: tuple[int, int]) -> pygame.Surface:
    tw, th = size
    sw, sh = surface.get_size()
    scale = max(tw / sw, th / sh)
    scaled = pygame.transform.smoothscale(surface, (max(1, int(sw * scale)), max(1, int(sh * scale))))
    crop = pygame.Rect(max(0, (scaled.get_width() - tw) // 2), max(0, (scaled.get_height() - th) // 2), tw, th)
    return scaled.subsurface(crop).copy()


def draw_soft_rect(surface: pygame.Surface, rect: pygame.Rect, color, radius: int = 24) -> None:
    if len(color) == 4:
        layer = pygame.Surface(rect.size, pygame.SRCALPHA)
        pygame.draw.rect(layer, color, layer.get_rect(), border_radius=radius)
        surface.blit(layer, rect.topleft)
    else:
        pygame.draw.rect(surface, color, rect, border_radius=radius)


def draw_panel(surface: pygame.Surface, rect: pygame.Rect, tint: tuple[int, int, int] = CARD, border=BORDER) -> None:
    draw_soft_rect(surface, rect.move(0, 10), SHADOW, radius=28)
    draw_soft_rect(surface, rect, tint, radius=28)
    pygame.draw.rect(surface, border, rect, 2, border_radius=28)


def draw_header_bar(surface: pygame.Surface, title: str, subtitle: str, title_font: pygame.font.Font, header_font: pygame.font.Font) -> None:
    bar = pygame.Rect(0, 0, VIRTUAL_W, 170)
    draw_soft_rect(surface, bar, PANEL, radius=0)
    surface.blit(title_font.render(title, True, TEXT), (24, 24))
    subtitle_surf = header_font.render(subtitle, True, TEXT)
    surface.blit(subtitle_surf, (VIRTUAL_W - subtitle_surf.get_width() - 28, 98))


def main() -> int:
    app = GameApp()
    return app.run()
