# Project: PyCraft Vanilla 1.8 Parity & Fabric Architecture

## Architecture
PyCraft is an authentic 1:1 Python/ModernGL/Pyxel recreation of Minecraft Vanilla 1.8 featuring Everest-scale LOD mountains, pixel-perfect 1.8 GUI, authentic copied assets, and a modular Fabric API.

```
                           +---------------------------+
                           |       main.py (Game)      |
                           +-------------+-------------+
                                         |
     +-------------------+---------------+-------------------+-------------------+
     |                   |                                   |                   |
+----+----+         +----+----+                         +----+----+         +----+----+
| UI Rndr |         | Physics |                         | WorldGen|         | Fabric  |
| 1.8 GUI |         |& Combat |                         | & LODs  |         |   API   |
+----+----+         +----+----+                         +----+----+         +----+----+
     |                   |                                   |                   |
+----+----+         +----+----+                         +----+----+         +----+----+
| Assets  |         | Sound   |                         | Chunk   |         | Mods &  |
| Vanilla |         | Manager |                         | Storage |         | Events  |
+---------+         +---------+                         +---------+         +---------+
```

### Subsystems:
1. **Asset Management (`pycraft-gpu/extract_vanilla_assets.py` & `assets/vanilla/`)**:
   - Local one-time extraction of PNG textures and OGG sounds from local installation (`/Users/Apple/Library/Application Support/minecraft`).
   - Zero .jar or prebuilt binaries in repository.
   - Procedural/synthetic fallback when reference assets are missing.
   - Absolute zero runtime dependency on external Minecraft directory.
2. **Audio Engine (`pycraft-gpu/sound_manager.py`)**:
   - 246 canonical 1.8 sound events mapped to local OGG audio files.
   - 3D spatialization: listener orientation, distance attenuation ($16 \times V$), natural pitch variation ($0.8 - 1.2$).
   - Multi-backend: `AfplayBackend`, `PyxelSynthBackend` fallback, and `SilentBackend` for testing.
3. **Fabric API (`pycraft-gpu/fabric_api/`)**:
   - Centralized registries (`Registries.BLOCK`, `ITEM`, `ENTITY_TYPE`, `SOUND_EVENT`, `SCREEN_HANDLER`, `BIOME`).
   - Namespaced identifiers (`Identifier`).
   - Fabric event bus (`FabricEvent`, `EventBus`) for game loop and action interception.
   - Mixin interception stubs (`@mixin`, `@inject`).
   - Mod discovery (`ModLoader`) parsing `fabric.mod.json`.
4. **WorldGen & LODs (`pycraft-gpu/generator.py`, `chunk.py`, `lod.py`)**:
   - Vertical bounds: $Y \in [-64, 512)$ (36 vertical subchunks of $16 \times 16 \times 16$).
   - Everest generation: multi-octave ridge noise with jagged summits peaking $> Y=400$, snow caps above $Y=200..250$, stone layers.
   - Watertight LOD meshes: `UV_INSET = 0.05 / 16` and vertical boundary skirts preventing inter-subchunk cracks.
   - Backward compatibility: preserves 24-subchunk defaults/compatibility for existing tests.
5. **Gameplay Mechanics (`pycraft-gpu/combat.py`, `player.py`)**:
   - 1.8 Combat: no 1.9 attack cooldown (unrestricted spam clicking).
   - Critical hits: falling downward ($v_y < 0$), deal +50% damage with crit particles.
   - 1.8 Armor: flat 4% damage reduction per defense point (max 80% at 20 points), 10-tick invulnerability window.
   - Sneak safe-edge: bounding box clamping preventing stepping off solid blocks into air.
