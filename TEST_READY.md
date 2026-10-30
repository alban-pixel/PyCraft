# TEST_READY: PyCraft Vanilla 1.8 Parity & Fabric Architecture E2E Test Suite

## Status: READY FOR MILESTONE VERIFICATION

The complete 4-Tier End-to-End (E2E) Test Suite for PyCraft has been designed, implemented, and verified. It is now published and active as the authoritative opaque-box testing harness across all implementation milestones (M1–M5) through final acceptance (M-FINAL).

---

## 1. Quick Start / Test Runner Commands

### Standard Pytest Invocations
```bash
# Execute entire E2E test suite (Tiers 1 - 4)
.venv/bin/pytest tests/e2e/ -v

# Execute specific tier test file
.venv/bin/pytest tests/e2e/test_tier1_features.py -v     # Tier 1: Feature Coverage
.venv/bin/pytest tests/e2e/test_tier2_boundaries.py -v   # Tier 2: Boundaries & Extremes
.venv/bin/pytest tests/e2e/test_tier3_interactions.py -v # Tier 3: Cross-Feature Interactions
.venv/bin/pytest tests/e2e/test_tier4_scenarios.py -v    # Tier 4: Real-World Scenarios
```

### Standalone E2E Runner Invocations
```bash
# Run all tiers via custom runner
.venv/bin/python tests/e2e/runner.py

# Run individual tiers with targeted summary
.venv/bin/python tests/e2e/runner.py --tier 1
.venv/bin/python tests/e2e/runner.py --tier 2
.venv/bin/python tests/e2e/runner.py --tier 3
.venv/bin/python tests/e2e/runner.py --tier 4
```

---

## 2. Test Suite Structure & Inventory

| Tier | Test File | Test Count | Description |
|---|---|---|---|
| **Tier 1** | `tests/e2e/test_tier1_features.py` | 33 | Nominal verification for all 33 inventoried features (#1 to #33) across M1–M5 |
| **Tier 2** | `tests/e2e/test_tier2_boundaries.py` | 18 | Boundary limits, extreme coordinates (Y=-64, Y=512, peak > 400), zero/negatives, 80% armor cap |
| **Tier 3** | `tests/e2e/test_tier3_interactions.py` | 7 | Cross-feature pairwise interactions: sneak combat, 3D mining audio, container tooltips, GUI rescaling |
| **Tier 4** | `tests/e2e/test_tier4_scenarios.py` | 5 | End-to-end workflows: survival progression, furnace smelting & eating, Everest ascent & LODs, world save/reload, Fabric mod lifecycle |
| **Total** | **All 4 Tiers** | **63 tests** | Comprehensive opaque-box coverage of all system requirements |

---

## 3. Baseline Execution Status (Pre-Implementation Baseline)

Running `.venv/bin/pytest tests/e2e/` against the current codebase produces the expected pre-implementation diagnostic baseline:
- **Passed**: 35 tests (validating existing survival mechanics, 2x2/3x3 crafting, furnace state progression, sneak edge physics, world persistence, 10-tick immunity, and LOD geometry).
- **Skipped**: 13 tests (waiting on pending module interfaces in M1, M2, and M5).
- **Pending Implementation Failures**: 15 tests (cleanly asserting requirements from planned milestones M1–M5):
  * **Milestone M1**: Features 4, 5, 6, 7 awaiting `sound_manager.py` (Sound event registry, 3D audio, pitch variation, multi-backend).
  * **Milestone M2**: Features 8, 9, 10, 11, 12 awaiting `fabric_api/` (Identifier, Registries, EventBus, Mixin system, ModLoader).
  * **Milestone M3**: Features 13, 15, 16, 17 awaiting extended chunk height $Y \in [-64, 512)$, peaks $> Y=400$, altitudinal stratification, and `lod.UV_INSET = 0.05 / 16`.
  * **Milestone M4**: Feature 21 awaiting 1.8 flat 4% armor mitigation formula.
  * **Milestone M5**: Feature 24 awaiting `ui_renderer.py` integer GUI scaling.

---

## 4. Milestone Acceptance Gating

Each milestone worker must ensure their respective tests transition from pending/skipped to **PASSED**:

1. **M1 (Asset & Audio Engine)**:
   - Must pass `test_tier1_features.py::test_feature_04` through `07`
   - Must pass `test_tier2_boundaries.py::test_boundary_audio_*`
   - Must pass `test_tier3_interactions.py::test_interaction_3d_audio_during_block_mining`
2. **M2 (Fabric Mod Architecture)**:
   - Must pass `test_tier1_features.py::test_feature_08` through `12`
   - Must pass `test_tier2_boundaries.py::test_boundary_fabric_*`
   - Must pass `test_tier3_interactions.py::test_interaction_fabric_*`
   - Must pass `test_tier4_scenarios.py::test_scenario_05_fabric_mod_lifecycle_and_interception`
3. **M3 (Everest WorldGen & Watertight LODs)**:
   - Must pass `test_tier1_features.py::test_feature_13` through `18`
   - Must pass `test_tier2_boundaries.py::test_boundary_chunk_*` and `test_boundary_everest_*`
   - Must pass `test_tier4_scenarios.py::test_scenario_03_everest_alpine_ascent_and_watertight_lods`
4. **M4 (1.8 Combat & Physics)**:
   - Must pass `test_tier1_features.py::test_feature_19` through `23`
   - Must pass `test_tier2_boundaries.py::test_boundary_combat_*` and `test_boundary_armor_*`
   - Must pass `test_tier3_interactions.py::test_interaction_combat_while_sneaking_on_ledge` and `test_interaction_airborne_descent_to_critical_hit_transition`
5. **M5 (Pixel-Perfect 1.8 UI)**:
   - Must pass `test_tier1_features.py::test_feature_24` through `33`
   - Must pass `test_tier2_boundaries.py::test_boundary_gui_scale_*` and `test_boundary_tool_durability_*`
   - Must pass `test_tier3_interactions.py::test_interaction_ui_tooltip_*` and `test_interaction_gui_scale_change_*`
6. **M-FINAL (Full 100% E2E Pass)**:
   - All 63 E2E tests across Tiers 1–4 must pass with **100% success rate, 0 failures, 0 skipped**.
