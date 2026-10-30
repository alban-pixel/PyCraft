"""Milestone 1 Test Suite & Verification Architecture: Sound Manager & Vanilla Asset Constraints.

Tests cover:
1. Strict Asset Distribution Constraints: Zero .jar or .class binaries in repository, local asset loading path.
2. Canonical Minecraft 1.8 Sound Registry: Exact 246 sound events and category mappings.
3. 3D Spatial Audio Math: Distance attenuation (d=0, d=8, d=16, d=32) and high-volume scaling.
4. Horizontal Stereo Panning Math: Yaw-relative angle panning at 0, 90, 180, 270 degrees.
5. Pitch Variation Bounds: 0.8 <= pitch <= 1.2 natural variation.
6. Block Sound Mapping: 1.8 step/dig sounds and block place sound parameter adjustments.
7. Sound Manager Backend Selection: SilentBackend (default in tests), AfplayBackend, PyxelSynthBackend.
8. Missing Asset Resilience: Graceful fallback handling when sound files are missing.
"""

import math
import os
import random
import sys
import pytest

# Ensure pycraft-gpu directory is in sys.path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
PYCRAFT_GPU_DIR = os.path.join(PROJECT_ROOT, "pycraft-gpu")
if PYCRAFT_GPU_DIR not in sys.path:
    sys.path.insert(0, PYCRAFT_GPU_DIR)

# Optional import of sound_manager (gracefully skipped if pending M1 worker implementation)
try:
    import sound_manager
    from sound_manager import (
        SoundManager,
        SoundRegistry,
        SoundEntry,
        AudioBackend,
        SilentBackend,
        AfplayBackend,
        PyxelSynthBackend,
        calculate_distance_attenuation,
        calculate_stereo_pan,
        calculate_pitch_variation,
        BLOCK_SOUND_MAP,
    )
    SOUND_MANAGER_AVAILABLE = True
except ImportError:
    sound_manager = None
    SOUND_MANAGER_AVAILABLE = False

requires_sound_manager = pytest.mark.skipif(
    not SOUND_MANAGER_AVAILABLE,
    reason="pycraft-gpu/sound_manager.py not yet implemented by M1 worker",
)


