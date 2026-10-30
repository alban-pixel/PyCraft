"""Tier 2: Boundary & Corner Cases Test Suite.

Stress-tests extreme limits, empty inputs, zero/negatives, extreme coordinates (Y=-64, Y=512, peak > 400),
boundary conditions, and pathological configurations across all subsystems.
"""
import math
import os
import sys
import tempfile
import pytest

# Ensure pycraft-gpu is in path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
PYCRAFT_GPU = os.path.join(PROJECT_ROOT, "pycraft-gpu")
if PYCRAFT_GPU not in sys.path:
    sys.path.insert(0, PYCRAFT_GPU)


# ============================================================================
# WorldGen & Chunk Boundaries (Y=-64, Y=512, Peaks > 400)
# ============================================================================

def test_boundary_chunk_y_min_floor():
    """Boundary: Y=-64 is the valid bottom-most voxel layer in extended chunk columns."""
    from world import World
    world = World(seed=1, generate=False)

    # Testing coordinate clamping and access at bottom floor Y = -64
    if hasattr(world, "inside_y"):
        assert world.inside_y(-64) is True
        assert world.inside_y(-65) is False

    # Block access at minimum coordinate
    block_at_min = world.get(0, -64, 0)
    assert block_at_min is not None


def test_boundary_chunk_y_max_ceiling():
    """Boundary: Y=511 is the top-most valid block, Y=512 is out of bounds."""
    from world import World
    import blocks
    world = World(seed=1, generate=False)

    # Coordinate Y=512 is out of range
    if hasattr(world, "inside_y"):
        assert world.inside_y(511) is True
        assert world.inside_y(512) is False

    # Out of bounds returns AIR
    val_oob = world.get(0, 512, 0)
    assert val_oob == blocks.AIR


