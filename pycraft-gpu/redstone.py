"""Redstone: how levers, buttons, plates, torches, repeaters and dust power each other, and the
lamps, pistons and TNT they drive. A simpler cousin of Minecraft's rules, kept predictable:

- A source gives power 15 to the blocks next to it. A lever, button or plate also powers
  *strongly* the block it is fixed to; a lit torch, the block above it; a repeater, the block in
  front of it.
- Dust carries power, losing 1 a block. It powers the block under it and the blocks it points
  into (weakly).
- A block powered strongly powers the dust and the parts next to it; powered weakly, only the
  parts (a lamp, a piston, a torch fixed to it...).
- A torch goes out when the block it is fixed to is powered (2 ticks later); a repeater copies
  its input to its output after its delay; a lamp lights at once and goes out 2 ticks later.

Each block reacts in its handler, called by the simulation (sim.py) when something next to it
changed or when the time it asked for has come."""
from collections import deque

import blocks as B
from blocks import (AIR, DOWN, FACING_VECTORS, LEVER, OPAQUE, OPPOSITE, PISTON, PISTON_HEAD, REDSTONE_BLOCK,
                    REDSTONE_LAMP, REDSTONE_LAMP_OFF, REDSTONE_TORCH, REDSTONE_WIRE, REPEATER, STICKY_PISTON,
                    STONE_BUTTON, STONE_PRESSURE_PLATE, UP)
from shapes import wire_links

MAX = 15
LAMP_OFF_DELAY = 2
TORCH_DELAY = 2
BUTTON_TICKS = 20
PLATE_CHECK = 10  # ticks between two looks at a pressed plate
BURNOUT_FLIPS, BURNOUT_TICKS = 8, 60  # a torch flipping this often burns out for a while
MAX_WIRES = 4096  # dust looked at in one go, at most
HORIZONTAL = (B.EAST, B.WEST, B.SOUTH, B.NORTH)
SOURCES = {LEVER, STONE_BUTTON, STONE_PRESSURE_PLATE, REDSTONE_TORCH, REDSTONE_WIRE, REPEATER, REDSTONE_BLOCK}


def step(pos, facing, k=1):
    dx, dy, dz = FACING_VECTORS[facing]
    return pos[0] + dx * k, pos[1] + dy * k, pos[2] + dz * k


def facing_of(state):
    f = state & 7
    return f if f < 6 else UP


def support_of(block, state, pos):
    """The block a part is fixed to (None for the blocks that need none)."""
    if block in (LEVER, STONE_BUTTON, REDSTONE_TORCH):
        return step(pos, OPPOSITE[facing_of(state)])
    if block in (REDSTONE_WIRE, STONE_PRESSURE_PLATE, REPEATER):
        return step(pos, DOWN)
    return None


def _around(world, pos):
    def around(dx, dy, dz):
        p = (pos[0] + dx, pos[1] + dy, pos[2] + dz)
        return world.get(*p), world.get_state(*p)
    return around


def wire_points(world, pos):
    """The sides a dust points into (powers): where it links, both ways along a line, all four
    for a lone dot."""
    links = dict(zip(HORIZONTAL, wire_links(_around(world, pos))))
    if not any(links.values()):
        return set(HORIZONTAL)
    if (links[B.EAST] or links[B.WEST]) and not (links[B.SOUTH] or links[B.NORTH]):
        return {B.EAST, B.WEST}
    if (links[B.SOUTH] or links[B.NORTH]) and not (links[B.EAST] or links[B.WEST]):
        return {B.SOUTH, B.NORTH}
    return {d for d, linked in links.items() if linked}