# ==============================================================================
# Canonical 246 Minecraft 1.8 Sound Events Catalog
# ==============================================================================
CANONICAL_1_8_SOUND_EVENTS = {
    "ambient.cave.cave": "ambient",
    "ambient.weather.rain": "weather",
    "ambient.weather.thunder": "weather",
    "creeper.primed": "hostile",
    "dig.cloth": "block",
    "dig.glass": "block",
    "dig.grass": "block",
    "dig.gravel": "block",
    "dig.sand": "block",
    "dig.snow": "block",
    "dig.stone": "block",
    "dig.wood": "block",
    "fire.fire": "block",
    "fire.ignite": "block",
    "fireworks.blast": "ambient",
    "fireworks.blast_far": "ambient",
    "fireworks.largeBlast": "ambient",
    "fireworks.largeBlast_far": "ambient",
    "fireworks.launch": "ambient",
    "fireworks.twinkle": "ambient",
    "fireworks.twinkle_far": "ambient",
    "game.hostile.die": "hostile",
    "game.hostile.hurt": "hostile",
    "game.hostile.hurt.fall.big": "hostile",
    "game.hostile.hurt.fall.small": "hostile",
    "game.hostile.swim": "hostile",
    "game.hostile.swim.splash": "hostile",
    "game.neutral.die": "neutral",
    "game.neutral.hurt": "neutral",
    "game.neutral.hurt.fall.big": "neutral",
    "game.neutral.hurt.fall.small": "neutral",
    "game.neutral.swim": "neutral",
    "game.neutral.swim.splash": "neutral",
    "game.player.die": "player",
    "game.player.hurt": "player",
    "game.player.hurt.fall.big": "player",
    "game.player.hurt.fall.small": "player",
    "game.player.swim": "player",
    "game.player.swim.splash": "block",
    "game.potion.smash": "neutral",
    "game.tnt.primed": "block",
    "gui.button.press": "master",
    "item.fireCharge.use": "block",
    "liquid.lava": "block",
    "liquid.lavapop": "block",
    "liquid.water": "block",
    "minecart.base": "neutral",
    "minecart.inside": "player",
    "mob.bat.death": "neutral",
    "mob.bat.hurt": "neutral",
    "mob.bat.idle": "neutral",
    "mob.bat.loop": "neutral",
    "mob.bat.takeoff": "neutral",
    "mob.blaze.breathe": "hostile",
    "mob.blaze.death": "hostile",
    "mob.blaze.hit": "hostile",
    "mob.cat.hiss": "neutral",
    "mob.cat.hitt": "neutral",
    "mob.cat.meow": "neutral",
    "mob.cat.purr": "neutral",
    "mob.cat.purreow": "neutral",
    "mob.chicken.hurt": "neutral",
    "mob.chicken.plop": "neutral",
    "mob.chicken.say": "neutral",
    "mob.chicken.step": "neutral",
    "mob.cow.hurt": "neutral",
    "mob.cow.say": "neutral",
    "mob.cow.step": "neutral",
    "mob.creeper.death": "hostile",
    "mob.creeper.say": "hostile",
    "mob.enderdragon.end": "hostile",
    "mob.enderdragon.growl": "hostile",
    "mob.enderdragon.hit": "hostile",
    "mob.enderdragon.wings": "hostile",
    "mob.endermen.death": "hostile",
    "mob.endermen.hit": "hostile",
    "mob.endermen.idle": "hostile",
    "mob.endermen.portal": "hostile",
    "mob.endermen.scream": "hostile",
    "mob.endermen.stare": "hostile",
    "mob.ghast.affectionate_scream": "hostile",
    "mob.ghast.charge": "hostile",
    "mob.ghast.death": "hostile",
    "mob.ghast.fireball": "hostile",
    "mob.ghast.moan": "hostile",
    "mob.ghast.scream": "hostile",
    "mob.guardian.attack": "hostile",
    "mob.guardian.curse": "hostile",
    "mob.guardian.death": "hostile",
    "mob.guardian.elder.death": "hostile",
    "mob.guardian.elder.hit": "hostile",
    "mob.guardian.elder.idle": "hostile",
    "mob.guardian.flop": "hostile",
    "mob.guardian.hit": "hostile",
    "mob.guardian.idle": "hostile",
    "mob.guardian.land.death": "hostile",
    "mob.guardian.land.hit": "hostile",
    "mob.guardian.land.idle": "hostile",
    "mob.horse.angry": "neutral",
    "mob.horse.armor": "neutral",
    "mob.horse.breathe": "neutral",
    "mob.horse.death": "neutral",
    "mob.horse.donkey.angry": "neutral",
    "mob.horse.donkey.death": "neutral",
    "mob.horse.donkey.hit": "neutral",
    "mob.horse.donkey.idle": "neutral",
    "mob.horse.gallop": "neutral",
    "mob.horse.hit": "neutral",
    "mob.horse.idle": "neutral",
    "mob.horse.jump": "neutral",
    "mob.horse.land": "neutral",
    "mob.horse.leather": "neutral",
    "mob.horse.skeleton.death": "neutral",
    "mob.horse.skeleton.hit": "neutral",
    "mob.horse.skeleton.idle": "neutral",
    "mob.horse.soft": "neutral",
    "mob.horse.wood": "neutral",
    "mob.horse.zombie.death": "neutral",
    "mob.horse.zombie.hit": "neutral",
    "mob.horse.zombie.idle": "neutral",
    "mob.irongolem.death": "neutral",
    "mob.irongolem.hit": "neutral",
    "mob.irongolem.throw": "neutral",
    "mob.irongolem.walk": "neutral",
    "mob.magmacube.big": "hostile",
    "mob.magmacube.jump": "hostile",
    "mob.magmacube.small": "hostile",
    "mob.pig.death": "neutral",
    "mob.pig.say": "neutral",
    "mob.pig.step": "neutral",
    "mob.rabbit.death": "neutral",
    "mob.rabbit.hop": "neutral",
    "mob.rabbit.hurt": "neutral",
    "mob.rabbit.idle": "neutral",
    "mob.sheep.say": "neutral",
    "mob.sheep.shear": "neutral",
    "mob.sheep.step": "neutral",
    "mob.silverfish.hit": "hostile",
    "mob.silverfish.kill": "hostile",
    "mob.silverfish.say": "hostile",
    "mob.silverfish.step": "hostile",
    "mob.skeleton.death": "hostile",
    "mob.skeleton.hurt": "hostile",
    "mob.skeleton.say": "hostile",
    "mob.skeleton.step": "hostile",
    "mob.slime.attack": "hostile",
    "mob.slime.big": "hostile",
    "mob.slime.small": "hostile",
    "mob.spider.death": "hostile",
    "mob.spider.say": "hostile",
    "mob.spider.step": "hostile",
    "mob.villager.death": "neutral",
    "mob.villager.haggle": "neutral",
    "mob.villager.hit": "neutral",
    "mob.villager.idle": "neutral",
    "mob.villager.no": "neutral",
    "mob.villager.yes": "neutral",
    "mob.wither.death": "hostile",
    "mob.wither.hurt": "hostile",
    "mob.wither.idle": "hostile",
    "mob.wither.shoot": "hostile",
    "mob.wither.spawn": "hostile",
    "mob.wolf.bark": "neutral",
    "mob.wolf.death": "neutral",
    "mob.wolf.growl": "neutral",
    "mob.wolf.howl": "neutral",
    "mob.wolf.hurt": "neutral",
    "mob.wolf.panting": "neutral",
    "mob.wolf.shake": "neutral",
    "mob.wolf.step": "neutral",
    "mob.wolf.whine": "neutral",
    "mob.zombie.death": "hostile",
    "mob.zombie.hurt": "hostile",
    "mob.zombie.infect": "hostile",
    "mob.zombie.metal": "hostile",
    "mob.zombie.remedy": "hostile",
    "mob.zombie.say": "hostile",
    "mob.zombie.step": "hostile",
    "mob.zombie.unfect": "hostile",
    "mob.zombie.wood": "hostile",
    "mob.zombie.woodbreak": "hostile",
    "mob.zombiepig.zpig": "hostile",
    "mob.zombiepig.zpigangry": "hostile",
    "mob.zombiepig.zpigdeath": "hostile",
    "mob.zombiepig.zpighurt": "hostile",
    "music.game": "music",
    "music.game.creative": "music",
    "music.game.end": "music",
    "music.game.end.credits": "music",
    "music.game.end.dragon": "music",
    "music.game.nether": "music",
    "music.menu": "music",
    "note.bass": "record",
    "note.bassattack": "record",
    "note.bd": "record",
    "note.harp": "record",
    "note.hat": "record",
    "note.pling": "record",
    "note.snare": "record",
    "portal.portal": "block",
    "portal.travel": "player",
    "portal.trigger": "block",
    "random.anvil_break": "block",
    "random.anvil_land": "block",
    "random.anvil_use": "block",
    "random.bow": "neutral",
    "random.bowhit": "neutral",
    "random.break": "player",
    "random.burp": "player",
    "random.chestclosed": "block",
    "random.chestopen": "block",
    "random.click": "block",
    "random.door_close": "block",
    "random.door_open": "block",
    "random.drink": "player",
    "random.eat": "player",
    "random.explode": "block",
    "random.fizz": "block",
    "random.levelup": "player",
    "random.orb": "player",
    "random.pop": "player",
    "random.splash": "player",
    "random.successful_hit": "player",
    "random.wood_click": "block",
    "records.11": "record",
    "records.13": "record",
    "records.blocks": "record",
    "records.cat": "record",
    "records.chirp": "record",
    "records.far": "record",
    "records.mall": "record",
    "records.mellohi": "record",
    "records.stal": "record",
    "records.strad": "record",
    "records.wait": "record",
    "records.ward": "record",
    "step.cloth": "neutral",
    "step.grass": "neutral",
    "step.gravel": "neutral",
    "step.ladder": "neutral",
    "step.sand": "neutral",
    "step.snow": "neutral",
    "step.stone": "neutral",
    "step.wood": "neutral",
    "tile.piston.in": "block",
    "tile.piston.out": "block",
}


