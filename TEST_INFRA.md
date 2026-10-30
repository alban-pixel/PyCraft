# PyCraft Vanilla 1.8 Parity & Fabric Architecture: E2E Test Infrastructure

## 1. Overview & Test Philosophy

The PyCraft End-to-End (E2E) Test Suite provides systematic, requirement-driven, opaque-box testing for the complete Minecraft Vanilla 1.8 parity engine, Everest mountain generation with Distant Horizons LOD meshing, pixel-perfect 1.8 user interfaces, and the Fabric modding architecture.

### Core Principles
1. **Opaque-Box Verification**: Tests interact strictly through public module interfaces, CLI/tool scripts, standard data structures, and game loop contracts rather than coupling to internal private state.
2. **Deterministic & Self-Contained**: Each test initializes its own environment, creates isolated mock/synthetic data (in temporary directories or fixtures), and cleans up cleanly without execution order dependencies.
3. **Progressive Testability**: Verification of core features does not presuppose higher-level abstractions. Tests isolate feature contracts so that each implementation milestone (M1 through M5) can be independently verified.
4. **Adversarial & Boundary Rigor**: Tests deliberately probe boundary limits (Y=-64..512, peak heights > 400), invalid or malformed data (corrupt mod configs, invalid namespaces), zero/negative values, and cross-subsystem edge interactions.

---

## 2. Directory Layout & Test Suite Architecture

```
radiant-pasteur/
├── TEST_INFRA.md               # [This document] E2E test infrastructure specification
├── TEST_READY.md               # Official test readiness declaration and runner instructions
├── tests/
│   ├── conftest.py             # Root pytest configuration & headless Pyxel session fixture
│   └── e2e/
│       ├── __init__.py         # E2E package root
│       ├── conftest.py         # E2E fixtures (temp dirs, mock assets, silent sound engine)
│       ├── test_tier1_features.py     # Tier 1: 1:1 Feature coverage across Features 1-33
│       ├── test_tier2_boundaries.py   # Tier 2: Boundary limits, extreme coordinates, edge cases
│       ├── test_tier3_interactions.py # Tier 3: Pairwise & cross-feature multi-system combinations
│       ├── test_tier4_scenarios.py    # Tier 4: Real-world survival, smelting, climbing, save/mod workflows
│       └── runner.py           # Standalone CLI test runner with tier filtering and reporting
```

---

## 3. Systematic 4-Tier Test Design

