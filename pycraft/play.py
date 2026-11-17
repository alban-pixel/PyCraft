"""Playing: moving and looking around, breaking, placing and picking blocks, working levers and
buttons."""
import numpy as np
import pyxel

from pycraft import redstone
from pycraft.blocks import (BLOCK_NAMES, DOWN, EAST, FACING, FACING_VECTORS, GROWS_ON, LEVER, NORTH, OPAQUE,
                            OPPOSITE, PISTON, PLACEABLE, PLANT, REDSTONE_TORCH, REDSTONE_WIRE, REPEATER, SOLID,
                            SOUTH, STICKY_PISTON, STONE_BUTTON, STONE_PRESSURE_PLATE, UNBREAKABLE, UP, WATER,
                            WEST, turned)
from pycraft.sound import SND_BREAK, SND_CLICK, SND_JUMP, SND_PLACE, SND_SPLASH, SND_STEP
from pycraft.ui import BASE_WIDTH


REACH = 6.0
MOUSE_SENSITIVITY = 0.45  # degrees per pixel at 320x180, with the mouse speed setting at 100%
HELP_SECONDS = 15
INTERACTIVE = {LEVER, STONE_BUTTON, REPEATER}  # a right click works them instead of placing a block


def right_click(block, first_press):
    """What a right click on this block does: "act" (flip a lever...), "place" a block against it,
    or nothing. Held down, it repeats placing, but never flips a lever again or places on it."""
    if block in INTERACTIVE:
        return "act" if first_press else None
    return "place"


def _main_direction(v, horizontal=False):
    """The facing (blocks.FACING_VECTORS) a vector points along the most."""
    x, y, z = v
    if not horizontal and abs(y) > max(abs(x), abs(z)):
        return UP if y > 0 else DOWN
    if abs(x) > abs(z):
        return EAST if x > 0 else WEST
    return SOUTH if z > 0 else NORTH


def placement(block, hit, previous, look, world):
    """The (block, state) to put in the cell previous, aiming at the block hit while looking along
    look; None when it can't go there (a lever needs a full block to be fixed to...)."""
    face = tuple(p - h for p, h in zip(previous, hit))
    facing = FACING_VECTORS.index(face) if face in FACING_VECTORS else UP
    floor = OPAQUE[world.get(previous[0], previous[1] - 1, previous[2])]
    if block in (LEVER, STONE_BUTTON, REDSTONE_TORCH):
        if not OPAQUE[world.get(*hit)] or (block == REDSTONE_TORCH and facing == DOWN):
            return None
        state = facing
        if block == LEVER and facing in (UP, DOWN) and abs(look[0]) > abs(look[2]):
            state |= 16  # a lever on the floor turns with the player's look
        return block, state
    if block in (REDSTONE_WIRE, STONE_PRESSURE_PLATE, REPEATER):
        if not floor:
            return None
        return block, (_main_direction(look, horizontal=True) if block == REPEATER else 0)
    if block in (PISTON, STICKY_PISTON):
        return block, OPPOSITE[_main_direction(look)]  # its face looks back at the player
    return block, 0


# The block the "pick" key puts in the hotbar for each block of the world (a turned furnace: a furnace)
PICKS = {b: b for b in PLACEABLE}
PICKS.update({version: block for block, versions in FACING.items() for version in versions})