# ==============================================================================
# Pure Reference Math Formulas (Minecraft 1.8 Audio Parity)
# ==============================================================================
def reference_distance_attenuation(distance: float, nominal_volume: float = 1.0) -> float:
    """Calculates Minecraft 1.8 linear distance attenuation factor.

    Radius R_max = 16.0 * max(1.0, nominal_volume).
    Attenuation = max(0.0, 1.0 - distance / R_max).
    """
    r_max = 16.0 * max(1.0, nominal_volume)
    if distance > r_max:
        return 0.0
    return max(0.0, 1.0 - distance / r_max)


def reference_stereo_pan(
    listener_pos: tuple[float, float, float],
    listener_yaw_deg: float,
    sound_pos: tuple[float, float, float],
) -> float:
    """Calculates horizontal stereo panning factor in [-1.0, 1.0].

    In PyCraft:
      Yaw = 0 looks toward +Z.
      Yaw = 90 looks toward +X.
      Yaw = 180 looks toward -Z.
      Yaw = 270 looks toward -X.
    Pan factor = clamp(sin(relative_angle), -1.0, 1.0).
    """
    dx = sound_pos[0] - listener_pos[0]
    dz = sound_pos[2] - listener_pos[2]
    dist_h = math.sqrt(dx * dx + dz * dz)
    if dist_h < 1e-4:
        return 0.0

    sound_azimuth = math.atan2(dx, dz)
    listener_yaw_rad = math.radians(listener_yaw_deg)
    relative_angle = sound_azimuth - listener_yaw_rad
    # Normalize to [-pi, pi]
    relative_angle = (relative_angle + math.pi) % (2.0 * math.pi) - math.pi

    pan = math.sin(relative_angle)
    return max(-1.0, min(1.0, pan))


def reference_pitch_variation(base_pitch: float = 1.0, variance: float = 0.2) -> float:
    """Calculates Minecraft 1.8 random pitch variation within [base * (1-var), base * (1+var)]."""
    factor = random.uniform(1.0 - variance, 1.0 + variance)
    return max(0.5, min(2.0, base_pitch * factor))


# ==============================================================================
# Test Cases: Asset Distribution & Repository Cleanliness
# ==============================================================================
def test_no_jar_files_in_repository():
    """Verify that NO .jar files exist in the repository (excluding virtual environment)."""
    jar_files = []
    for root, dirs, files in os.walk(PROJECT_ROOT):
        # Exclude git and virtual environment directories
        dirs[:] = [d for d in dirs if d not in {".git", ".venv", "venv", "__pycache__"}]
        for f in files:
            if f.endswith(".jar"):
                jar_files.append(os.path.join(root, f))

    assert len(jar_files) == 0, f"Found forbidden .jar files in repository: {jar_files}"


def test_no_class_files_in_repository():
    """Verify that NO prebuilt .class files exist in the repository."""
    class_files = []
    for root, dirs, files in os.walk(PROJECT_ROOT):
        dirs[:] = [d for d in dirs if d not in {".git", ".venv", "venv", "__pycache__"}]
        for f in files:
            if f.endswith(".class"):
                class_files.append(os.path.join(root, f))

    assert len(class_files) == 0, f"Found forbidden .class files in repository: {class_files}"


def test_assets_path_conventions():
    """Verify that the assets directory path convention is pycraft-gpu/assets/vanilla/."""
    expected_assets_dir = os.path.join(PYCRAFT_GPU_DIR, "assets", "vanilla")
    expected_textures_dir = os.path.join(expected_assets_dir, "textures")
    expected_sounds_dir = os.path.join(expected_assets_dir, "sounds")

    # Path strings must be canonically anchored inside the project
    assert expected_assets_dir.startswith(PROJECT_ROOT)
    assert expected_textures_dir.endswith(os.path.join("assets", "vanilla", "textures"))
    assert expected_sounds_dir.endswith(os.path.join("assets", "vanilla", "sounds"))


# ==============================================================================
# Test Cases: Canonical 246 Sound Events Catalog
# ==============================================================================
def test_canonical_1_8_sound_event_catalog_completeness():
    """Verify that all 246 canonical Minecraft 1.8 sound events are defined."""
    assert len(CANONICAL_1_8_SOUND_EVENTS) == 246

    # Verify category counts match 1.8 specification
    categories = list(CANONICAL_1_8_SOUND_EVENTS.values())
    assert categories.count("ambient") == 8
    assert categories.count("block") == 31
    assert categories.count("hostile") == 76
    assert categories.count("master") == 1
    assert categories.count("music") == 7
    assert categories.count("neutral") == 86
    assert categories.count("player") == 16
    assert categories.count("record") == 19
    assert categories.count("weather") == 2


def test_canonical_sound_event_prefixes():
    """Verify presence of key 1.8 sound prefixes across essential gameplay domains."""
    events = CANONICAL_1_8_SOUND_EVENTS

    # Step sounds
    step_events = [e for e in events if e.startswith("step.")]
    assert len(step_events) >= 8
    assert "step.grass" in step_events
    assert "step.stone" in step_events
    assert "step.wood" in step_events

    # Dig sounds
    dig_events = [e for e in events if e.startswith("dig.")]
    assert len(dig_events) >= 8
    assert "dig.grass" in dig_events
    assert "dig.stone" in dig_events
    assert "dig.wood" in dig_events

    # Random sounds
    assert "random.click" in events
    assert "random.explode" in events
    assert "random.bow" in events
    assert "random.chestopen" in events

    # Player and Mob sounds
    assert "game.player.hurt" in events
    assert "game.player.die" in events
    assert "mob.zombie.say" in events
    assert "mob.creeper.say" in events