def source_power(world, pos, toward):
    """Power the block at pos gives to its neighbor in direction toward."""
    block = world.get(*pos)
    if block not in SOURCES:
        return 0
    state = world.get_state(*pos)
    if block in (LEVER, STONE_BUTTON, STONE_PRESSURE_PLATE):
        return MAX if state & 8 else 0
    if block == REDSTONE_BLOCK:
        return MAX
    if block == REDSTONE_TORCH:
        lit = not state & 8
        return MAX if lit and toward != OPPOSITE[facing_of(state)] else 0
    if block == REPEATER:
        return MAX if state & 32 and toward == facing_of(state) else 0
    # Dust
    power = state & 15
    if power and (toward == DOWN or toward in wire_points(world, pos)):
        return power
    return 0


def strong_power(world, pos, toward):
    """Power the block at pos gives *strongly* to the block in direction toward."""
    block = world.get(*pos)
    state = world.get_state(*pos)
    if block in (LEVER, STONE_BUTTON):
        return MAX if state & 8 and toward == OPPOSITE[facing_of(state)] else 0
    if block == STONE_PRESSURE_PLATE:
        return MAX if state & 8 and toward == DOWN else 0
    if block == REDSTONE_TORCH:
        return MAX if not state & 8 and toward == UP else 0
    if block == REPEATER:
        return MAX if state & 32 and toward == facing_of(state) else 0
    return 0


def block_strong(world, pos):
    """How strongly a full block is powered (it then powers the dust next to it)."""
    return max(strong_power(world, step(pos, d), OPPOSITE[d]) for d in range(6))


def block_power(world, pos):
    """How a full block is powered, strongly or weakly (it then drives the parts next to it)."""
    if not OPAQUE[world.get(*pos)]:
        return 0
    weak = 0
    for d in range(6):
        n = step(pos, d)
        if world.get(*n) == REDSTONE_WIRE:
            weak = max(weak, source_power(world, n, OPPOSITE[d]))
    return max(weak, block_strong(world, pos))


def power_at(world, pos):
    """The power a part (lamp, piston, TNT) at pos receives: from the sources next to it, and
    from the full blocks next to it that are powered."""
    best = 0
    for d in range(6):
        n = step(pos, d)
        block = world.get(*n)
        if block in SOURCES:
            best = max(best, source_power(world, n, OPPOSITE[d]))
        elif OPAQUE[block]:
            best = max(best, block_power(world, n))
        if best == MAX:
            break
    return best


def spread(sim, pos, dust_changed=False):
    """A source at pos changed: wake the blocks it may power and their neighbors (a lamp next to
    the block a lever is fixed to). Anything but dust changing makes the dust solved this tick
    worth solving again."""
    if not dust_changed:
        sim.memory.pop("wire_solved", None)
    for d in range(6):
        sim.notify(step(pos, d))


# --- Dust ---------------------------------------------------------------------------------------

def wire_neighbors(world, pos):
    """The dust linked to this one: beside it, a step up, or a step down."""
    out = []
    above_open = not OPAQUE[world.get(*step(pos, UP))]
    for d in HORIZONTAL:
        n = step(pos, d)
        block = world.get(*n)
        if block == REDSTONE_WIRE:
            out.append(n)
        elif OPAQUE[block]:
            if above_open and world.get(*step(n, UP)) == REDSTONE_WIRE:
                out.append(step(n, UP))
        elif world.get(*step(n, DOWN)) == REDSTONE_WIRE:
            out.append(step(n, DOWN))
    return out


def _wire_input(world, pos):
    """Power a dust gets from what isn't dust: sources, and strongly powered blocks."""
    best = 0
    for d in range(6):
        n = step(pos, d)
        block = world.get(*n)
        if block == REDSTONE_WIRE:
            continue
        if block in SOURCES:
            best = max(best, source_power(world, n, OPPOSITE[d]))
        elif OPAQUE[block]:
            best = max(best, block_strong(world, n))
    return best


