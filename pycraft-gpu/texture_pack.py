"""Texture / Resource Pack Manager for PyCraft.

Manages built-in and user-installed resource packs located in `resourcepacks/`.
Supports loading packs from directories and .zip files with pack.mcmeta metadata,
live hot-reloading into Pyxel image bank 0 and ModernGL texture 0 without restarting.
Fully compatible with standard Minecraft 1.6-1.20+ resource packs containing
individual block and item PNG textures in `assets/minecraft/textures/blocks/` (or `block/`).
"""
import io
import json
import os
import shutil
import zipfile
from dataclasses import dataclass
from typing import Dict, List, Optional, Set, Tuple

import numpy as np

from blocks import (
    ATLAS_TILES, TILE, build_atlas,
    T_GRASS_TOP, T_GRASS_SIDE, T_DIRT, T_STONE, T_COBBLE, T_PLANKS, T_LOG_SIDE, T_LOG_TOP, T_LEAVES,
    T_SAND, T_BRICK, T_GLASS, T_WATER, T_COAL, T_IRON, T_BEDROCK,
    T_GOLD, T_DIAMOND, T_GLOWSTONE, T_SNOW, T_SNOW_SIDE,
    T_CRAFT_TOP, T_CRAFT_SIDE, T_ICE, T_SLIME, T_OBSIDIAN, T_LAVA,
    T_GRANITE, T_POLISHED_GRANITE, T_DIORITE, T_POLISHED_DIORITE, T_ANDESITE,
    T_POLISHED_ANDESITE, T_PRISMARINE, T_PRISMARINE_BRICKS, T_DARK_PRISMARINE, T_SEA_LANTERN,
    T_RED_SAND, T_RED_SANDSTONE_SIDE, T_RED_SANDSTONE_TOP, T_RED_SANDSTONE_BOTTOM,
    T_CHISELED_RED_SANDSTONE, T_SMOOTH_RED_SANDSTONE,
    T_COARSE_DIRT, T_PODZOL_TOP, T_PODZOL_SIDE, T_SPONGE, T_WET_SPONGE,
    T_SPRUCE_PLANKS, T_BIRCH_PLANKS, T_JUNGLE_PLANKS, T_ACACIA_PLANKS, T_DARK_OAK_PLANKS,
    T_IRON_TRAPDOOR,
    T_CRACK_0, T_CRACK_1, T_CRACK_2, T_CRACK_3,
    T_ZOMBIE_FACE, T_ZOMBIE_BODY, T_PIG_FACE, T_PIG_BODY,
    T_STICK, T_ARMOR_STAND,
    T_WOOD_PICKAXE, T_STONE_PICKAXE, T_IRON_PICKAXE, T_DIAMOND_PICKAXE,
    T_WOOD_SWORD, T_STONE_SWORD, ITEM_IRON_SWORD_TILE, T_DIAMOND_SWORD,
    T_RAW_PORK, T_COOKED_PORK, T_RAW_MUTTON, T_COOKED_MUTTON,
    T_RAW_RABBIT, T_COOKED_RABBIT, T_RABBIT_STEW, T_RABBIT_FOOT,
    T_RABBIT_HIDE, T_PRISMARINE_SHARD, T_PRISMARINE_CRYSTALS,
    T_FURNACE_FRONT, T_FURNACE_FRONT_LIT, T_FURNACE_SIDE, T_FURNACE_TOP,
    T_CHEST_FRONT, T_CHEST_SIDE, T_CHEST_TOP,
    T_DISPENSER_FRONT, T_HOPPER_TOP, T_HOPPER_SIDE,
    T_BREWING_STAND, T_ANVIL_TOP, T_ANVIL_SIDE,
    T_ENCHANTING_TABLE_TOP, T_ENCHANTING_TABLE_SIDE,
    T_JUKEBOX_TOP, T_JUKEBOX_SIDE, T_NOTE_BLOCK, T_BEACON,
    T_TORCH, T_REDSTONE_TORCH,
    T_TALL_GRASS, T_FERN, T_DEAD_BUSH,
    T_DANDELION, T_POPPY, T_BLUE_ORCHID, T_ALLIUM, T_RED_TULIP,
    T_OXEYE_DAISY, T_SUNFLOWER,
    T_BROWN_MUSHROOM, T_RED_MUSHROOM,
    T_SUGAR_CANE, T_CACTUS_SIDE, T_CACTUS_TOP,
    T_OAK_SAPLING, T_SPRUCE_SAPLING, T_BIRCH_SAPLING,
    T_LADDER, T_VINE, T_LILY_PAD, T_COBWEB,
    T_WOODEN_DOOR_TOP, T_WOODEN_DOOR_BOTTOM,
    T_IRON_DOOR_TOP, T_IRON_DOOR_BOTTOM,
    T_WOODEN_TRAPDOOR,
    T_REDSTONE_WIRE, T_REDSTONE_REPEATER, T_REDSTONE_COMPARATOR,
    T_REDSTONE_LAMP_OFF, T_REDSTONE_LAMP_ON,
    T_LEVER, T_STONE_BUTTON,
    T_RAIL, T_POWERED_RAIL,
    T_PISTON_TOP, T_PISTON_SIDE,
    T_DAYLIGHT_DETECTOR, T_TNT_SIDE,
    T_TNT_TOP, T_TNT_BOTTOM,
    T_COAL_BLOCK, T_IRON_BLOCK, T_GOLD_BLOCK, T_DIAMOND_BLOCK,
    T_EMERALD_BLOCK, T_REDSTONE_BLOCK, T_LAPIS_BLOCK,
    T_LAPIS_ORE, T_EMERALD_ORE, T_NETHER_QUARTZ_ORE, T_REDSTONE_ORE,
    T_QUARTZ_BLOCK_TOP, T_QUARTZ_BLOCK_SIDE, T_QUARTZ_PILLAR_SIDE,
    T_STONE_BRICKS, T_MOSSY_STONE_BRICKS, T_CRACKED_STONE_BRICKS, T_CHISELED_STONE_BRICKS,
    T_MOSSY_COBBLE, T_NETHERRACK, T_SOUL_SAND, T_NETHER_BRICKS, T_END_STONE,
    T_CLAY_BLOCK, T_HARDENED_CLAY,
    T_HAY_SIDE, T_HAY_TOP, T_BOOKSHELF,
    T_PUMPKIN_SIDE, T_PUMPKIN_TOP,
    T_PUMPKIN_FRONT, T_JACK_O_LANTERN_FRONT,
    T_MELON_SIDE, T_MELON_TOP,
    T_FARMLAND_TOP, T_WHEAT_STAGE_7,
    T_WHITE_WOOL, T_RED_WOOL, T_BLUE_WOOL, T_YELLOW_WOOL, T_GREEN_WOOL, T_BLACK_WOOL,
    T_IRON_BARS, T_GLASS_PANE, T_STONE_SLAB_SIDE, T_MYCELIUM_TOP,
    T_CREEPER_FACE, T_SKELETON_FACE, T_SPIDER_FACE, T_ENDERMAN_FACE,
    T_COW_FACE, T_SHEEP_FACE, T_CHICKEN_FACE, T_VILLAGER_FACE,
    T_SLIME_FACE, T_GHAST_FACE, T_BLAZE_FACE, T_WOLF_FACE,
    T_OCELOT_FACE, T_IRON_GOLEM_FACE, T_SNOW_GOLEM_FACE, T_WITCH_FACE,
    T_COAL_ITEM, T_IRON_INGOT, T_GOLD_INGOT, T_DIAMOND_ITEM,
    T_EMERALD_ITEM, T_REDSTONE_ITEM, T_LAPIS_ITEM, T_QUARTZ_ITEM,
    T_BREAD, T_APPLE, T_GOLDEN_APPLE, T_CARROT, T_POTATO,
    T_RAW_BEEF, T_STEAK, T_RAW_CHICKEN,
    T_COOKED_CHICKEN, T_GUNPOWDER, T_STRING, T_FEATHER,
    T_BONE, T_ARROW, T_BOW, T_SNOWBALL, T_SLIMEBALL,
    T_BLAZE_ROD, T_GHAST_TEAR, T_NETHER_STAR, T_ENDER_PEARL,
    T_LEATHER, T_WHEAT_ITEM, T_FLINT,
    T_BUCKET, T_WATER_BUCKET, T_LAVA_BUCKET, T_MILK_BUCKET,
    T_FLINT_AND_STEEL, T_SHEARS,
    T_IRON_HELMET, T_IRON_CHESTPLATE, T_IRON_LEGGINGS, T_IRON_BOOTS,
    T_DIAMOND_HELMET, T_DIAMOND_CHESTPLATE, T_DIAMOND_LEGGINGS, T_DIAMOND_BOOTS,
    T_BED_ITEM, T_DRAGON_EGG,
)