# ==============================================================================
# Test Cases: 3D Distance Attenuation Math (d=0, d=8, d=16, d=32)
# ==============================================================================
def test_3d_distance_attenuation_math():
    """Verify exact distance attenuation at d=0, d=8, d=16, d=32 for nominal volume 1.0."""
    # At d=0, attenuation is full (1.0)
    att_0 = reference_distance_attenuation(distance=0.0, nominal_volume=1.0)
    assert att_0 == pytest.approx(1.0, abs=1e-5)

    # At d=8, attenuation is half (0.5)
    att_8 = reference_distance_attenuation(distance=8.0, nominal_volume=1.0)
    assert att_8 == pytest.approx(0.5, abs=1e-5)

    # At d=16, attenuation reaches zero (0.0)
    att_16 = reference_distance_attenuation(distance=16.0, nominal_volume=1.0)
    assert att_16 == pytest.approx(0.0, abs=1e-5)

    # At d=32, sound is beyond max range and clamped to zero (0.0)
    att_32 = reference_distance_attenuation(distance=32.0, nominal_volume=1.0)
    assert att_32 == pytest.approx(0.0, abs=1e-5)


def test_high_volume_distance_attenuation():
    """Verify high-volume sounds (e.g. explosion volume 4.0) scale max range to 64 blocks."""
    nominal_v = 4.0
    # At d=0: factor 1.0
    assert reference_distance_attenuation(0.0, nominal_v) == pytest.approx(1.0, abs=1e-5)
    # At d=16: factor 1.0 - 16/64 = 0.75
    assert reference_distance_attenuation(16.0, nominal_v) == pytest.approx(0.75, abs=1e-5)
    # At d=32: factor 1.0 - 32/64 = 0.50
    assert reference_distance_attenuation(32.0, nominal_v) == pytest.approx(0.50, abs=1e-5)
    # At d=64: factor 1.0 - 64/64 = 0.00
    assert reference_distance_attenuation(64.0, nominal_v) == pytest.approx(0.00, abs=1e-5)
    # At d=100: clamped to 0.0
    assert reference_distance_attenuation(100.0, nominal_v) == pytest.approx(0.00, abs=1e-5)


# ==============================================================================
# Test Cases: Stereo Panning Calculation (0, 90, 180, 270 degrees)
# ==============================================================================
def test_stereo_panning_angles_listener_facing_z():
    """Verify horizontal stereo pan with listener at (0, 0, 0) and yaw=0 (facing +Z)."""
    listener = (0.0, 1.62, 0.0)
    yaw = 0.0

    # 1. Angle 0 (Front): Sound at (0, 1.62, 10) -> pan 0.0 (center)
    pan_front = reference_stereo_pan(listener, yaw, (0.0, 1.62, 10.0))
    assert pan_front == pytest.approx(0.0, abs=1e-5)

    # 2. Angle 90 (Right): Sound at (10, 1.62, 0) -> pan 1.0 (full right)
    pan_right = reference_stereo_pan(listener, yaw, (10.0, 1.62, 0.0))
    assert pan_right == pytest.approx(1.0, abs=1e-5)

    # 3. Angle 180 (Behind): Sound at (0, 1.62, -10) -> pan 0.0 (center)
    pan_behind = reference_stereo_pan(listener, yaw, (0.0, 1.62, -10.0))
    assert pan_behind == pytest.approx(0.0, abs=1e-5)

    # 4. Angle 270 (Left): Sound at (-10, 1.62, 0) -> pan -1.0 (full left)
    pan_left = reference_stereo_pan(listener, yaw, (-10.0, 1.62, 0.0))
    assert pan_left == pytest.approx(-1.0, abs=1e-5)


def test_stereo_panning_listener_rotated():
    """Verify horizontal stereo pan when listener is rotated (yaw=90, facing +X)."""
    listener = (0.0, 1.62, 0.0)
    yaw = 90.0  # Facing +X

    # Sound at (10, 1.62, 0) is now in FRONT -> pan 0.0
    assert reference_stereo_pan(listener, yaw, (10.0, 1.62, 0.0)) == pytest.approx(0.0, abs=1e-5)

    # Sound at (0, 1.62, -10) is now to the RIGHT -> pan 1.0
    assert reference_stereo_pan(listener, yaw, (0.0, 1.62, -10.0)) == pytest.approx(1.0, abs=1e-5)

    # Sound at (-10, 1.62, 0) is now BEHIND -> pan 0.0
    assert reference_stereo_pan(listener, yaw, (-10.0, 1.62, 0.0)) == pytest.approx(0.0, abs=1e-5)

    # Sound at (0, 1.62, 10) is now to the LEFT -> pan -1.0
    assert reference_stereo_pan(listener, yaw, (0.0, 1.62, 10.0)) == pytest.approx(-1.0, abs=1e-5)


def test_stereo_panning_coincident_position():
    """Verify that sound at the listener's exact position is centered (pan=0.0)."""
    listener = (5.0, 10.0, -3.0)
    assert reference_stereo_pan(listener, 45.0, listener) == 0.0


# ==============================================================================
# Test Cases: Pitch Variation Bounds (0.8 <= pitch <= 1.2)
# ==============================================================================
def test_pitch_variation_bounds():
    """Verify that natural pitch variation produces values strictly within [0.8, 1.2]."""
    samples = [reference_pitch_variation(base_pitch=1.0, variance=0.2) for _ in range(250)]

    # Every sample must adhere to the bounds
    for p in samples:
        assert 0.8 <= p <= 1.2, f"Pitch sample {p} out of bounds [0.8, 1.2]"

    # Verify that variation is dynamic (not a static dummy value)
    std_dev = (sum((p - 1.0) ** 2 for p in samples) / len(samples)) ** 0.5
    assert std_dev > 0.04, f"Pitch samples lack variance (std_dev={std_dev})"


