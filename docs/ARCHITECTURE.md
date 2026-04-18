# ARCHITECTURE

Project: `asteroids_single-player`

## 1. Purpose

This document describes the current architecture of the project.

Scope:
- Python code in `core/`, `client/`, and `main.py`
- Documentation in `docs/`
- Assets in `assets/`

This project is still single-player.

## 2. Current Repository Structure

```text
asteroids_single-player/
├── assets/
│   └── sounds/
├── client/
│   ├── audio.py
│   ├── controls.py
│   ├── game.py
│   └── renderer.py
├── core/
│   ├── commands.py
│   ├── config.py
│   ├── entities.py
│   ├── utils.py
│   └── world.py
├── docs/
│   └── ARCHITECTURE.md
└── main.py
```

Audio files in `assets/sounds/`:
- `asteroid_explosion.wav`
- `player_shoot.wav`
- `ship_explosion.wav`
- `thrust_loop.wav`
- `ufo_shoot.wav`
- `ufo_siren_big.wav`
- `ufo_siren_small.wav`

## 3. Responsibilities by File

### `main.py`

Entry point.

Current responsibilities:
- Imports `Game` from `client.game`
- Runs `Game().run()`

### `client/game.py`

Orchestrates the game loop, scenes, and pygame integration.

Current responsibilities:
- Pygame and mixer initialization
- Window, clock, and font creation
- Scene control (`menu`, `play`, `game_over`)
- Event reading and game exit
- Uses `InputMapper` to convert input into commands
- Calls `World.update(dt, commands)`
- Draws menu, game over, and world
- Plays audio based on `world.events`
- Controls audio loops (thrust and UFO siren)

### `client/renderer.py`

Client-side rendering.

Current responsibilities:
- Screen clearing
- Scene drawing (`menu`, `game_over`)
- World drawing from sprites exposed by `World`
- HUD drawing

### `client/controls.py`

Local input mapping to player commands.

Current responsibilities:
- `InputMapper` class
- Captures `KEYDOWN` events for `shoot` and `hyperspace`
- Reads continuous keys for rotation and thrust
- Builds `PlayerCommand`

### `client/audio.py`

Sound effect loading.

Current responsibilities:
- `SoundPack` with `pygame.mixer.Sound` references
- `load_sounds(base_path)` to load sounds from `core.config`

### `core/world.py`

Core game rules (`World`).

Current responsibilities:
- Game state: ships, bullets, asteroids, UFOs, score, lives, wave
- Player, asteroid, and UFO spawning
- Command application by `player_id`
- Per-frame simulation update
- Collision handling
- Scoring, death, and game over rules
- Domain event generation in `world.events`

### `core/entities.py`

Game entities based on `pygame.sprite.Sprite`.

Current responsibilities:
- Classes: `Ship`, `Asteroid`, `Bullet`, `UFO`
- Physics and local update for each entity
- Firing rules for `Ship` and `UFO`
- `UFO_BULLET_OWNER` constant

### `core/commands.py`

Player intent contract.

Current responsibilities:
- Immutable `dataclass` `PlayerCommand`
- Flags: `rotate_left`, `rotate_right`, `thrust`, `shoot`, `hyperspace`

### `core/utils.py`

Math utilities.

Current responsibilities:
- `Vec` alias (`pygame.math.Vector2`)
- Vector and geometry helpers (`wrap_pos`, `angle_to_vec`, etc.)

### `core/config.py`

Central game configuration.

Current responsibilities:
- Screen, FPS, and ID constants
- Ship, bullet, asteroid, and UFO parameters
- Colors and asset paths
- Sound file names

### `docs/`

Project documentation.

Current state:
- Contains this document (`ARCHITECTURE.md`)

### `assets/`

Static game resources.

Current state:
- `sounds/` folder with WAV effects used by the pygame client

## 4. Module Dependencies (Current)

Main import flow observed today:
- `main.py` -> `client.game`
- `client.game` -> `client.audio`, `client.controls`, `client.renderer`,
  `core.config`, `core.world`
- `client.controls` -> `core.commands`
- `client.audio` -> `core.config`
- `client.renderer` -> `core.config`, `core.entities`
- `core.world` -> `core.config`, `core.commands`, `core.entities`,
  `core.utils`
- `core.entities` -> `core.config`, `core.commands`, `core.utils`
- `core.utils` -> `core.config`