### Tier 1: Feature Coverage (`test_tier1_features.py`)
Validates nominal behavior for each inventoried feature in `PROJECT.md § Feature Inventory` (#1 through #33):
- **Features 1–3**: Asset extraction script, zero runtime JAR dependency, and procedural asset fallback.
- **Features 4–7**: Sound event registry (246 canonical 1.8 events), 3D spatial attenuation ($16 \times V$), random pitch scaling ($0.8 - 1.2$), and multi-backend audio (Afplay, Pyxel synth, Silent).
- **Features 8–12**: Fabric API foundations: `Identifier`, typed `Registries`, `EventBus` priority/cancellation, `@mixin` / `@inject` interception, and `ModLoader` discovery.
- **Features 13–18**: Extended vertical chunk height ($Y \in [-64, 512)$, 36 subchunks), homogeneous palette compression, Everest mountain generation (peaks $> Y=400$), altitudinal biome stratification, watertight LOD meshing (`UV_INSET = 0.05 / 16`), and backward compatibility.
- **Features 19–23**: Authentic 1.8 combat mechanics: unrestricted spam clicking, jump/fall critical hits ($v_y < 0$, $+50\%$ damage), 1.8 flat 4% armor formula, 10-tick damage immunity window, and sneak safe-edge physics.
- **Features 24–33**: Pixel-perfect 1.8 UI: integer GUI scaling (1x–4x, `GL_NEAREST`), authentic HUD layout, survival inventory (176x166 px), 3D Steve preview (51x72 px), crafting table (176x166 px), furnace (176x166 px with flame/arrow), single/double chest (176x166 / 176x222 px), creative inventory (195x136 px), double purple border tooltips (`#100010`, `#5000FF`, `#28007F`), and 9-slice widgets with durability bars.

### Tier 2: Boundary & Corner Cases (`test_tier2_boundaries.py`)
Stress-tests extreme and pathological conditions:
- **Chunk & World Boundaries**: $Y = -64$ (minimum floor), $Y = 511$ (maximum ceiling), $Y = 512$ (out of bounds error), subchunk indices $cy = -4$ and $cy = 31$.
- **Combat & Damage Limits**: $0.0$ damage attacks, negative damage, $0$ armor defense, $20$ armor defense (exact $80\%$ reduction), extreme incoming damage ($1000.0$ damage), 10-tick immunity timing boundaries (ticks 0, 1, 9, 10, 11), lower vs higher incoming damage differentials.
- **Audio Boundaries**: $0.0$m listener distance (full volume), extreme distance ($> 1000$m distance attenuation clamping), pitch extremes at $[0.8, 1.2]$, empty or unregistered sound event names.
- **Fabric Boundaries**: Malformed identifiers, empty namespaces, unregistered registry lookups, mixin interception on non-existent targets, missing `fabric.mod.json`, corrupted JSON configs.
- **UI & Display Boundaries**: Zero and negative window dimensions, extreme display resolutions (320x180 min to 3840x2160 4K), empty tooltip lists, tool durability at $0$, $1$, max, and negative values.

### Tier 3: Cross-Feature Combinations (`test_tier3_interactions.py`)
Validates pairwise and multi-system interactions between independent subsystems:
- **Combat while Sneaking**: Player holds sneak on a block ledge, attacks a mob or takes damage, verifying sneak safe-edge clamping holds during knockback and 10-tick invulnerability.
- **UI Tooltips during Container Operations**: Hovering over container slots (Survival, Crafting, Furnace, Double Chest) generates authentic double purple border tooltips with stack count drop shadows.
- **3D Audio during Block Mining**: Mining a block computes raycast intersection, fires particle effects, and dispatches 3D block-break sound events with spatial listener attenuation.
- **Crafting & Smelting with EventBus Interception**: Fabric `AttackBlockCallback` and `UseBlockCallback` intercept container interactions, advancing furnace burn/cook ticks and checking recipe grids.
- **Dynamic GUI Rescaling**: Real-time switching between 1x, 2x, 3x, 4x integer GUI scales correctly recalculates container origins and slot hitboxes without coordinate drift.
- **Airborne Critical Hit Transition**: Player transitions from sneak to airborne jump, achieves downward velocity ($v_y < 0$), deals critical hit bonus ($+50\%$), and lands safely.
- **Custom Mod Block in Creative Inventory**: Custom block registered via Fabric `Registries.BLOCK` and `Registries.ITEM` appears in creative tab and can be placed into hotbar.

### Tier 4: Real-World Scenarios (`test_tier4_scenarios.py`)
Simulates authentic end-to-end player sessions and modding lifecycles:
- **Scenario 1: Full Survival Progression**: Chopping Oak Log $\to$ crafting 4 Planks in 2x2 grid $\to$ crafting Crafting Table & Sticks $\to$ placing table $\to$ crafting Wooden Pickaxe & Sword in 3x3 grid $\to$ verifying inventory slots and durability.
- **Scenario 2: Furnace Cooking & Smelting Lifecycle**: Placing Raw Pork and Planks into Furnace $\to$ advancing simulation ticks $\to$ animating burn flame and cook arrow $\to$ collecting Cooked Pork $\to$ consuming food to restore hunger and health.
- **Scenario 3: Everest Alpine Ascent & LOD Mesh Continuity**: Generating Everest terrain chunk column $\to$ ascending from $Y=63$ (sea level) to $Y > 400$ (summit) $\to$ validating altitudinal block stratification (grass $\to$ stone $\to$ snow) $\to$ generating LOD 1, 2, 3 meshes and verifying boundary skirts ensure watertight vertical continuity without cracks.
- **Scenario 4: World Save, Persistence & Reload Lifecycle**: Modifying voxel blocks and player inventory $\to$ saving world via `WorldManager` $\to$ re-instantiating engine and loading save $\to$ asserting 100% bitwise parity of block states, extended chunk palettes, and player coordinates.
- **Scenario 5: Fabric Mod Lifecycle & Event Interception**: Generating synthetic Fabric mod with `fabric.mod.json` $\to$ `ModLoader` discovery and initialization $\to$ registering custom block and event listeners $\to$ intercepting game tick and player attack $\to$ verifying cancellation and custom logic execution.

---

## 4. Test Execution & Usage

### Running via Pytest
```bash
# Run all E2E tests
.venv/bin/pytest tests/e2e/ -v

# Run a specific tier
.venv/bin/pytest tests/e2e/test_tier1_features.py -v
.venv/bin/pytest tests/e2e/test_tier2_boundaries.py -v
.venv/bin/pytest tests/e2e/test_tier3_interactions.py -v
.venv/bin/pytest tests/e2e/test_tier4_scenarios.py -v

# Run with keyword filter
.venv/bin/pytest tests/e2e/ -k "combat" -v
```

### Running via Standalone Runner
```bash
# Run all tiers with detailed summary
.venv/bin/python tests/e2e/runner.py

# Run a specific tier
.venv/bin/python tests/e2e/runner.py --tier 1
.venv/bin/python tests/e2e/runner.py --tier 2
.venv/bin/python tests/e2e/runner.py --tier 3
.venv/bin/python tests/e2e/runner.py --tier 4

# Run with verbose output
.venv/bin/python tests/e2e/runner.py --verbose
```

---

## 5. Milestone Integration & Quality Gates

| Milestone | Gate Criteria |
|---|---|
| **M1: Assets & Audio** | Features 1–7 pass in Tier 1; audio distance/pitch boundaries pass in Tier 2. |
| **M2: Fabric Architecture** | Features 8–12 pass in Tier 1; registry/mixin boundaries pass in Tier 2; Mod lifecycle passes in Tier 4. |
| **M3: Everest WorldGen & LODs** | Features 13–18 pass in Tier 1; Y=-64..512 limits pass in Tier 2; Alpine ascent passes in Tier 4. |
| **M4: 1.8 Combat & Physics** | Features 19–23 pass in Tier 1; 4% armor & sneak edge pass in Tier 2; Sneak combat passes in Tier 3. |
| **M5: Pixel-Perfect 1.8 UI** | Features 24–33 pass in Tier 1; container sizes & scaling pass in Tier 2; UI tooltips pass in Tier 3. |
| **M-FINAL: 100% E2E Pass** | 100% of tests in Tiers 1–4 pass unconditionally. Zero failures or uncaught errors. |