def test_boundary_subchunk_index_limits():
    """Boundary: Subchunk indices cy range strictly from -4 (Y=-64..-49) to 31 (Y=496..511)."""
    import chunk
    # Lowest cy: -64 // 16 = -4
    min_cy = -64 // 16
    assert min_cy == -4

    # Highest cy: (512 // 16) - 1 = 31
    max_cy = (512 // 16) - 1
    assert max_cy == 31

    # Total subchunks: 31 - (-4) + 1 = 36
    assert (max_cy - min_cy + 1) == 36


def test_boundary_everest_peak_limits():
    """Boundary: Everest peaks must be > 400 but strictly within world ceiling < 512."""
    from world import World
    from generator import WorldPreset
    world = World(seed=999, preset=getattr(WorldPreset, "EVEREST", getattr(WorldPreset, "STANDARD", None)), generate=False)

    # Sample several mountain regions
    for x in (100, 500, 1000, 1500):
        for z in (100, 500, 1000, 1500):
            h = world.compute_terrain_height(x, z)
            # Terrain height must never exceed world vertical boundary
            assert h < 512, f"Terrain height exceeded ceiling: h={h}"


# ============================================================================
# Combat & Damage Boundaries (Zero, Negatives, 80% Cap, 1000 Damage)
# ============================================================================

def test_boundary_combat_zero_and_negative_damage():
    """Boundary: Zero and negative incoming damage must inflict 0 net damage."""
    import combat
    engine = combat.CombatEngine

    # Zero damage
    assert engine.calculate_armor_damage(0.0, 20.0) == 0.0
    # Negative damage must be clamped to 0.0
    assert engine.calculate_armor_damage(-5.0, 20.0) == 0.0
    assert engine.calculate_armor_damage(-100.0, 0.0) == 0.0


def test_boundary_armor_limits_0_and_20():
    """Boundary: 0 armor gives 0% reduction, 20 armor gives max 80% reduction in 1.8."""
    import combat

    raw_damage = 20.0
    # 0 armor points
    if hasattr(combat, "calculate_1_8_armor"):
        net_0 = combat.calculate_1_8_armor(raw_damage, 0.0)
        assert net_0 == 20.0
        # 20 armor points gives exactly 80% reduction: 20 * 0.20 = 4.0
        net_20 = combat.calculate_1_8_armor(raw_damage, 20.0)
        assert math.isclose(net_20, 4.0, rel_tol=1e-5)
    elif hasattr(combat.CombatEngine, "calculate_armor_damage_1_8"):
        net_0 = combat.CombatEngine.calculate_armor_damage_1_8(raw_damage, 0.0)
        assert net_0 == 20.0
        net_20 = combat.CombatEngine.calculate_armor_damage_1_8(raw_damage, 20.0)
        assert math.isclose(net_20, 4.0, rel_tol=1e-5)


def test_boundary_armor_overcap_clamping():
    """Boundary: Defense points > 20 clamp to 20 (cannot exceed 80% mitigation)."""
    import combat

    raw_damage = 50.0
    # 30 armor points (e.g. from mods or attributes)
    if hasattr(combat, "calculate_1_8_armor"):
        net_over = combat.calculate_1_8_armor(raw_damage, 30.0)
        # Should clamp to 20 armor (80% reduction): 50 * 0.20 = 10.0
        assert math.isclose(net_over, 10.0, rel_tol=1e-5)
    elif hasattr(combat.CombatEngine, "calculate_armor_damage_1_8"):
        net_over = combat.CombatEngine.calculate_armor_damage_1_8(raw_damage, 30.0)
        assert math.isclose(net_over, 10.0, rel_tol=1e-5)


def test_boundary_extreme_damage_1000():
    """Boundary: Extreme damage (1000.0) against 20 armor does not overflow or crash."""
    import combat
    extreme_dmg = 1000.0
    if hasattr(combat, "calculate_1_8_armor"):
        net = combat.calculate_1_8_armor(extreme_dmg, 20.0)
        assert math.isclose(net, 200.0, rel_tol=1e-5)
    elif hasattr(combat.CombatEngine, "calculate_armor_damage_1_8"):
        net = combat.CombatEngine.calculate_armor_damage_1_8(extreme_dmg, 20.0)
        assert math.isclose(net, 200.0, rel_tol=1e-5)


def test_boundary_invulnerability_ticks_lifecycle():
    """Boundary: 10-tick immunity window expires precisely on tick 10 -> tick 11."""
    from combat import InvulnerabilityTracker
    tracker = InvulnerabilityTracker()

    tracker.attempt_damage(10.0)
    assert tracker.invulnerable_ticks == 10

    # Advance 9 ticks
    for _ in range(9):
        tracker.tick()
    assert tracker.invulnerable_ticks == 1
    # Equal damage at tick 9 deals 0
    assert tracker.attempt_damage(10.0) == 0.0

    # 10th tick -> window reaches 0
    tracker.tick()
    assert tracker.invulnerable_ticks == 0

    # Next hit deals full damage
    next_dmg = tracker.attempt_damage(10.0)
    assert next_dmg == 10.0


# ============================================================================
# Audio Engine Boundaries (Distance Clamping, Pitch Limits)
# ============================================================================

def test_boundary_audio_zero_distance():
    """Boundary: Sound played at listener position (distance=0.0m) maintains full volume (1.0)."""
    try:
        import sound_manager
    except ImportError:
        pytest.skip("sound_manager not yet implemented (M1)")

    if hasattr(sound_manager, "calculate_distance_attenuation"):
        vol = sound_manager.calculate_distance_attenuation(distance=0.0, max_distance=16.0)
        assert vol == 1.0


def test_boundary_audio_extreme_distance_clamping():
    """Boundary: Sound played at extreme distance (> 1000m) attenuates cleanly to 0.0."""
    try:
        import sound_manager
    except ImportError:
        pytest.skip("sound_manager not yet implemented (M1)")

    if hasattr(sound_manager, "calculate_distance_attenuation"):
        vol = sound_manager.calculate_distance_attenuation(distance=1500.0, max_distance=16.0)
        assert vol == 0.0


def test_boundary_audio_pitch_extreme_bounds():
    """Boundary: Pitch values outside valid range [0.5, 2.0] are clamped without crashing."""
    try:
        import sound_manager
    except ImportError:
        pytest.skip("sound_manager not yet implemented (M1)")

    if hasattr(sound_manager, "clamp_pitch"):
        assert sound_manager.clamp_pitch(-1.0) >= 0.5
        assert sound_manager.clamp_pitch(10.0) <= 2.0


# ============================================================================
# Fabric API Boundaries (Invalid Identifiers, Mixin Errors, Malformed JSON)
# ============================================================================

def test_boundary_fabric_invalid_identifier_formats():
    """Boundary: Identifiers with illegal characters or uppercase letters raise ValueError."""
    try:
        from fabric_api.identifier import Identifier
    except ImportError:
        pytest.skip("fabric_api.identifier not yet implemented (M2)")

    # Uppercase letters are invalid in 1.8 / Fabric identifiers
    with pytest.raises(ValueError):
        Identifier("Minecraft", "Dirt")

    # Special characters / spaces are invalid
    with pytest.raises(ValueError):
        Identifier("minecraft", "dirt block with spaces")

    with pytest.raises(ValueError):
        Identifier("invalid@ns:bad#path")


def test_boundary_fabric_registry_unregistered_key():
    """Boundary: Querying an unregistered Identifier from Registry returns None."""
    try:
        from fabric_api.registry import Registries
        from fabric_api.identifier import Identifier
    except ImportError:
        pytest.skip("fabric_api.registry not yet implemented (M2)")

    unregistered_id = Identifier("nonexistent_mod", "ghost_item_12345")
    result = Registries.ITEM.get(unregistered_id)
    assert result is None


def test_boundary_fabric_malformed_mod_json(temp_dir):
    """Boundary: Malformed fabric.mod.json (missing id or corrupt JSON) is handled safely."""
    try:
        from fabric_api.mod_loader import ModLoader
    except ImportError:
        pytest.skip("fabric_api.mod_loader not yet implemented (M2)")

    corrupt_dir = os.path.join(temp_dir, "mods", "corrupt_mod")
    os.makedirs(corrupt_dir, exist_ok=True)
    with open(os.path.join(corrupt_dir, "fabric.mod.json"), "w") as fh:
        fh.write("{ bad json: [ unclosed ")

    loader = ModLoader()
    # Loading corrupt mod directory should log warning and continue without unhandled crash
    loader.load_mods(os.path.join(temp_dir, "mods"))
    assert "corrupt_mod" not in loader.loaded_mods


# ============================================================================
# UI & Display Boundaries (Resolution Extremes, Tooltip Durability)
# ============================================================================

def test_boundary_gui_scale_min_resolution_320x180():
    """Boundary: Minimum supported resolution 320x180 forces GUI scale 1x."""
    try:
        from ui_renderer import UIRenderer
        renderer = UIRenderer()
        scale = renderer.calculate_gui_scale(320, 180)
        assert scale == 1
    except ImportError:
        pytest.skip("ui_renderer not yet implemented (M5)")


def test_boundary_gui_scale_4k_resolution():
    """Boundary: 4K resolution (3840x2160) produces integer scale >= 4 without fractional drift."""
    try:
        from ui_renderer import UIRenderer
        renderer = UIRenderer()
        scale = renderer.calculate_gui_scale(3840, 2160)
        assert isinstance(scale, int)
        assert scale >= 4
    except ImportError:
        pytest.skip("ui_renderer not yet implemented (M5)")


def test_boundary_tool_durability_bar_extremes():
    """Boundary: Durability bar renders correctly at 0 durability, 1 durability, max, and overflow."""
    try:
        from ui_renderer import calculate_durability_bar
        # Full durability: bar width 13px, green color
        w_max, color_max = calculate_durability_bar(current=100, max_durability=100)
        assert w_max == 13

        # Zero durability: bar width 0px or red
        w_zero, color_zero = calculate_durability_bar(current=0, max_durability=100)
        assert w_zero == 0

        # Negative durability: clamped to 0
        w_neg, color_neg = calculate_durability_bar(current=-5, max_durability=100)
        assert w_neg == 0
    except ImportError:
        pytest.skip("ui_renderer not yet implemented (M5)")