6. **Pixel-Perfect 1.8 UI (`pycraft-gpu/ui_renderer.py`, `main.py`)**:
   - Integer GUI scaling (1x, 2x, 3x, 4x) using nearest-neighbor sampling (`GL_NEAREST`).
   - In-game HUD: 182x22 hotbar, 10 hearts (flash/shake), 10 armor, 10 food (shake), 10 oxygen bubbles, green XP bar with centered level text, inverted crosshair (`GL_ONE_MINUS_DST_COLOR`).
   - Containers: Survival inventory (176x166 px) with 2x2 craft, armor slots, 3D Steve preview; Crafting table (176x166 px) 3x3; Furnace (176x166 px) with animated flame (14px) and arrow (24px); Single/Double chests (176x166 px & 176x222 px); Creative inventory (195x136 px) with 12 tabs and scrollbar.
   - Widgets & Tooltips: 9-slice buttons, slot hover highlight `rgba(255,255,255,0.5)`, item stack count drop shadows, durability bars, double purple border tooltips (#100010 background, #5000FF outer border, #28007F inner border).

---

## Feature Inventory
| # | Feature | Description | Milestone | Source |
|---|---------|-------------|-----------|--------|
| 1 | Asset Extraction Script | Local extraction of PNGs and OGGs into `assets/vanilla/`, no jars committed | M1 | Survey / R1 |
| 2 | Zero Runtime Jar Dependency | Game loads only from local assets directory without referencing external paths | M1 | Survey / R1 |
| 3 | Procedural Asset Fallback | Procedural texture and synthetic sound generation if local assets missing | M1 | Survey / R1 |
| 4 | Sound Event Registry | 246 canonical 1.8 sound events mapped to local OGG files | M1 | Survey / R3 |
| 5 | 3D Audio Spatialization | Listener-relative 3D position, distance attenuation ($16 \times V$), stereo pan | M1 | Survey / R3 |
| 6 | Audio Pitch Variation | Random pitch scaling between 0.8 and 1.2 per sound event play | M1 | Survey / R3 |
| 7 | Multi-Backend Audio Engine | macOS audio backend + Pyxel synth fallback + Silent test backend | M1 | Survey / R3 |
| 8 | Fabric Identifier | `Identifier("namespace", "path")` with string parsing and validation | M2 | Survey / R6 |
| 9 | Fabric Registries | Centralized typed registry for BLOCK, ITEM, ENTITY_TYPE, SOUND_EVENT, SCREEN_HANDLER, BIOME | M2 | Survey / R6 |
| 10 | Fabric Event Bus | Standard event callbacks (`ServerTickEvents`, `ClientTickEvents`, `AttackBlockCallback`, etc.) | M2 | Survey / R6 |
| 11 | Fabric Mixin System | `@mixin` class decorator and `@inject` method interceptor with `CallbackInfo` | M2 | Survey / R6 |
| 12 | Fabric Mod Loader | Scanning `mods/` directory, parsing `fabric.mod.json`, instantiating `ModInitializer` | M2 | Survey / R6 |
| 13 | Extended Vertical Chunk Height | Support for $Y \in [-64, 512)$ (36 vertical subchunks of 16x16x16) | M3 | Survey / R4 |
| 14 | Homogeneous Subchunk Compression | Air and uniform subchunks stored with single palette entry (<16 bytes) | M3 | Survey / R4 |
| 15 | Everest Mountain Generation | Multi-octave ridged noise generating peaks $> Y=400$ | M3 | Survey / R4 |
| 16 | Altitudinal Biome Stratification | Stone cliffs and permanent snow caps above $Y=200..250$ | M3 | Survey / R4 |
| 17 | Watertight LOD Meshing | `UV_INSET = 0.05 / 16` and boundary skirts preventing inter-subchunk cracks | M3 | Survey / R4 |
| 18 | WorldGen Backward Compatibility | Existing 24-subchunk tests continue passing with zero regressions | M3 | Survey / R4 |
| 19 | 1.8 Unrestricted Combat | No 1.9 attack cooldown / attack speed indicator; full spam clicking | M4 | Survey / R5 |
| 20 | 1.8 Critical Hits | +50% damage bonus and crit particles on downward vertical velocity ($v_y < 0$) | M4 | Survey / R5 |
| 21 | 1.8 Flat Armor Formula | Exactly 4% damage reduction per defense point (max 80% at 20 points) | M4 | Survey / R5 |
| 22 | 10-Tick Damage Immunity | 0.5s invulnerability window with higher damage delta calculation | M4 | Survey / R5 |
| 23 | Sneak Safe-Edge Physics | Movement bounding box clamping preventing stepping off solid blocks | M4 | Survey / R5 |
| 24 | Integer GUI Scaling | Integer scale factors (1x, 2x, 3x, 4x) using `GL_NEAREST` sampling | M5 | Survey / R2 |
| 25 | Authentic HUD Layout | 182x22 hotbar, 10 hearts with flash/shake, armor, food with shake, bubbles, XP bar, crosshair | M5 | Survey / R2 |
| 26 | Survival Inventory 176x166 | 2x2 crafting grid, 4 armor slots, 3x9 inventory, 1x9 hotbar | M5 | Survey / R2 |
| 27 | 3D Steve Inventory Preview | 51x72 px preview window with rotating 3D player tracking mouse cursor | M5 | Survey / R2 |
| 28 | Crafting Table GUI 176x166 | 3x3 crafting grid, indicative arrow, result slot | M5 | Survey / R2 |
| 29 | Furnace GUI 176x166 | Animated burning flame (14px) and cook progress arrow (24px) | M5 | Survey / R2 |
| 30 | Single & Double Chest GUIs | 176x166 px (27 slots) and 176x222 px (54 slots) container screens | M5 | Survey / R2 |
| 31 | Creative Inventory GUI 195x136 | 12 tabs, 5x9 grid (45 slots), draggable scrollbar thumb (12x15 px), search tab | M5 | Survey / R2 |
| 32 | Double Purple Border Tooltips | #100010 background, #5000FF outer border, #28007F inner border, rarity colors | M5 | Survey / R2 |
| 33 | 9-Slice Widgets & Durability | Standard 9-slice buttons, slot hover highlight, stack count drop shadows, durability bars | M5 | Survey / R2 |
| 34 | Full 100% E2E Test Suite Pass | 100% pass on Tiers 1-4 comprehensive opaque-box E2E test suite | M-FINAL | Project Pattern |
| 35 | Tier 5 Adversarial Coverage Hardening | White-box adversarial testing, edge case probing, bug remediation | M-FINAL | Project Pattern |

---

## Milestones
| # | Name | Scope | Dependencies | Status |
|---|------|-------|-------------|--------|
| M1 | Asset Ingestion & Audio Engine | Features 1–7: `extract_vanilla_assets.py`, `sound_manager.py`, asset tests | None | DONE |
| M2 | Fabric Mod Architecture | Features 8–12: `fabric_api/` (identifier, registry, events, mixin, mod_loader) | None | PLANNED |
| M3 | Everest WorldGen & Watertight LODs | Features 13–18: `chunk.py` (Y=-64..512), `generator.py` (peaks > Y=400), `lod.py` | None | PLANNED |
| M4 | Authentic 1.8 Combat & Physics | Features 19–23: `combat.py` (1.8 formulas), `player.py` (sneak safe-edge) | None | PLANNED |
| M5 | Pixel-Perfect 1.8 User Interfaces | Features 24–33: `ui_renderer.py`, HUD & Containers in `main.py` | M1, M2 | PLANNED |
| M-FINAL | Integration, E2E Pass & Hardening | Features 34–35: Pass 100% E2E tests (Tiers 1-4) + Tier 5 Hardening | M1..M5, E2E Suite | PLANNED |

---

## Interface Contracts

### 1. `sound_manager.py` ↔ Game Engine (`main.py`, `player.py`, `combat.py`)
```python
class SoundManager:
    def play_sound(
        self,
        event_name: str,
        pos: tuple[float, float, float] | None = None,
        volume: float = 1.0,
        pitch: float = 1.0,
        pitch_variance: float = 0.2
    ) -> None:
        """Plays 1.8 sound event with 3D attenuation relative to player eye position."""
        ...
    def update_listener(self, pos: tuple[float, float, float], yaw: float, pitch: float) -> None:
        """Updates player eye position and camera orientation for spatial panning."""
        ...
    def stop_all(self) -> None:
        """Halts all active sound playbacks."""
        ...
```

### 2. `fabric_api` ↔ Game Engine
```python
class Identifier:
    namespace: str
    path: str
    def __init__(self, namespace_or_string: str, path: str | None = None) -> None: ...

class Registry[T]:
    def register(self, identifier: Identifier, entry: T) -> T: ...
    def get(self, identifier: Identifier) -> T | None: ...

class Registries:
    BLOCK: Registry
    ITEM: Registry
    ENTITY_TYPE: Registry
    SOUND_EVENT: Registry
    SCREEN_HANDLER: Registry
    BIOME: Registry

class EventBus:
    ServerTickEvents: Event
    ClientTickEvents: Event
    AttackBlockCallback: Event
    UseBlockCallback: Event
    UseItemCallback: Event
    HudRenderCallback: Event
```

### 3. `ui_renderer.py` ↔ `main.py`
```python
class UIRenderer:
    def set_gui_scale(self, scale_mode: str | int, window_width: int, window_height: int) -> int: ...
    def draw_container(self, container_type: str, x: int, y: int, data: dict) -> None: ...
    def draw_tooltip(self, lines: list[tuple[str, tuple[int, int, int]]], mouse_x: int, mouse_y: int) -> None: ...
    def draw_3d_player_preview(self, x: int, y: int, width: int, height: int, mouse_x: int, mouse_y: int, tick: int) -> None: ...
    def draw_hud(self, player_stats: dict, hotbar_slots: list, active_slot: int) -> None: ...
```

### 4. `chunk.py` & `generator.py` ↔ Engine
```python
# Extended chunk dimensions
CHUNK_Y_MIN = -64
CHUNK_Y_MAX = 512
CHUNK_SUBCHUNKS = 36  # cy in range [-4, 32)
# Backward-compatibility API for legacy tests:
DEFAULT_SUBCHUNKS = 24  # maintains existing 222 tests
```

---

## Code Layout
```
pycraft-gpu/
├── assets/
│   └── vanilla/
│       ├── textures/          # Extracted vanilla 1.8 PNG textures
│       └── sounds/            # Extracted vanilla 1.8 OGG sounds
├── fabric_api/                # [M2] Fabric mod architecture
│   ├── __init__.py
│   ├── identifier.py
│   ├── registry.py
│   ├── events.py
│   ├── mixin.py
│   └── mod_loader.py
├── extract_vanilla_assets.py  # [M1] Asset extraction tool
├── sound_manager.py           # [M1] Audio engine & 3D spatializer
├── ui_renderer.py             # [M5] Pixel-perfect 1.8 UI engine
├── chunk.py                   # [M3] Extended chunk storage & compression
├── generator.py               # [M3] Everest world generation
├── lod.py                     # [M3] Watertight Distant Horizons LOD meshing
├── combat.py                  # [M4] 1.8 combat damage & armor formulas
├── player.py                  # [M4] 1.8 sneak safe-edge & physics
└── main.py                    # [M5] UI container integration & HUD

tests/
├── test_ui_pixel_perfect.py   # [M5 / E2E] UI pixel parity tests
├── test_sound_manager.py      # [M1 / E2E] Audio event & spatialization tests
├── test_fabric_api.py         # [M2 / E2E] Fabric registry, events & mixin tests
├── test_everest_height.py     # [M3 / E2E] Everest generation & subchunk tests
├── test_combat_1_8.py         # [M4 / E2E] 1.8 combat & sneak edge tests
└── e2e/                       # [E2E Testing Track] Tiers 1-4 opaque-box suite
```

---

## Write Ownership
To prevent race conditions during parallel development:
- **E2E Testing Track**: Owns `tests/e2e/`, `TEST_INFRA.md`, `TEST_READY.md`. Read-only on `pycraft-gpu/`.
- **M1 Worker**: Owns `pycraft-gpu/extract_vanilla_assets.py`, `pycraft-gpu/sound_manager.py`, `pycraft-gpu/assets/`, `tests/test_sound_manager.py`.
- **M2 Worker**: Owns `pycraft-gpu/fabric_api/*`, `tests/test_fabric_api.py`.
- **M3 Worker**: Owns `pycraft-gpu/chunk.py`, `pycraft-gpu/generator.py`, `pycraft-gpu/lod.py`, `tests/test_everest_height.py`.
- **M4 Worker**: Owns `pycraft-gpu/combat.py`, `pycraft-gpu/player.py`, `tests/test_combat_1_8.py`.
- **M5 Worker**: Owns `pycraft-gpu/ui_renderer.py`, `pycraft-gpu/main.py`, `tests/test_ui_pixel_perfect.py`.