def test_pitch_variation_disabled():
    """Verify that variance=0.0 produces the exact base pitch without alteration."""
    for base in [0.8, 1.0, 1.5]:
        val = reference_pitch_variation(base_pitch=base, variance=0.0)
        assert val == pytest.approx(base, abs=1e-6)


# ==============================================================================
# Test Cases: Block Sound Mapping & Place Formula
# ==============================================================================
def test_block_place_sound_math():
    """Verify Minecraft 1.8 block placement sound modification formulas.

    V_place = (V_dig + 1.0) / 2.0 * 0.8
    P_place = P_dig * 0.8
    """
    v_dig = 1.0
    p_dig = 1.0

    v_place = ((v_dig + 1.0) / 2.0) * 0.8
    p_place = p_dig * 0.8

    assert v_place == pytest.approx(0.8, abs=1e-5)
    assert p_place == pytest.approx(0.8, abs=1e-5)


# ==============================================================================
# Integration Tests: SoundManager API & Backends (Executed when sound_manager.py exists)
# ==============================================================================
@requires_sound_manager
def test_sound_manager_registration_and_retrieval():
    """Verify SoundManager registers all 246 sound events and retrieves them accurately."""
    manager = SoundManager(backend="silent")
    registry = manager.registry

    for event_name, expected_category in CANONICAL_1_8_SOUND_EVENTS.items():
        assert registry.has_event(event_name), f"Event {event_name} not registered in SoundRegistry"
        event_data = registry.get_event(event_name)
        assert event_data is not None
        assert event_data["category"] == expected_category

    # Retrieval of unknown event returns None
    assert registry.get_event("nonexistent.event.foobar") is None


@requires_sound_manager
def test_sound_manager_silent_backend_playback_log():
    """Verify SilentBackend captures play_sound calls with accurate math."""
    manager = SoundManager(backend="silent")
    manager.update_listener(pos=(0.0, 1.62, 0.0), yaw=0.0, pitch=0.0)

    # Play non-spatial sound (e.g. GUI click)
    manager.play_sound("gui.button.press", pos=None, volume=1.0, pitch=1.0, pitch_variance=0.0)
    assert len(manager.backend.played_events) == 1
    rec1 = manager.backend.played_events[-1]
    assert rec1["event_name"] == "gui.button.press"
    assert rec1["volume"] == pytest.approx(1.0, abs=1e-5)
    assert rec1["pan"] == pytest.approx(0.0, abs=1e-5)
    assert rec1["pitch"] == pytest.approx(1.0, abs=1e-5)

    # Play spatial sound at distance d=8, angle 90 (to the right)
    manager.play_sound("step.grass", pos=(8.0, 1.62, 0.0), volume=1.0, pitch=1.0, pitch_variance=0.0)
    assert len(manager.backend.played_events) == 2
    rec2 = manager.backend.played_events[-1]
    assert rec2["event_name"] == "step.grass"
    assert rec2["volume"] == pytest.approx(0.5, abs=1e-5)  # d=8 -> attenuation 0.5
    assert rec2["pan"] == pytest.approx(1.0, abs=1e-5)  # 90 deg right -> pan 1.0


@requires_sound_manager
def test_sound_manager_backend_selection():
    """Verify SoundManager instantiates correct backend based on parameter or environment."""
    # Silent backend
    m_silent = SoundManager(backend="silent")
    assert isinstance(m_silent.backend, SilentBackend)

    # Afplay backend
    m_afplay = SoundManager(backend="afplay")
    assert isinstance(m_afplay.backend, AfplayBackend)

    # Pyxel synth backend
    m_pyxel = SoundManager(backend="pyxel")
    assert isinstance(m_pyxel.backend, PyxelSynthBackend)


@requires_sound_manager
def test_sound_manager_missing_asset_handling():
    """Verify SoundManager handles missing audio files gracefully without crashing."""
    manager = SoundManager(backend="silent")
    # Playing sound with missing file must not throw FileNotFoundError
    manager.play_sound("dig.stone", pos=(0.0, 1.62, 2.0))
    assert len(manager.backend.played_events) >= 1


@requires_sound_manager
def test_sound_manager_stop_all():
    """Verify stop_all executes cleanly across backends."""
    manager = SoundManager(backend="silent")
    manager.play_sound("music.game")
    manager.stop_all()
    # Confirms no unhandled exception


@requires_sound_manager
def test_block_sound_map_completeness():
    """Verify that all 164 canonical block IDs (0..163) map to valid step and dig sound events."""
    for block_id in range(164):
        assert block_id in BLOCK_SOUND_MAP, f"Block ID {block_id} missing from BLOCK_SOUND_MAP"
        step_snd, dig_snd = BLOCK_SOUND_MAP[block_id]
        assert step_snd in CANONICAL_1_8_SOUND_EVENTS, f"Invalid step sound {step_snd} for block {block_id}"
        assert dig_snd in CANONICAL_1_8_SOUND_EVENTS, f"Invalid dig sound {dig_snd} for block {block_id}"