# Comprehensive mapping from PyCraft tile indices (0..255) to standard Minecraft texture names
MINECRAFT_TILE_MAP: Dict[int, List[str]] = {
    T_GRASS_TOP: ["grass_top.png", "grass_block_top.png"],
    T_GRASS_SIDE: ["grass_side.png", "grass_block_side.png"],
    T_DIRT: ["dirt.png"],
    T_STONE: ["stone.png"],
    T_COBBLE: ["cobblestone.png"],
    T_PLANKS: ["planks_oak.png", "oak_planks.png", "planks.png"],
    T_LOG_SIDE: ["log_oak.png", "oak_log.png", "log.png"],
    T_LOG_TOP: ["log_oak_top.png", "oak_log_top.png", "log_top.png"],
    T_LEAVES: ["leaves_oak.png", "oak_leaves.png", "leaves_oak_opaque.png", "leaves.png"],
    T_SAND: ["sand.png"],
    T_BRICK: ["brick.png", "bricks.png"],
    T_GLASS: ["glass.png"],
    T_WATER: ["water_still.png", "water.png", "water_flow.png"],
    T_COAL: ["coal_ore.png"],
    T_IRON: ["iron_ore.png"],
    T_BEDROCK: ["bedrock.png"],
    T_GOLD: ["gold_ore.png"],
    T_DIAMOND: ["diamond_ore.png"],
    T_GLOWSTONE: ["glowstone.png"],
    T_SNOW: ["snow.png"],
    T_SNOW_SIDE: ["grass_side_snowed.png", "snow_side.png"],
    T_CRAFT_TOP: ["crafting_table_top.png"],
    T_CRAFT_SIDE: ["crafting_table_side.png", "crafting_table_front.png"],
    T_ICE: ["ice.png", "packed_ice.png"],
    T_SLIME: ["slime.png", "slime_block.png"],
    T_OBSIDIAN: ["obsidian.png"],
    T_LAVA: ["lava_still.png", "lava.png", "lava_flow.png"],
    T_GRANITE: ["stone_granite.png", "granite.png"],
    T_POLISHED_GRANITE: ["stone_granite_smooth.png", "granite_smooth.png", "polished_granite.png"],
    T_DIORITE: ["stone_diorite.png", "diorite.png"],
    T_POLISHED_DIORITE: ["stone_diorite_smooth.png", "diorite_smooth.png", "polished_diorite.png"],
    T_ANDESITE: ["stone_andesite.png", "andesite.png"],
    T_POLISHED_ANDESITE: ["stone_andesite_smooth.png", "andesite_smooth.png", "polished_andesite.png"],
    T_PRISMARINE: ["prismarine_rough.png", "prismarine.png"],
    T_PRISMARINE_BRICKS: ["prismarine_bricks.png"],
    T_DARK_PRISMARINE: ["prismarine_dark.png", "dark_prismarine.png"],
    T_SEA_LANTERN: ["sea_lantern.png"],
    T_RED_SAND: ["red_sand.png"],
    T_RED_SANDSTONE_SIDE: ["red_sandstone_normal.png", "red_sandstone_side.png", "red_sandstone.png"],
    T_RED_SANDSTONE_TOP: ["red_sandstone_top.png"],
    T_RED_SANDSTONE_BOTTOM: ["red_sandstone_bottom.png"],
    T_CHISELED_RED_SANDSTONE: ["red_sandstone_carved.png", "chiseled_red_sandstone.png"],
    T_SMOOTH_RED_SANDSTONE: ["red_sandstone_smooth.png", "smooth_red_sandstone.png"],
    T_COARSE_DIRT: ["coarse_dirt.png"],
    T_PODZOL_TOP: ["dirt_podzol_top.png", "podzol_top.png"],
    T_PODZOL_SIDE: ["dirt_podzol_side.png", "podzol_side.png"],
    T_SPONGE: ["sponge.png"],
    T_WET_SPONGE: ["sponge_wet.png", "wet_sponge.png"],
    T_SPRUCE_PLANKS: ["planks_spruce.png", "spruce_planks.png"],
    T_BIRCH_PLANKS: ["planks_birch.png", "birch_planks.png"],
    T_JUNGLE_PLANKS: ["planks_jungle.png", "jungle_planks.png"],
    T_ACACIA_PLANKS: ["planks_acacia.png", "acacia_planks.png"],
    T_DARK_OAK_PLANKS: ["planks_big_oak.png", "dark_oak_planks.png"],
    T_IRON_TRAPDOOR: ["iron_trapdoor.png"],
    T_CRACK_0: ["destroy_stage_0.png"],
    T_CRACK_1: ["destroy_stage_1.png"],
    T_CRACK_2: ["destroy_stage_2.png"],
    T_CRACK_3: ["destroy_stage_3.png"],
    T_STICK: ["stick.png"],
    T_ARMOR_STAND: ["wooden_armorstand.png", "armor_stand.png"],
    T_WOOD_PICKAXE: ["wooden_pickaxe.png", "wood_pickaxe.png"],
    T_STONE_PICKAXE: ["stone_pickaxe.png"],
    T_IRON_PICKAXE: ["iron_pickaxe.png"],
    T_DIAMOND_PICKAXE: ["diamond_pickaxe.png"],
    T_WOOD_SWORD: ["wooden_sword.png", "wood_sword.png"],
    T_STONE_SWORD: ["stone_sword.png"],
    ITEM_IRON_SWORD_TILE: ["iron_sword.png"],
    T_DIAMOND_SWORD: ["diamond_sword.png"],
    T_RAW_PORK: ["porkchop_raw.png", "raw_porkchop.png"],
    T_COOKED_PORK: ["porkchop_cooked.png", "cooked_porkchop.png"],
    T_RAW_MUTTON: ["mutton_raw.png", "raw_mutton.png"],
    T_COOKED_MUTTON: ["mutton_cooked.png", "cooked_mutton.png"],
    T_RAW_RABBIT: ["rabbit_raw.png", "raw_rabbit.png"],
    T_COOKED_RABBIT: ["rabbit_cooked.png", "cooked_rabbit.png"],
    T_RABBIT_STEW: ["rabbit_stew.png"],
    T_RABBIT_FOOT: ["rabbit_foot.png"],
    T_RABBIT_HIDE: ["rabbit_hide.png"],
    T_PRISMARINE_SHARD: ["prismarine_shard.png"],
    T_PRISMARINE_CRYSTALS: ["prismarine_crystals.png"],
    T_FURNACE_FRONT: ["furnace_front_off.png", "furnace_front.png"],
    T_FURNACE_FRONT_LIT: ["furnace_front_on.png"],
    T_FURNACE_SIDE: ["furnace_side.png"],
    T_FURNACE_TOP: ["furnace_top.png"],
    T_CHEST_FRONT: ["chest_front.png", "chest.png"],
    T_CHEST_SIDE: ["chest_side.png"],
    T_CHEST_TOP: ["chest_top.png"],
    T_DISPENSER_FRONT: ["dispenser_front_horizontal.png", "dispenser_front.png"],
    T_HOPPER_TOP: ["hopper_top.png"],
    T_HOPPER_SIDE: ["hopper_outside.png", "hopper_side.png"],
    T_BREWING_STAND: ["brewing_stand_base.png", "brewing_stand.png"],
    T_ANVIL_TOP: ["anvil_top_damaged_0.png", "anvil_top.png"],
    T_ANVIL_SIDE: ["anvil_base.png", "anvil_side.png"],
    T_ENCHANTING_TABLE_TOP: ["enchanting_table_top.png"],
    T_ENCHANTING_TABLE_SIDE: ["enchanting_table_side.png"],
    T_JUKEBOX_TOP: ["jukebox_top.png"],
    T_JUKEBOX_SIDE: ["jukebox_side.png"],
    T_NOTE_BLOCK: ["noteblock.png", "note_block.png"],
    T_BEACON: ["beacon.png"],
    T_TORCH: ["torch_on.png", "torch.png"],
    T_REDSTONE_TORCH: ["redstone_torch_on.png", "redstone_torch.png"],
    T_TALL_GRASS: ["tallgrass.png", "grass.png", "tall_grass.png"],
    T_FERN: ["fern.png"],
    T_DEAD_BUSH: ["deadbush.png", "dead_bush.png"],
    T_DANDELION: ["flower_dandelion.png", "dandelion.png"],
    T_POPPY: ["flower_rose.png", "flower_poppy.png", "poppy.png"],
    T_BLUE_ORCHID: ["flower_blue_orchid.png", "blue_orchid.png"],
    T_ALLIUM: ["flower_allium.png", "allium.png"],
    T_RED_TULIP: ["flower_tulip_red.png", "red_tulip.png"],
    T_OXEYE_DAISY: ["flower_oxeye_daisy.png", "oxeye_daisy.png"],
    T_SUNFLOWER: ["double_plant_sunflower_front.png", "sunflower.png"],
    T_BROWN_MUSHROOM: ["mushroom_brown.png", "brown_mushroom.png"],
    T_RED_MUSHROOM: ["mushroom_red.png", "red_mushroom.png"],
    T_SUGAR_CANE: ["reeds.png", "sugar_cane.png"],
    T_CACTUS_SIDE: ["cactus_side.png"],
    T_CACTUS_TOP: ["cactus_top.png"],
    T_OAK_SAPLING: ["sapling_oak.png", "oak_sapling.png"],
    T_SPRUCE_SAPLING: ["sapling_spruce.png", "spruce_sapling.png"],
    T_BIRCH_SAPLING: ["sapling_birch.png", "birch_sapling.png"],
    T_LADDER: ["ladder.png"],
    T_VINE: ["vine.png"],
    T_LILY_PAD: ["waterlily.png", "lily_pad.png"],
    T_COBWEB: ["web.png", "cobweb.png"],
    T_WOODEN_DOOR_TOP: ["door_wood_upper.png", "oak_door_top.png"],
    T_WOODEN_DOOR_BOTTOM: ["door_wood_lower.png", "oak_door_bottom.png"],
    T_IRON_DOOR_TOP: ["door_iron_upper.png", "iron_door_top.png"],
    T_IRON_DOOR_BOTTOM: ["door_iron_lower.png", "iron_door_bottom.png"],
    T_WOODEN_TRAPDOOR: ["trapdoor.png", "oak_trapdoor.png"],
    T_REDSTONE_WIRE: ["redstone_dust_cross.png", "redstone_dust_line.png", "redstone_dust.png"],
    T_REDSTONE_REPEATER: ["repeater_off.png"],
    T_REDSTONE_COMPARATOR: ["comparator_off.png"],
    T_REDSTONE_LAMP_OFF: ["redstone_lamp_off.png"],
    T_REDSTONE_LAMP_ON: ["redstone_lamp_on.png"],
    T_LEVER: ["lever.png"],
    T_STONE_BUTTON: ["stone.png"],
    T_RAIL: ["rail_normal.png", "rail.png"],
    T_POWERED_RAIL: ["rail_golden_powered.png", "rail_golden.png", "powered_rail.png"],
    T_PISTON_TOP: ["piston_top_normal.png", "piston_top.png"],
    T_PISTON_SIDE: ["piston_side.png"],
    T_DAYLIGHT_DETECTOR: ["daylight_detector_top.png"],
    T_TNT_SIDE: ["tnt_side.png"],
    T_TNT_TOP: ["tnt_top.png"],
    T_TNT_BOTTOM: ["tnt_bottom.png"],
    T_COAL_BLOCK: ["coal_block.png"],
    T_IRON_BLOCK: ["iron_block.png"],
    T_GOLD_BLOCK: ["gold_block.png"],
    T_DIAMOND_BLOCK: ["diamond_block.png"],
    T_EMERALD_BLOCK: ["emerald_block.png"],
    T_REDSTONE_BLOCK: ["redstone_block.png"],
    T_LAPIS_BLOCK: ["lapis_block.png"],
    T_LAPIS_ORE: ["lapis_ore.png"],
    T_EMERALD_ORE: ["emerald_ore.png"],
    T_NETHER_QUARTZ_ORE: ["quartz_ore.png", "nether_quartz_ore.png"],
    T_REDSTONE_ORE: ["redstone_ore.png"],
    T_QUARTZ_BLOCK_TOP: ["quartz_block_top.png"],
    T_QUARTZ_BLOCK_SIDE: ["quartz_block_side.png"],
    T_QUARTZ_PILLAR_SIDE: ["quartz_block_lines.png", "quartz_pillar.png"],
    T_STONE_BRICKS: ["stonebrick.png", "stone_bricks.png"],
    T_MOSSY_STONE_BRICKS: ["stonebrick_mossy.png", "mossy_stone_bricks.png"],
    T_CRACKED_STONE_BRICKS: ["stonebrick_cracked.png", "cracked_stone_bricks.png"],
    T_CHISELED_STONE_BRICKS: ["stonebrick_carved.png", "chiseled_stone_bricks.png"],
    T_MOSSY_COBBLE: ["cobblestone_mossy.png", "mossy_cobblestone.png"],
    T_NETHERRACK: ["netherrack.png"],
    T_SOUL_SAND: ["soul_sand.png"],
    T_NETHER_BRICKS: ["nether_brick.png", "nether_bricks.png"],
    T_END_STONE: ["end_stone.png"],
    T_CLAY_BLOCK: ["clay.png", "clay_block.png"],
    T_HARDENED_CLAY: ["hardened_clay.png", "terracotta.png"],
    T_HAY_SIDE: ["hay_block_side.png"],
    T_HAY_TOP: ["hay_block_top.png"],
    T_BOOKSHELF: ["bookshelf.png"],
    T_PUMPKIN_SIDE: ["pumpkin_side.png"],
    T_PUMPKIN_TOP: ["pumpkin_top.png"],
    T_PUMPKIN_FRONT: ["pumpkin_face_off.png"],
    T_JACK_O_LANTERN_FRONT: ["pumpkin_face_on.png"],
    T_MELON_SIDE: ["melon_side.png"],
    T_MELON_TOP: ["melon_top.png"],
    T_FARMLAND_TOP: ["farmland_wet.png", "farmland.png"],
    T_WHEAT_STAGE_7: ["wheat_stage_7.png"],
    T_WHITE_WOOL: ["wool_colored_white.png", "white_wool.png"],
    T_RED_WOOL: ["wool_colored_red.png", "red_wool.png"],
    T_BLUE_WOOL: ["wool_colored_blue.png", "blue_wool.png"],
    T_YELLOW_WOOL: ["wool_colored_yellow.png", "yellow_wool.png"],
    T_GREEN_WOOL: ["wool_colored_green.png", "green_wool.png"],
    T_BLACK_WOOL: ["wool_colored_black.png", "black_wool.png"],
    T_IRON_BARS: ["iron_bars.png"],
    T_GLASS_PANE: ["glass_pane_top.png"],
    T_STONE_SLAB_SIDE: ["stone_slab_side.png"],
    T_MYCELIUM_TOP: ["mycelium_top.png"],
    T_COAL_ITEM: ["coal.png"],
    T_IRON_INGOT: ["iron_ingot.png"],
    T_GOLD_INGOT: ["gold_ingot.png"],
    T_DIAMOND_ITEM: ["diamond.png"],
    T_EMERALD_ITEM: ["emerald.png"],
    T_REDSTONE_ITEM: ["redstone_dust.png"],
    T_LAPIS_ITEM: ["dye_powder_blue.png", "lapis_lazuli.png"],
    T_QUARTZ_ITEM: ["quartz.png"],
    T_BREAD: ["bread.png"],
    T_APPLE: ["apple.png"],
    T_GOLDEN_APPLE: ["apple_golden.png"],
    T_CARROT: ["carrot.png"],
    T_POTATO: ["potato.png"],
    T_RAW_BEEF: ["beef_raw.png"],
    T_STEAK: ["beef_cooked.png"],
    T_RAW_CHICKEN: ["chicken_raw.png"],
    T_COOKED_CHICKEN: ["chicken_cooked.png"],
    T_GUNPOWDER: ["gunpowder.png"],
    T_STRING: ["string.png"],
    T_FEATHER: ["feather.png"],
    T_BONE: ["bone.png"],
    T_ARROW: ["arrow.png"],
    T_BOW: ["bow_standby.png", "bow.png"],
    T_SNOWBALL: ["snowball.png"],
    T_SLIMEBALL: ["slimeball.png"],
    T_BLAZE_ROD: ["blaze_rod.png"],
    T_GHAST_TEAR: ["ghast_tear.png"],
    T_NETHER_STAR: ["nether_star.png"],
    T_ENDER_PEARL: ["ender_pearl.png"],
    T_LEATHER: ["leather.png"],
    T_WHEAT_ITEM: ["wheat.png"],
    T_FLINT: ["flint.png"],
    T_BUCKET: ["bucket_empty.png", "bucket.png"],
    T_WATER_BUCKET: ["bucket_water.png"],
    T_LAVA_BUCKET: ["bucket_lava.png"],
    T_MILK_BUCKET: ["bucket_milk.png"],
    T_FLINT_AND_STEEL: ["flint_and_steel.png"],
    T_SHEARS: ["shears.png"],
    T_IRON_HELMET: ["iron_helmet.png"],
    T_IRON_CHESTPLATE: ["iron_chestplate.png"],
    T_IRON_LEGGINGS: ["iron_leggings.png"],
    T_IRON_BOOTS: ["iron_boots.png"],
    T_DIAMOND_HELMET: ["diamond_helmet.png"],
    T_DIAMOND_CHESTPLATE: ["diamond_chestplate.png"],
    T_DIAMOND_LEGGINGS: ["diamond_leggings.png"],
    T_DIAMOND_BOOTS: ["diamond_boots.png"],
    T_BED_ITEM: ["bed.png"],
    T_DRAGON_EGG: ["dragon_egg.png"],
}