def update_wire(sim, x, y, z):
    """Work out again the power of the whole stretch of dust this one belongs to."""
    world = sim.world
    start = (x, y, z)
    tick, solved = sim.memory.get("wire_solved", (None, set()))
    if tick == sim.now and start in solved:
        return  # its whole stretch was solved this tick, and no source changed since
    sim.memory["wire_solves"] = sim.memory.get("wire_solves", 0) + 1
    network, todo = {start}, deque([start])
    while todo and len(network) < MAX_WIRES:
        p = todo.popleft()
        for n in wire_neighbors(world, p):
            if n not in network:
                network.add(n)
                todo.append(n)
    power = {p: _wire_input(world, p) for p in network}
    # Spread from the strongest: each dust gets the best of its input and its neighbors' minus 1
    order = sorted(network, key=lambda p: -power[p])
    todo = deque(order)
    while todo:
        p = todo.popleft()
        if power[p] <= 1:
            continue
        for n in wire_neighbors(world, p):
            if n in power and power[n] < power[p] - 1:
                power[n] = power[p] - 1
                todo.append(n)
    if tick != sim.now:
        solved = set()
    solved |= network
    sim.memory["wire_solved"] = (sim.now, solved)
    for p, value in power.items():
        if world.get_state(*p) & 15 != value:
            sim.set_block(*p, REDSTONE_WIRE, value)
            spread(sim, p, dust_changed=True)


# --- Handlers -----------------------------------------------------------------------------------

def _supported(sim, x, y, z, block, state):
    """False (and the part broken) when what it is fixed to or stands on is gone."""
    support = support_of(block, state, (x, y, z))
    if support is None or OPAQUE[sim.world.get(*support)]:
        return True
    sim.set_block(x, y, z, AIR)
    spread(sim, (x, y, z))
    return False


def _wire(sim, x, y, z, block, state):
    if _supported(sim, x, y, z, block, state):
        update_wire(sim, x, y, z)


def _lever(sim, x, y, z, block, state):
    _supported(sim, x, y, z, block, state)


def _button(sim, x, y, z, block, state):
    if not _supported(sim, x, y, z, block, state) or not state & 8:
        return
    if sim.after((x, y, z), BUTTON_TICKS):
        sim.set_block(x, y, z, block, state & ~8)
        spread(sim, (x, y, z))
        spread(sim, support_of(block, state, (x, y, z)))


def _plate(sim, x, y, z, block, state):
    if not _supported(sim, x, y, z, block, state):
        return
    pressed = (x, y, z) in sim.occupied
    if pressed != bool(state & 8):
        sim.set_block(x, y, z, block, state ^ 8)
        spread(sim, (x, y, z))
        spread(sim, (x, y - 1, z))
    if pressed or state & 8:
        sim.schedule((x, y, z), PLATE_CHECK)


def _torch(sim, x, y, z, block, state):
    if not _supported(sim, x, y, z, block, state):
        return
    pos = (x, y, z)
    lit = not state & 8
    should = block_power(sim.world, support_of(block, state, pos)) == 0
    flips = [t for t in sim.memory.get(pos, ()) if sim.now - t < BURNOUT_TICKS]
    sim.memory[pos] = flips
    if should and len(flips) >= BURNOUT_FLIPS:  # burnt out: stays dark a while
        sim.schedule(pos, BURNOUT_TICKS)
        should = False
    if lit == should:
        sim.cancel(pos)
        return
    if sim.after(pos, TORCH_DELAY):
        flips.append(sim.now)
        sim.set_block(x, y, z, block, state ^ 8)
        spread(sim, pos)
        spread(sim, step(pos, UP))


def repeater_input(world, pos, state):
    back = step(pos, OPPOSITE[facing_of(state)])
    block = world.get(*back)
    if block in SOURCES:
        return source_power(world, back, facing_of(state))
    if OPAQUE[block]:
        return block_power(world, back)
    return 0


def _repeater(sim, x, y, z, block, state):
    if not _supported(sim, x, y, z, block, state):
        return
    pos = (x, y, z)
    on = repeater_input(sim.world, pos, state) > 0
    if on == bool(state & 32):
        sim.cancel(pos)
        return
    if sim.after(pos, 2 * (((state >> 3) & 3) + 1)):
        sim.set_block(x, y, z, block, state ^ 32)
        spread(sim, pos)
        spread(sim, step(pos, facing_of(state)))