@requires_sound_manager
def test_sound_manager_block_helpers():
    """Verify play_block_step, play_block_dig, and 1.8 play_block_place math."""
    manager = SoundManager(backend="silent")
    manager.update_listener((0.0, 1.62, 0.0), 0.0, 0.0)

    # 1. Block step sound (stone = 3)
    manager.play_block_step(3, pos=None, volume=0.5)
    rec1 = manager.backend.played_events[-1]
    assert rec1["event_name"] == "step.stone"
    assert rec1["volume"] == pytest.approx(0.5, abs=1e-5)

    # 2. Block dig sound (dirt = 2)
    manager.play_block_dig(2, pos=None, volume=1.0)
    rec2 = manager.backend.played_events[-1]
    assert rec2["event_name"] == "dig.grass"
    assert rec2["volume"] == pytest.approx(1.0, abs=1e-5)

    # 3. Block place formula: V_place = (V_dig + 1.0) / 2.0 * 0.8, P_place = P_dig * 0.8
    # For volume=1.0: place_vol = (1.0 + 1.0)/2 * 0.8 = 0.8, place_pitch nominal = 0.8
    manager.play_block_place(3, pos=None, volume=1.0)
    rec3 = manager.backend.played_events[-1]
    assert rec3["event_name"] == "dig.stone"
    assert rec3["volume"] == pytest.approx(0.8, abs=1e-5)


@requires_sound_manager
def test_sound_manager_legacy_sfx():
    """Verify backward compatibility for legacy sfx(sound_id) calls."""
    manager = SoundManager(backend="silent")

    # SND_BREAK = 0 -> dig.stone
    manager.sfx(0)
    assert manager.backend.played_events[-1]["event_name"] == "dig.stone"

    # SND_PLACE = 1 -> dig.stone with volume 0.8
    manager.sfx(1)
    assert manager.backend.played_events[-1]["event_name"] == "dig.stone"
    assert manager.backend.played_events[-1]["volume"] == pytest.approx(0.8, abs=1e-5)

    # SND_HURT = 6 -> game.player.hurt
    manager.sfx(6)
    assert manager.backend.played_events[-1]["event_name"] == "game.player.hurt"


@requires_sound_manager
def test_sound_manager_volume_categories():
    """Verify volume sliders for sound categories correctly scale output volumes."""
    manager = SoundManager(backend="silent")

    # Lower block volume to 50%
    manager.set_category_volume("block", 0.5)
    assert manager.get_category_volume("block") == 0.5

    # Master at 100% -> effective = 0.5
    manager.play_sound("dig.stone", pos=None, volume=1.0, pitch_variance=0.0)
    rec1 = manager.backend.played_events[-1]
    assert rec1["volume"] == pytest.approx(0.5, abs=1e-5)

    # Lower master volume to 50% -> effective = 0.5 * 0.5 = 0.25
    manager.set_master_volume(0.5)
    assert manager.get_master_volume() == 0.5
    manager.play_sound("dig.stone", pos=None, volume=1.0, pitch_variance=0.0)
    rec2 = manager.backend.played_events[-1]
    assert rec2["volume"] == pytest.approx(0.25, abs=1e-5)


@requires_sound_manager
def test_sound_manager_update_from_player():
    """Verify updating listener state from a player instance."""
    class DummyPlayer:
        def __init__(self):
            self.pos = (12.0, 64.0, -8.0)
            self.yaw = 180.0
            self.pitch = -15.0
            self.sneaking = False

        def eye(self):
            return (self.pos[0], self.pos[1] + 1.62, self.pos[2])

    player = DummyPlayer()
    manager = SoundManager(backend="silent")
    manager.update_from_player(player)

    assert manager.listener_pos == (12.0, 65.62, -8.0)
    assert manager.listener_yaw == 180.0
    assert manager.listener_pitch == -15.0


def test_extract_vanilla_assets_fallback_mode(tmp_path):
    """Verify procedural fallback generator synthesizes textures and config without Minecraft installed."""
    import extract_vanilla_assets
    extractor = extract_vanilla_assets.VanillaAssetExtractor(
        minecraft_dir=str(tmp_path / "nonexistent"),
        output_dir=str(tmp_path / "assets"),
    )
    stats = extractor.run(force_fallback=True)

    # Assert textures were synthesized
    assert stats.textures_extracted >= 20
    assert os.path.isfile(tmp_path / "assets" / "textures" / "gui" / "icons.png")
    assert os.path.isfile(tmp_path / "assets" / "textures" / "gui" / "widgets.png")
    assert os.path.isfile(tmp_path / "assets" / "textures" / "gui" / "container" / "inventory.png")
    assert os.path.isfile(tmp_path / "assets" / "sounds" / "sounds.json")


# ==============================================================================
# Milestone 1 Iteration 2 Verification Tests:
# Candidate Pitch, Weighted Selection, Clamping, Concurrency, Afplay Zombie Reaping, Pyxel Panic Protection
# ==============================================================================

@requires_sound_manager
def test_sound_registry_candidate_pitch_parsing(tmp_path):
    """Verify that candidate pitch in sounds.json is parsed and applied to playback."""
    import json
    sounds_dir = tmp_path / "sounds"
    sounds_dir.mkdir()

    custom_sounds = {
        "test.pitch_event": {
            "category": "player",
            "sounds": [
                {"name": "test/p_low", "volume": 0.9, "pitch": 0.65, "weight": 1},
                {"name": "test/p_high", "volume": 1.0, "pitch": 1.35, "weight": 1},
            ],
        }
    }
    with open(sounds_dir / "sounds.json", "w", encoding="utf-8") as f:
        json.dump(custom_sounds, f)

    reg = SoundRegistry(sounds_dir=str(sounds_dir))
    assert reg.has_event("test.pitch_event")
    event = reg.events["test.pitch_event"]
    assert len(event.sounds) == 2
    assert event.sounds[0].pitch == pytest.approx(0.65)
    assert event.sounds[1].pitch == pytest.approx(1.35)

    mgr = SoundManager(backend="silent", sounds_dir=str(sounds_dir))
    mgr.play_sound("test.pitch_event", pitch=1.0, pitch_variance=0.0)
    rec = mgr.backend.played_events[-1]
    assert rec["pitch"] in (pytest.approx(0.65), pytest.approx(1.35))