Architectural health rule:
- Avoid circular imports

## 5. Architectural Notes

The current separation between `core/` and `client/` already exists and is in use.

Important:
- `client/` concentrates pygame integration for input, rendering, and audio.
- `core/` concentrates rules, game state, and entities.
- `core/` still depends on `pygame.sprite` and `pygame.math.Vector2`, so
  it is not a fully framework-agnostic layer.
- The current rendering flow goes through `client.renderer`; `World` is not
  responsible for drawing HUD or sprites.

## 6. Quality Analysis

### 6.1 Cohesion (7/10)

Strengths:
- `config.py` has perfect single responsibility (constants only)
- `commands.py` is a pure dataclass with no behavior
- Each entity (`Bullet`, `Asteroid`, `Ship`, `UFO`) has clear focus

Areas for improvement:
- `Game` (client/game.py) accumulates too many responsibilities: game loop,
  pygame initialization, audio channel management, UFO siren logic, and
  event handling. Should extract `AudioManager`.
- `World` (core/world.py) mixes game state with 77 lines of collision
  detection (5 methods). Should extract `CollisionManager`.
- `Ship.apply_command` mixes input response with physics (rotation, thrust,
  friction, and firing in the same method).

### 6.2 Coupling (5/10)

Main problem: core/ directly depends on pygame:
- Entities inherit from `pygame.sprite.Sprite`
- `World` uses `pygame.sprite.Group`
- `Vec` is an alias for `pygame.math.Vector2`
- The core/client separation is partial -- core is not framework-agnostic

Other issues:
- `Renderer` uses `isinstance` chains to decide how to draw each
  entity -- impossible to add a new entity without modifying Renderer.
- Global config `C.` imported in ~35 references without dependency injection.
- Audio logic (sirens, channels) mixed directly into `Game`.

### 6.3 Maintainability (6/10)

Magic numbers scattered throughout the code:
- `entities.py`: polygon steps (12/10/8), jitter (0.75-1.2), ship
  angle (140.0), bullet spawn offset (+6)
- `world.py`: minimum spawn distance (150), split speed multiplier (1.2),
  wave count (3 + wave)
- `game.py`: audio config (44100, -16, 2, 512), font sizes (22, 64)
- `renderer.py`: layout positions (170, 350, 340, 260)

Code duplication:
- Timer/countdown pattern repeated 5+ times without a utility
- 5 collision methods with repetitive structure

Known bug:
- Hyperspace can teleport the player inside an asteroid (no safe
  position check).

### 6.4 Readability (7/10)

Strengths:
- Descriptive names: `rotate_left`, `spawn_player()`, `_handle_collisions()`
- Type hints present on most signatures
- Consistent private method `_` prefix

Areas for improvement:
- Scenes as hardcoded strings ("menu", "play", "game_over") instead of Enum
- `UFO_BULLET_OWNER = -10` without explanatory comment

## 7. Multiplayer Preparation

### 7.1 What is already in place

The current architecture facilitates conversion in several ways:

- `World.update(dt, commands: dict[int, PlayerCommand])` already accepts
  multiple players by design.
- `World.ships: dict[int, Ship]` indexed by player_id.
- `Bullet.owner` tracks who fired each bullet.
- `PlayerCommand` as a dataclass is easy to serialize for networking.
- core/client separation already exists (even with pygame coupling).

### 7.2 What needs to change

Required refactorings before conversion:

1. **Decouple core from pygame** -- entities should not inherit from
   `pygame.sprite.Sprite`; create custom interfaces so that core/
   is framework-agnostic.

2. **Extract CollisionManager** -- 77 lines of collision code in `World`
   should go into a separate class, making testing and rule modification easier.

3. **Per-player score** -- `self.score` is currently global; needs to be
   `dict[int, int]` indexed by player_id.

4. **Per-player lives** -- `self.lives` needs to be per player, with
   partial game over (one player dies, another continues).

5. **Multi-player spawning** -- `spawn_player()` already receives `pid`,
   but needs to manage distinct starting positions.

6. **Networking** -- serialize `PlayerCommand` (send) and `World`
   state (sync between clients).

7. **Multi-player HUD** -- display score/lives for each player.

8. **Lobby** -- waiting screen before the game starts.

9. **Eliminate magic numbers** -- centralize in `config.py` before
   adding multiplayer complexity.