@dataclass
class ResourcePackInfo:
    """Metadata describing a resource pack."""
    pack_id: str
    name: str
    description: str
    pack_format: int
    is_builtin: bool
    path: Optional[str] = None


class TexturePackManager:
    """Discovers, parses, and activates resource packs."""

    def __init__(self, packs_dir: str):
        self.packs_dir = packs_dir
        os.makedirs(self.packs_dir, exist_ok=True)
        self.active_pack_id = "default"
        self._ensure_sample_pack()

    def _ensure_sample_pack(self):
        """Creates a sample resource pack structure if folder is empty."""
        sample_dir = os.path.join(self.packs_dir, "sample_pack")
        if not os.path.exists(sample_dir):
            try:
                os.makedirs(sample_dir, exist_ok=True)
                mcmeta = {
                    "pack": {
                        "pack_format": 1,
                        "description": "Example PyCraft Resource Pack"
                    }
                }
                with open(os.path.join(sample_dir, "pack.mcmeta"), "w", encoding="utf-8") as f:
                    json.dump(mcmeta, f, indent=2)
            except OSError:
                pass

    def list_packs(self) -> List[ResourcePackInfo]:
        """Return all available packs (built-in + scanned in resourcepacks/)."""
        packs = [
            ResourcePackInfo(
                pack_id="default",
                name="Default (PyCraft 1.8)",
                description="Iconic standard Minecraft 1.8 procedural pixel art.",
                pack_format=1,
                is_builtin=True,
            ),
            ResourcePackInfo(
                pack_id="faithful",
                name="Faithful 16x",
                description="Sharper contrast, well-defined brick joints and vivid ores.",
                pack_format=1,
                is_builtin=True,
            ),
            ResourcePackInfo(
                pack_id="retro",
                name="Retro Classic (Alpha)",
                description="Nostalgic vibrant alpha green terrain and saturated colors.",
                pack_format=1,
                is_builtin=True,
            ),
            ResourcePackInfo(
                pack_id="dark_mode",
                name="Dark Mode / Obsidian",
                description="Sleek dark stone, deep obsidian hues, and low-contrast stone.",
                pack_format=1,
                is_builtin=True,
            ),
        ]

        # Scan resourcepacks directory
        if os.path.exists(self.packs_dir):
            for entry in sorted(os.listdir(self.packs_dir)):
                full_path = os.path.join(self.packs_dir, entry)
                pack_info = self._inspect_pack(full_path, entry)
                if pack_info:
                    packs.append(pack_info)

        return packs

    def _inspect_pack(self, path: str, filename: str) -> Optional[ResourcePackInfo]:
        """Inspect a file or directory to determine if it is a valid resource pack."""
        if os.path.isdir(path):
            mcmeta_path = os.path.join(path, "pack.mcmeta")
            desc = "Custom User Resource Pack"
            p_format = 1
            pack_name = filename.replace("_", " ").title()
            if os.path.exists(mcmeta_path):
                try:
                    with open(mcmeta_path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    p_info = data.get("pack", {})
                    d_val = p_info.get("description", desc)
                    if isinstance(d_val, dict):
                        d_val = d_val.get("text", desc)
                    desc = str(d_val)
                    p_format = p_info.get("pack_format", 1)
                except Exception:
                    pass
            return ResourcePackInfo(
                pack_id=f"dir_{filename}",
                name=pack_name,
                description=desc,
                pack_format=p_format,
                is_builtin=False,
                path=path,
            )

        if zipfile.is_zipfile(path):
            pack_id = f"zip_{os.path.splitext(filename)[0]}"
            pack_name = os.path.splitext(filename)[0].replace("_", " ").title()
            desc = "Zipped Resource Pack"
            p_format = 1
            try:
                with zipfile.ZipFile(path, "r") as zf:
                    for name in zf.namelist():
                        if os.path.basename(name).lower() == "pack.mcmeta":
                            meta_bytes = zf.read(name)
                            data = json.loads(meta_bytes.decode("utf-8"))
                            p_info = data.get("pack", {})
                            d_val = p_info.get("description", desc)
                            if isinstance(d_val, dict):
                                d_val = d_val.get("text", desc)
                            desc = str(d_val)
                            p_format = p_info.get("pack_format", 1)
                            break
            except Exception:
                pass
            return ResourcePackInfo(
                pack_id=pack_id,
                name=pack_name,
                description=desc,
                pack_format=p_format,
                is_builtin=False,
                path=path,
            )

        return None

    def build_pack_atlas(self, pack_id: str) -> np.ndarray:
        """Construct the 256x256 RGBA atlas array for the specified pack."""
        if pack_id == "faithful":
            base = build_atlas(seed=1337).astype(np.float32)
            mean = 128.0
            enhanced = (base[..., :3] - mean) * 1.25 + mean
            base[..., :3] = np.clip(enhanced, 0, 255)
            return base.astype(np.uint8)

        elif pack_id == "retro":
            base = build_atlas(seed=42).astype(np.float32)
            base[:32, :32, 1] = np.clip(base[:32, :32, 1] * 1.35, 0, 255)
            base[..., 0] = np.clip(base[..., 0] * 1.05, 0, 255)
            return base.astype(np.uint8)

        elif pack_id == "dark_mode":
            base = build_atlas(seed=777).astype(np.float32)
            base[..., :3] = np.clip(base[..., :3] * 0.72, 0, 255)
            return base.astype(np.uint8)

        # Check custom directory / zip packs
        for pack in self.list_packs():
            if pack.pack_id == pack_id and pack.path:
                custom_atlas = self._load_custom_atlas(pack.path)
                if custom_atlas is not None:
                    return custom_atlas

        # Default fallback
        return build_atlas(seed=7)

    def _load_custom_atlas(self, path: str) -> Optional[np.ndarray]:
        """Extract and compile textures from a custom resource pack directory or .zip archive."""
        try:
            from PIL import Image
        except ImportError:
            Image = None

        if Image is None:
            return None

        # Start with default procedural pixel art as baseline
        atlas = build_atlas(seed=7).copy()
        target_tile_size = (16, 16)
        matched_textures = 0

        # Build index of texture files in pack
        file_map: Dict[str, Tuple[str, Optional[zipfile.ZipFile]]] = {}

        if os.path.isdir(path):
            # Check for direct atlas image first
            for candidate in ["textures/atlas.png", "textures/terrain.png", "terrain.png"]:
                c_path = os.path.join(path, candidate)
                if os.path.exists(c_path):
                    try:
                        im = Image.open(c_path).convert("RGBA")
                        if im.size != (256, 256):
                            im = im.resize((256, 256), Image.NEAREST)
                        return np.array(im, dtype=np.uint8)
                    except Exception:
                        pass

            for root, _, files in os.walk(path):
                for f in files:
                    if f.lower().endswith(".png"):
                        base = f.lower()
                        full = os.path.join(root, f)
                        # Prefer blocks/ directory if there are duplicates
                        if base not in file_map or "textures/block" in root.lower():
                            file_map[base] = (full, None)

        elif zipfile.is_zipfile(path):
            try:
                zf = zipfile.ZipFile(path, "r")
                # Check for direct atlas image first
                for candidate in ["textures/atlas.png", "textures/terrain.png", "terrain.png"]:
                    if candidate in zf.namelist():
                        try:
                            with zf.open(candidate) as f:
                                im = Image.open(f).convert("RGBA")
                                if im.size != (256, 256):
                                    im = im.resize((256, 256), Image.NEAREST)
                                return np.array(im, dtype=np.uint8)
                        except Exception:
                            pass

                for name in zf.namelist():
                    if name.lower().endswith(".png") and not name.endswith("/"):
                        base = os.path.basename(name).lower()
                        if base not in file_map or "textures/block" in name.lower():
                            file_map[base] = (name, zf)
            except Exception:
                return None
        else:
            return None

        # Compile individual block and item textures into the atlas
        for tile_id, candidates in MINECRAFT_TILE_MAP.items():
            for cand in candidates:
                cand_lower = cand.lower()
                if cand_lower in file_map:
                    filepath_or_name, zf = file_map[cand_lower]
                    try:
                        if zf is not None:
                            with zf.open(filepath_or_name) as f:
                                im = Image.open(f).convert("RGBA")
                        else:
                            im = Image.open(filepath_or_name).convert("RGBA")

                        # If texture is an animated strip (height > width, e.g. water_still.png), crop the top square frame
                        if im.height > im.width:
                            im = im.crop((0, 0, im.width, im.width))

                        if im.size != target_tile_size:
                            im = im.resize(target_tile_size, Image.NEAREST)

                        img_arr = np.array(im, dtype=np.uint8)

                        # Minecraft biome-tinted textures (grayscale masks that need color multipliers)
                        biome_tints = {
                            T_GRASS_TOP: (95, 159, 53),
                            T_LEAVES: (65, 150, 45),
                            T_TALL_GRASS: (95, 159, 53),
                            T_FERN: (95, 159, 53),
                            T_VINE: (65, 150, 45),
                            T_LILY_PAD: (50, 130, 40),
                        }
                        if tile_id in biome_tints:
                            rgb = img_arr[..., :3].astype(float)
                            max_diff = np.max(np.abs(rgb[..., 0] - rgb[..., 1])) + np.max(np.abs(rgb[..., 1] - rgb[..., 2]))
                            if max_diff < 15.0:
                                tint = np.array(biome_tints[tile_id], dtype=float) / 128.0
                                img_arr[..., :3] = np.clip(rgb * tint, 0, 255).astype(np.uint8)

                        # For grass side, if grass_side_overlay.png exists, composite it on top
                        if tile_id == T_GRASS_SIDE and "grass_side_overlay.png" in file_map:
                            try:
                                ov_path, ov_zf = file_map["grass_side_overlay.png"]
                                if ov_zf is not None:
                                    with ov_zf.open(ov_path) as ov_f:
                                        ov_im = Image.open(ov_f).convert("RGBA")
                                else:
                                    ov_im = Image.open(ov_path).convert("RGBA")
                                if ov_im.size != target_tile_size:
                                    ov_im = ov_im.resize(target_tile_size, Image.NEAREST)
                                ov_arr = np.array(ov_im, dtype=np.uint8)
                                ov_rgb = ov_arr[..., :3].astype(float)
                                ov_diff = np.max(np.abs(ov_rgb[..., 0] - ov_rgb[..., 1])) + np.max(np.abs(ov_rgb[..., 1] - ov_rgb[..., 2]))
                                if ov_diff < 15.0:
                                    tint = np.array(biome_tints[T_GRASS_TOP], dtype=float) / 128.0
                                    ov_arr[..., :3] = np.clip(ov_rgb * tint, 0, 255).astype(np.uint8)
                                alpha_mask = ov_arr[..., 3] > 64
                                img_arr[alpha_mask] = ov_arr[alpha_mask]
                            except Exception:
                                pass

                        tx = (tile_id % 16) * 16
                        ty = (tile_id // 16) * 16
                        atlas[ty : ty + 16, tx : tx + 16] = img_arr
                        matched_textures += 1
                        break
                    except Exception:
                        continue

        # Check for chest entity texture extraction (normal.png) if chest blocks weren't directly provided
        if "normal.png" in file_map and ("chest_front.png" not in file_map):
            try:
                ch_path, ch_zf = file_map["normal.png"]
                if ch_zf is not None:
                    with ch_zf.open(ch_path) as ch_f:
                        ch_im = Image.open(ch_f).convert("RGBA")
                else:
                    ch_im = Image.open(ch_path).convert("RGBA")
                sc = max(1, ch_im.width // 64)
                # Front: Lid front (14x5) + Base front (14x10) + Latch (2x4)
                ch_front = Image.new("RGBA", (16, 16), (0, 0, 0, 0))
                lid_f = ch_im.crop((14 * sc, 14 * sc, 28 * sc, 19 * sc)).resize((14, 5), Image.NEAREST)
                base_f = ch_im.crop((14 * sc, 33 * sc, 28 * sc, 43 * sc)).resize((14, 10), Image.NEAREST)
                latch = ch_im.crop((1 * sc, 1 * sc, 3 * sc, 5 * sc)).resize((2, 4), Image.NEAREST)
                ch_front.paste(lid_f, (1, 1))
                ch_front.paste(base_f, (1, 6))
                ch_front.paste(latch, (7, 4), latch)

                # Side: Lid side (14x5) + Base side (14x10)
                ch_side = Image.new("RGBA", (16, 16), (0, 0, 0, 0))
                lid_s = ch_im.crop((0, 14 * sc, 14 * sc, 19 * sc)).resize((14, 5), Image.NEAREST)
                base_s = ch_im.crop((0, 33 * sc, 14 * sc, 43 * sc)).resize((14, 10), Image.NEAREST)
                ch_side.paste(lid_s, (1, 1))
                ch_side.paste(base_s, (1, 6))

                # Top: Lid top (14x14)
                ch_top = ch_im.crop((14 * sc, 0, 28 * sc, 14 * sc)).resize((16, 16), Image.NEAREST)

                for t_id, im_face in [(T_CHEST_FRONT, ch_front), (T_CHEST_SIDE, ch_side), (T_CHEST_TOP, ch_top)]:
                    tx = (t_id % 16) * 16
                    ty = (t_id // 16) * 16
                    atlas[ty : ty + 16, tx : tx + 16] = np.array(im_face, dtype=np.uint8)
                    matched_textures += 1
            except Exception:
                pass

        if matched_textures > 0:
            return atlas

        return None