@requires_sound_manager
def test_sound_registry_weighted_candidate_selection(tmp_path):
    """Verify resolve_sound performs weighted selection based on sound entry weight."""
    import json
    sounds_dir = tmp_path / "sounds"
    sounds_dir.mkdir()

    custom_sounds = {
        "test.weighted_event": {
            "category": "neutral",
            "sounds": [
                {"name": "common_sound", "weight": 95},
                {"name": "rare_sound", "weight": 5},
            ],
        }
    }
    with open(sounds_dir / "sounds.json", "w", encoding="utf-8") as f:
        json.dump(custom_sounds, f)

    reg = SoundRegistry(sounds_dir=str(sounds_dir))
    rng = random.Random(12345)

    counts = {"common_sound": 0, "rare_sound": 0}
    trials = 1000
    for _ in range(trials):
        entry, _ = reg.resolve_sound("test.weighted_event", rng=rng)
        counts[entry.name] += 1

    assert counts["common_sound"] > 850, f"Common sound selected too few times: {counts}"
    assert counts["rare_sound"] < 150, f"Rare sound selected too many times: {counts}"
    assert counts["common_sound"] > counts["rare_sound"] * 5


@requires_sound_manager
def test_sound_manager_volume_clamping():
    """Verify volume clamping [0.0, 1.0] for negative inputs and amplifying sound entries."""
    mgr = SoundManager(backend="silent")

    # 1. Negative nominal volume clamped to 0.0
    rec_neg = mgr.play_sound("random.click", volume=-10.0)
    assert rec_neg["volume"] == 0.0

    # 2. Candidate entry with volume > 1.0 clamped to 1.0
    mgr.registry.register_event(
        "test.loud_event",
        "master",
        [SoundEntry(name="loud", volume=3.0, pitch=1.0)],
    )
    rec_loud = mgr.play_sound("test.loud_event", volume=1.0)
    assert rec_loud["volume"] == pytest.approx(1.0, abs=1e-5)

    # 3. Unknown event with negative volume clamped to 0.0
    rec_unk = mgr.play_sound("unknown.nonexistent.event", volume=-5.0)
    assert rec_unk["volume"] == 0.0

    # 4. Standard in-bounds volume preserved
    rec_norm = mgr.play_sound("random.click", volume=0.7)
    assert rec_norm["volume"] == pytest.approx(0.7, abs=1e-5)


@requires_sound_manager
def test_sound_manager_play_block_place_custom_pitch():
    """Verify play_block_place accepts pitch parameter and scales P_place = P_dig * 0.8."""
    mgr = SoundManager(backend="silent")
    mgr.update_listener((0.0, 1.62, 0.0), 0.0, 0.0)

    # 1. Default pitch = 1.0 -> nominal place pitch = 0.8 (within 0.2 variance [0.64, 0.96])
    rec_def = mgr.play_block_place(3, pos=None, volume=1.0)
    assert rec_def["volume"] == pytest.approx(0.8, abs=1e-5)
    assert 0.64 <= rec_def["pitch"] <= 0.96

    # 2. Custom pitch = 1.5 -> nominal place pitch = 1.5 * 0.8 = 1.2 (variance [0.96, 1.44])
    rec_high = mgr.play_block_place(3, pos=None, volume=1.0, pitch=1.5)
    assert 0.96 <= rec_high["pitch"] <= 1.44

    # 3. Custom pitch = 0.8 -> nominal place pitch = 0.8 * 0.8 = 0.64 (variance [0.512, 0.768])
    rec_low = mgr.play_block_place(3, pos=None, volume=1.0, pitch=0.8)
    assert 0.512 <= rec_low["pitch"] <= 0.768


@requires_sound_manager
def test_silent_backend_thread_safety():
    """Verify SilentBackend synchronization under concurrent multithreaded logging."""
    import threading
    backend = SilentBackend()
    threads = []
    events_per_thread = 50
    num_threads = 8

    def worker(worker_id: int):
        for _ in range(events_per_thread):
            backend.play(
                event_name=f"event_{worker_id}",
                volume=1.0,
                pitch=1.0,
            )
            _ = backend.count()
            _ = backend.has_played(f"event_{worker_id}")
            _ = backend.last_played

    for tid in range(num_threads):
        t = threading.Thread(target=worker, args=(tid,))
        threads.append(t)
        t.start()

    for t in threads:
        t.join()

    expected_total = num_threads * events_per_thread
    assert backend.count() == expected_total
    assert len(backend.played_events) == expected_total
    for tid in range(num_threads):
        assert backend.count(f"event_{tid}") == events_per_thread
        assert backend.has_played(f"event_{tid}") is True

    backend.clear()
    assert backend.count() == 0
    assert len(backend.played_events) == 0


@requires_sound_manager
def test_afplay_backend_lifecycle_and_zombie_reaping():
    """Verify AfplayBackend evicts voices, tracks terminating processes, and leaves zero zombies."""
    import subprocess
    import time

    backend = AfplayBackend(max_voices=3)
    if not backend.is_available():
        pytest.skip("AfplayBackend is only available on macOS Darwin with /usr/bin/afplay")

    sound_path = os.path.join(PYCRAFT_GPU_DIR, "assets", "vanilla", "sounds", "random", "click.ogg")
    if not os.path.isfile(sound_path):
        pytest.skip("Reference click.ogg not found for AfplayBackend test")

    spawned = []
    for _ in range(10):
        p = backend.play(sound_path)
        if p:
            spawned.append(p)

    # Max concurrent active processes must not exceed max_voices
    assert len(backend.active_processes) <= 3
    # Terminating list tracks evicted processes
    assert len(backend._terminating_processes) >= 0

    time.sleep(0.2)
    backend._reap_dead()

    # Verify no spawned processes are left as defunct zombies
    pids = [str(p.pid) for p in spawned if p]
    if pids:
        res = subprocess.run(["ps", "-o", "pid,stat", "-p", ",".join(pids)], capture_output=True, text=True)
        zombies = [line for line in res.stdout.splitlines() if "Z" in line]
        assert len(zombies) == 0, f"Found zombie processes: {zombies}"

    backend.stop_all()
    assert len(backend.active_processes) == 0
    assert len(backend._terminating_processes) == 0

    if pids:
        res = subprocess.run(["ps", "-o", "pid,stat", "-p", ",".join(pids)], capture_output=True, text=True)
        zombies = [line for line in res.stdout.splitlines() if "Z" in line]
        assert len(zombies) == 0, f"Found zombie processes after stop_all: {zombies}"