def _lamp(sim, x, y, z, block, state):
    pos = (x, y, z)
    powered = power_at(sim.world, pos) > 0
    if block == REDSTONE_LAMP_OFF:
        if powered:
            sim.set_block(x, y, z, REDSTONE_LAMP)
        return
    if powered:
        sim.cancel(pos)
    elif sim.after(pos, LAMP_OFF_DELAY):
        sim.set_block(x, y, z, REDSTONE_LAMP_OFF)


# --- Pistons ---------------------------------------------------------------------------------------

PUSH_LIMIT = 12
IMMOVABLE = {B.BEDROCK, B.OBSIDIAN, PISTON_HEAD}
PISTONS = (PISTON, STICKY_PISTON)


def _crushed(block):
    """Blocks a piston breaks instead of pushing: plants, and the small redstone parts."""
    return B.PLANT[block] or B.FLAT[block] or block == B.WATER


def _immovable(block, state):
    return block in IMMOVABLE or (block in PISTONS and state & 8)


def push(sim, x, y, z, facing, sticky):
    """Push the line of blocks in front of a piston one block further, and put its head in front.
    False (and nothing moved) when it can't: more than PUSH_LIMIT blocks, or one that doesn't move."""
    world = sim.world
    pos = (x, y, z)
    line = []
    for i in range(1, PUSH_LIMIT + 2):
        p = step(pos, facing, i)
        if not world.inside(*p):
            return False
        block, state = world.get(*p), world.get_state(*p)
        if block == AIR or _crushed(block):
            break
        if _immovable(block, state) or len(line) == PUSH_LIMIT:
            return False
        line.append((p, block, state))
    end = step(pos, facing, len(line) + 1)
    if world.get(*end) != AIR:  # a plant or a redstone part crushed: what it powered goes dark
        sim.set_block(*end, AIR)
        spread(sim, end)
    for p, block, state in reversed(line):  # the farthest first, into the free cell after it
        sim.set_block(*step(p, facing), block, state)
        spread(sim, step(p, facing))
    head = step(pos, facing)
    sim.set_block(*head, PISTON_HEAD, facing | (8 if sticky else 0))
    sim.set_block(x, y, z, world.get(x, y, z), world.get_state(x, y, z) | 8)
    return True


def retract(sim, x, y, z, facing, sticky):
    """Take the head back in (a sticky piston pulls the block in front of its head)."""
    world = sim.world
    head = step((x, y, z), facing)
    block = world.get(x, y, z)
    sim.set_block(x, y, z, block, world.get_state(x, y, z) & ~8)
    if world.get(*head) == PISTON_HEAD:
        sim.set_block(*head, AIR)
    if sticky:
        front = step(head, facing)
        b, st = world.get(*front), world.get_state(*front)
        if b != AIR and not _crushed(b) and not _immovable(b, st):
            sim.set_block(*front, AIR)
            sim.set_block(*head, b, st)


def piston_power(world, pos, facing):
    """Power reaching a piston, except through its front."""
    best = 0
    for d in range(6):
        if d == facing:
            continue
        n = step(pos, d)
        block = world.get(*n)
        if block in SOURCES:
            best = max(best, source_power(world, n, OPPOSITE[d]))
        elif OPAQUE[block]:
            best = max(best, block_power(world, n))
    return best


def _piston(sim, x, y, z, block, state):
    facing = facing_of(state)
    sticky = block == STICKY_PISTON
    powered = piston_power(sim.world, (x, y, z), facing) > 0
    extended = bool(state & 8)
    if extended and sim.world.get(*step((x, y, z), facing)) != PISTON_HEAD:
        sim.set_block(x, y, z, block, state & ~8)  # its head was broken
        return
    if powered and not extended:
        push(sim, x, y, z, facing, sticky)
    elif not powered and extended:
        retract(sim, x, y, z, facing, sticky)


