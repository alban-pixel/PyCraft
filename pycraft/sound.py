"""Sound effects and the generated music, and their volumes."""
import pyxel


MUSIC_GAIN, SOUND_GAIN = 0.14, 0.125  # the channels' gains at full volume

# Sound numbers; sound effects play on channel 3, music on channels 0-2
SND_BREAK, SND_PLACE, SND_JUMP, SND_STEP, SND_SPLASH, SND_CLICK = range(6)
SFX_CHANNEL = 3


class Sound:
    """The App's sounds: made once, played on channel SFX_CHANNEL; the music on the other three."""

    def init_sounds(self):
        pyxel.sounds[SND_BREAK].set("a1f1c1", "n", "654", "nnf", 4)
        pyxel.sounds[SND_PLACE].set("c2", "n", "5", "f", 6)
        pyxel.sounds[SND_JUMP].set("c2", "n", "2", "f", 3)
        pyxel.sounds[SND_STEP].set("f1", "n", "2", "f", 4)
        pyxel.sounds[SND_SPLASH].set("g2c2f1", "n", "543", "nnf", 7)
        pyxel.sounds[SND_CLICK].set("c3", "p", "4", "f", 6)
        self.music = pyxel.gen_bgm(2, 0, 0, 1234)
    def sfx(self, sound):
        pyxel.play(SFX_CHANNEL, sound)
    def apply_sound(self):
        """The volumes of the settings: the music's three channels and the sound effects' one.
        The music stops at volume 0 and starts again from the top above it."""
        music = self.settings["music_volume"] / 100
        for ch in range(3):
            pyxel.channels[ch].gain = MUSIC_GAIN * music
        pyxel.channels[SFX_CHANNEL].gain = SOUND_GAIN * self.settings["sound_volume"] / 100
        if music > 0 and not self.music_playing:
            for ch, mml in enumerate(self.music[:3]):  # the 4th part is empty for this instrumentation
                pyxel.play(ch, mml, loop=True)
        elif music == 0 and self.music_playing:
            for ch in range(3):
                pyxel.stop(ch)
        self.music_playing = music > 0