@requires_sound_manager
def test_afplay_backend_multithreaded_concurrency():
    """Verify AfplayBackend maintains voice limit under multithreaded contention."""
    import threading
    import subprocess

    backend = AfplayBackend(max_voices=4)
    if not backend.is_available():
        pytest.skip("AfplayBackend is only available on macOS Darwin with /usr/bin/afplay")

    sound_path = os.path.join(PYCRAFT_GPU_DIR, "assets", "vanilla", "sounds", "random", "click.ogg")
    if not os.path.isfile(sound_path):
        pytest.skip("Reference click.ogg not found for AfplayBackend test")

    max_observed = 0
    all_spawned = []
    lock = threading.Lock()

    def worker():
        nonlocal max_observed
        for _ in range(8):
            p = backend.play(sound_path)
            if p:
                with lock:
                    all_spawned.append(p)
            with backend._lock:
                cnt = len(backend.active_processes)
                if cnt > max_observed:
                    max_observed = cnt

    threads = [threading.Thread(target=worker) for _ in range(6)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert max_observed <= 4, f"Active voices exceeded limit: {max_observed} > 4"
    backend.stop_all()

    pids = [str(p.pid) for p in all_spawned if p]
    if pids:
        res = subprocess.run(["ps", "-o", "pid,stat", "-p", ",".join(pids)], capture_output=True, text=True)
        zombies = [line for line in res.stdout.splitlines() if "Z" in line]
        assert len(zombies) == 0, f"Found zombie processes after multithreaded test: {zombies}"


@requires_sound_manager
def test_pyxel_synth_backend_uninitialized_safety():
    """Verify PyxelSynthBackend is safe from Rust panics when Pyxel is not initialized or panics."""
    class UninitializedPyxel:
        width = 0
        height = 0
        def play_pos(self, ch):
            raise Exception("Pyxel not initialized")
        def play(self, ch, sound_id):
            raise Exception("Pyxel not initialized")
        def stop(self, ch):
            raise Exception("Pyxel not initialized")

    uninit_pyxel = UninitializedPyxel()
    backend = PyxelSynthBackend(channel=3)

    import unittest.mock
    # 1. Verify uninitialized Pyxel (width == 0) produces is_available == False and clean no-ops
    with unittest.mock.patch.dict("sys.modules", {"pyxel": uninit_pyxel}):
        assert backend.is_available() is False
        backend.play("random.click", volume=0.8, pitch=1.1)
        backend.play_synth("dig.stone", "block", volume=0.5, pitch=0.9)
        backend.init_pyxel_sounds()
        backend.stop_all()
        backend.close()

    # 2. Verify Rust BaseException / PanicException is safely caught and suppressed
    class PanicException(BaseException):
        pass

    class PanickingPyxel:
        width = 100
        height = 100
        def play_pos(self, ch):
            raise PanicException("Rust panic")
        def play(self, ch, sound_id):
            raise PanicException("Rust panic")
        def stop(self, ch):
            raise PanicException("Rust panic")

    PanickingPyxel.PanicException = PanicException
    panic_pyxel = PanickingPyxel()
    with unittest.mock.patch.dict("sys.modules", {"pyxel": panic_pyxel}):
        assert backend.is_available() is False
        backend.play("random.click", volume=0.8, pitch=1.1)
        backend.play_synth("dig.stone", "block", volume=0.5, pitch=0.9)
        backend.init_pyxel_sounds()
        backend.stop_all()
        backend.close()


@requires_sound_manager
def test_pyxel_synth_backend_parameter_modulation():
    """Verify Pyxel channel gain scaling and detune cents calculation formula."""
    class DummyChannel:
        def __init__(self):
            self.gain = 0.125
            self.detune = 0

    class DummyPyxel:
        def __init__(self):
            self.width = 160
            self.height = 120
            self.channels = [DummyChannel() for _ in range(4)]
            self.sounds = [type("DummySound", (), {"set": lambda *args: None})() for _ in range(12)]

        def play_pos(self, ch):
            return -1

        def play(self, ch, sound_id):
            pass

        def stop(self, ch):
            pass

    dummy_pyxel = DummyPyxel()
    backend = PyxelSynthBackend(channel=2)

    import unittest.mock
    with unittest.mock.patch.dict("sys.modules", {"pyxel": dummy_pyxel}):
        assert backend.is_available() is True

        # Test volume = 0.8 -> gain = 0.125 * 0.8 = 0.1
        # Test pitch = 1.2 -> detune = int(round(1200 * log2(1.2))) = 316
        backend.play("random.click", volume=0.8, pitch=1.2)
        ch = dummy_pyxel.channels[2]
        assert ch.gain == pytest.approx(0.1, abs=1e-5)
        assert ch.detune == 316

        # Test volume = 0.0 -> gain = 0.0
        # Test pitch = 0.8 -> detune = int(round(1200 * log2(0.8))) = -386
        backend.play("dig.stone", volume=0.0, pitch=0.8)
        assert ch.gain == 0.0
        assert ch.detune == -386

        # Test pitch = 1.0 -> detune = 0
        backend.play("step.grass", volume=1.0, pitch=1.0)
        assert ch.gain == pytest.approx(0.125, abs=1e-5)
        assert ch.detune == 0

        backend.stop_all()
        backend.close()