def _head(sim, x, y, z, block, state):
    facing = facing_of(state)
    base = step((x, y, z), OPPOSITE[facing])
    b, st = sim.world.get(*base), sim.world.get_state(*base)
    if b not in PISTONS or not st & 8 or facing_of(st) != facing:
        sim.set_block(x, y, z, AIR)  # no piston behind it any more


# --- TNT ----------------------------------------------------------------------------------------------

TNT_FUSE = 80  # ticks
BLAST_RADIUS = 4
BLAST_PROOF = {B.BEDROCK, B.OBSIDIAN, B.WATER, AIR}


def _lit(sim, pos, fuse):
    lit = sim.memory.setdefault("lit_tnt", set())
    if pos not in lit:
        lit.add(pos)
        sim.cancel(pos)
        sim.after(pos, fuse)


def _tnt(sim, x, y, z, block, state):
    pos = (x, y, z)
    lit = sim.memory.setdefault("lit_tnt", set())
    if pos not in lit:
        if power_at(sim.world, pos) > 0:
            _lit(sim, pos, TNT_FUSE)
        return
    if sim.after(pos, TNT_FUSE):
        lit.discard(pos)
        explode(sim, x, y, z)


def explode(sim, x, y, z, radius=BLAST_RADIUS):
    """Blow away the blocks within radius (not bedrock, obsidian or water); TNT caught in it is
    lit, with a short fuse."""
    world = sim.world
    sim.set_block(x, y, z, AIR)
    r2 = radius * radius + 0.5
    for dx in range(-radius, radius + 1):
        for dy in range(-radius, radius + 1):
            for dz in range(-radius, radius + 1):
                if dx * dx + dy * dy + dz * dz > r2:
                    continue
                p = (x + dx, y + dy, z + dz)
                block = world.get(*p)
                if block in BLAST_PROOF or B.UNBREAKABLE[block]:
                    continue
                if block == B.TNT:
                    _lit(sim, p, 10 + (dx * 7 + dy * 13 + dz * 5) % 21)  # 10 to 30 ticks, never all at once
                    continue
                if block in SOURCES or block in PISTONS:
                    spread(sim, p)  # what it powered goes dark
                sim.set_block(*p, AIR)
    sim.events.append(("explode", (x, y, z)))


def install(sim):
    """Give the simulation the redstone blocks' handlers."""
    sim.handlers.update({
        REDSTONE_WIRE: _wire, LEVER: _lever, STONE_BUTTON: _button, STONE_PRESSURE_PLATE: _plate,
        REDSTONE_TORCH: _torch, REPEATER: _repeater, REDSTONE_LAMP: _lamp, REDSTONE_LAMP_OFF: _lamp,
        PISTON: _piston, STICKY_PISTON: _piston, PISTON_HEAD: _head, B.TNT: _tnt,
    })


# --- What the player does -------------------------------------------------------------------------

def toggle_lever(sim, x, y, z):
    state = sim.world.get_state(x, y, z)
    sim.set_block(x, y, z, LEVER, state ^ 8)
    spread(sim, (x, y, z))
    spread(sim, support_of(LEVER, state, (x, y, z)))


def press_button(sim, x, y, z):
    state = sim.world.get_state(x, y, z)
    if not state & 8:
        sim.set_block(x, y, z, STONE_BUTTON, state | 8)
        spread(sim, (x, y, z))
        spread(sim, support_of(STONE_BUTTON, state, (x, y, z)))
        sim.cancel((x, y, z))
        sim.after((x, y, z), BUTTON_TICKS)


def cycle_repeater(sim, x, y, z):
    """Next delay: 1, 2, 3, 4 notches."""
    state = sim.world.get_state(x, y, z)
    delay = ((state >> 3) & 3) + 1 & 3
    sim.set_block(x, y, z, REPEATER, (state & ~(3 << 3)) | delay << 3)