class Playing:
    """The App while playing."""

    def update_playing(self):
        dt = self.dt
        keys = self.controls
        self.play_time += dt
        self.time_of_day = (self.time_of_day + dt / (self.settings["day_length"] * 60)) % 1.0
        self.sim.update(dt)  # the machines: 20 ticks a second
        if self.sim.events:
            for event, pos in self.sim.events:
                if event == "explode":
                    self.sfx(SND_BREAK)
            self.sim.events.clear()
        if self.play_time - dt < HELP_SECONDS <= self.play_time:
            self.show_help = False  # hide the help once, after the first seconds of play
        autosave = self.settings["autosave"] * 60
        if autosave and self.play_time - self.last_save > autosave:
            self.save()
            self.notify("Game saved")

        if pyxel.btnp(pyxel.KEY_ESCAPE):
            self.set_state("paused")
            return
        if keys.pressed("inventory"):
            self.set_state("inventory")
            return
        if keys.pressed("mouse"):
            if self.mouse_captured:
                self.mouse_captured = False
            else:
                self.capture_mouse()
        if keys.pressed("help"):
            self.show_help = not self.show_help
        if keys.pressed("info"):
            self.show_debug = not self.show_debug
        if keys.pressed("chat") or pyxel.btnp(pyxel.KEY_SLASH):
            self.chat_text = "/" if pyxel.btnp(pyxel.KEY_SLASH) else ""
            self.set_state("chat")
            return

        self.update_look()
        events = self.player.update(self.world, dt, keys)
        for event, sound in (("jump", SND_JUMP), ("step", SND_STEP), ("splash", SND_SPLASH)):
            if event in events:
                self.sfx(sound)
        self.update_hotbar_keys()

        # Break, place and pick blocks (hold the key to repeat)
        self.target = self.world.raycast(self.player.eye(), self.player.forward(), REACH)
        if not self.mouse_captured:
            if pyxel.btnp(pyxel.MOUSE_BUTTON_LEFT):
                self.capture_mouse()
            return
        hold, repeat = self.frames(0.25), self.frames(0.13)
        if self.target and keys.pressed("pick"):
            self.pick_block(self.world.get(*self.target[0]))
        elif self.target and keys.pressed("break", hold=hold, repeat=repeat):
            x, y, z = self.target[0]
            if UNBREAKABLE[self.world.get(x, y, z)]:
                self.notify("Bedrock can't be broken")
            else:
                broken, state = self.world.get(x, y, z), self.world.get_state(x, y, z)
                self.sim.set_block(x, y, z, 0)
                if broken in redstone.SOURCES:  # what it powered goes dark
                    redstone.spread(self.sim, (x, y, z))
                    support = redstone.support_of(broken, state, (x, y, z))
                    if support is not None:
                        redstone.spread(self.sim, support)
                if PLANT[self.world.get(x, y + 1, z)]:  # the plant on it goes too
                    self.sim.set_block(x, y + 1, z, 0)
                self.sfx(SND_BREAK)
        elif self.target and keys.pressed("place", hold=hold, repeat=repeat) and right_click(
                self.world.get(*self.target[0]), keys.pressed("place")) == "act":
            x, y, z = self.target[0]
            act = {LEVER: redstone.toggle_lever, STONE_BUTTON: redstone.press_button,
                   REPEATER: redstone.cycle_repeater}[self.world.get(x, y, z)]
            act(self.sim, x, y, z)
            self.sfx(SND_CLICK)
        elif self.target and keys.pressed("place", hold=hold, repeat=repeat) and right_click(
                self.world.get(*self.target[0]), keys.pressed("place")) == "place":
            # Aiming at a plant puts the block in its place, like on the ground under it
            x, y, z = self.target[0] if PLANT[self.world.get(*self.target[0])] else self.target[1]
            block = turned(self.hotbar[self.selected], self.player.forward())  # a front faces the player
            here = self.world.get(x, y, z)
            free = self.world.inside(x, y, z) and (here in (0, WATER) or PLANT[here])
            if free and PLANT[block] and (here == WATER or not GROWS_ON[block, self.world.get(x, y - 1, z)]):
                grounds = [BLOCK_NAMES[g].lower() for g in np.flatnonzero(GROWS_ON[block])]
                self.notify("%s grows only on %s or %s" % (BLOCK_NAMES[block], ", ".join(grounds[:-1]), grounds[-1]))
            elif free and (not SOLID[block] or not self.player.overlaps(x, y, z)):  # plants and water: walk-through
                placed = placement(block, self.target[0], (x, y, z), self.player.forward(), self.world)
                if placed is None:
                    self.notify("%s needs a full block to go on" % BLOCK_NAMES[block])
                else:
                    self.sim.set_block(x, y, z, *placed)
                    self.sfx(SND_PLACE)
    def pick_block(self, block):
        """The block looked at becomes the chosen one: its hotbar slot if it has one, else it
        takes the chosen slot's place."""
        block = PICKS.get(int(block))
        if block is None:
            return
        if block in self.hotbar:
            self.selected = self.hotbar.index(block)
        else:
            self.hotbar[self.selected] = block
        self.selected_time = self.play_time
        self.sfx(SND_CLICK)
    def zooming(self):
        return self.state == "playing" and self.mouse_captured and self.controls.held("zoom")
    def update_look(self):
        s = self.settings
        keys_yaw = pyxel.btn(pyxel.KEY_LEFT) - pyxel.btn(pyxel.KEY_RIGHT)
        keys_pitch = pyxel.btn(pyxel.KEY_UP) - pyxel.btn(pyxel.KEY_DOWN)
        zoom = self.view_fov / s["fov"]  # zoomed in, the view turns as much slower as it is narrower
        self.player.look(keys_yaw * s["look_speed"] * zoom * self.dt, keys_pitch * s["look_speed"] * zoom * self.dt)
        if not self.mouse_captured:
            return
        w, h = pyxel.width, pyxel.height
        mx, my = pyxel.mouse_x, pyxel.mouse_y
        dx, dy = mx - self.last_mouse[0], my - self.last_mouse[1]
        # (the same turn for the same hand movement at any resolution)
        sensitivity = MOUSE_SENSITIVITY * s["sensitivity"] / 100 * BASE_WIDTH / w * zoom
        self.player.look(-dx * sensitivity, (dy if s["invert_y"] else -dy) * sensitivity)
        # Only move the cursor back to the center when it gets near the edge: re-centering every
        # frame would throw away slow movements smaller than one Pyxel pixel.
        if not self.headless and (abs(mx - w / 2) > w / 4 or abs(my - h / 2) > h / 4):
            pyxel.set_mouse_pos(w / 2, h / 2)
            self.last_mouse = (w // 2, h // 2)
        else:
            self.last_mouse = (mx, my)
