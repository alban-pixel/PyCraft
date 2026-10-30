"""384m chunk column and 24 sub-chunks with dynamic local palette compression and zlib serialization.

Implements the deterministic voxel architecture:
- Canonical height range: Y in [-64, 320] (total height = 384 blocks).
- 24 sub-chunks of 16x16x16 voxels per column (cy in [-4, 19]).
- Local dynamic indexed palette mapping to immutable BlockState objects.
- Homogeneous sub-chunk memory optimization (< 2 KB per homogeneous sub-chunk).
- Fast binary zlib serialization for world persistence.
"""
from dataclasses import dataclass
import io
import struct
from typing import Dict, List, Optional, Tuple, Union
import zlib

import numpy as np

from blocks import AIR

CHUNK_SIZE = 16  # 16x16x16 voxels per sub-chunk
SUBCHUNK_VOXELS = CHUNK_SIZE * CHUNK_SIZE * CHUNK_SIZE  # 4096 voxels
Y_MIN = -64
Y_MAX = 320
TOTAL_HEIGHT = Y_MAX - Y_MIN  # 384 blocks
NUM_SUBCHUNKS = TOTAL_HEIGHT // CHUNK_SIZE  # 24 sub-chunks
MIN_CY = Y_MIN // CHUNK_SIZE  # -4
MAX_CY = (Y_MAX // CHUNK_SIZE) - 1  # 19

# Extended vertical chunk height constants for 512m worlds (Milestone M3)
CHUNK_Y_MIN = -64
CHUNK_Y_MAX = 512
CHUNK_SUBCHUNKS = 36  # (512 - (-64)) // 16 = 36
DEFAULT_SUBCHUNKS = 24


def serialize_subchunk(subchunk: "SubChunk") -> bytes:
    """Serialize a single SubChunk into compressed binary data."""
    return subchunk.serialize()



@dataclass(frozen=True, slots=True)
class BlockState:
    """Immutable representation of a voxel state."""
    id: int
    properties: Tuple[Tuple[str, Union[str, int, bool]], ...] = ()

    @classmethod
    def create(cls, block_id: int, **props) -> "BlockState":
        sorted_props = tuple(sorted(props.items()))
        return cls(id=int(block_id), properties=sorted_props)


AIR_STATE = BlockState.create(AIR)


class SubChunk:
    """A 16x16x16 cubic volume of voxels managed via an indexed local palette."""

    __slots__ = ("cy", "palette", "indices", "_homogeneous")

    def __init__(self, cy: int, initial_state: BlockState = AIR_STATE):
        self.cy = int(cy)
        self.palette: List[BlockState] = [initial_state]
        self._homogeneous: bool = True
        # For homogeneous sub-chunks, data is allocated lazily as an all-zero uint8 array
        self.indices: np.ndarray = np.zeros((CHUNK_SIZE, CHUNK_SIZE, CHUNK_SIZE), dtype=np.uint8)

    @property
    def is_homogeneous(self) -> bool:
        return self._homogeneous

    def get(self, lx: int, ly: int, lz: int) -> BlockState:
        """Get BlockState at local coordinates (0..15, 0..15, 0..15)."""
        idx = int(self.indices[lx, ly, lz])
        return self.palette[idx]

    def set(self, lx: int, ly: int, lz: int, state: BlockState) -> None:
        """Set BlockState at local coordinates, updating palette dynamically."""
        current_idx = int(self.indices[lx, ly, lz])
        if self.palette[current_idx] == state:
            return

        # Find or insert state into palette
        try:
            new_idx = self.palette.index(state)
        except ValueError:
            new_idx = len(self.palette)
            self.palette.append(state)
            if new_idx > 255 and self.indices.dtype != np.uint16:
                self.indices = self.indices.astype(np.uint16)

        self.indices[lx, ly, lz] = new_idx
        self._homogeneous = (len(self.palette) == 1)

    def fill(self, state: BlockState) -> None:
        """Fill the entire sub-chunk homogeneously with one BlockState."""
        self.palette = [state]
        self.indices.fill(0)
        self._homogeneous = True

    def serialize(self) -> bytes:
        """Serialize sub-chunk to compressed binary format."""
        buf = io.BytesIO()
        # Header: cy (signed byte), homogeneous flag (uint8), palette length (uint16)
        palette_len = len(self.palette)
        buf.write(struct.pack("<bBH", self.cy, 1 if self._homogeneous else 0, palette_len))

        # Write palette
        for st in self.palette:
            buf.write(struct.pack("<H", st.id))

        # If homogeneous, indices array is omitted (saving space)
        if not self._homogeneous:
            raw_bytes = self.indices.tobytes()
            buf.write(raw_bytes)

        return zlib.compress(buf.getvalue(), level=6)

    @classmethod
    def deserialize(cls, compressed_data: bytes) -> "SubChunk":
        """Deserialize sub-chunk from compressed binary format."""
        raw = zlib.decompress(compressed_data)
        buf = io.BytesIO(raw)

        cy, hom_flag, palette_len = struct.unpack("<bBH", buf.read(4))
        palette: List[BlockState] = []
        for _ in range(palette_len):
            (block_id,) = struct.unpack("<H", buf.read(2))
            palette.append(BlockState.create(block_id))

        sub = cls(cy, palette[0] if palette else AIR_STATE)
        sub.palette = palette
        sub._homogeneous = bool(hom_flag)

        if not sub._homogeneous:
            dtype = np.uint16 if palette_len > 256 else np.uint8
            item_size = np.dtype(dtype).itemsize
            expected_bytes = SUBCHUNK_VOXELS * item_size
            data_bytes = buf.read(expected_bytes)
            sub.indices = np.frombuffer(data_bytes, dtype=dtype).reshape(
                (CHUNK_SIZE, CHUNK_SIZE, CHUNK_SIZE)
            ).copy()
        else:
            sub.indices.fill(0)

        return sub


class ChunkColumn:
    """A vertical column of 16x384x16 voxels partitioned into 24 SubChunks."""

    __slots__ = ("cx", "cz", "subchunks")

    def __init__(self, cx: int, cz: int):
        self.cx = int(cx)
        self.cz = int(cz)
        # 24 subchunks from cy = -4 to 19
        self.subchunks: Dict[int, SubChunk] = {
            cy: SubChunk(cy) for cy in range(MIN_CY, MAX_CY + 1)
        }

    def _get_subchunk(self, y: int) -> Tuple[SubChunk, int]:
        if y < Y_MIN or y >= Y_MAX:
            raise IndexError(f"Y coordinate {y} out of bounds [{Y_MIN}, {Y_MAX})")
        cy = (y - Y_MIN) // CHUNK_SIZE + MIN_CY
        ly = (y - Y_MIN) % CHUNK_SIZE
        return self.subchunks[cy], ly

    def get_block(self, lx: int, y: int, lz: int) -> int:
        """Get block ID at local column coordinates lx (0..15), y (-64..319), lz (0..15)."""
        sub, ly = self._get_subchunk(y)
        return sub.get(lx, ly, lz).id

    def set_block(self, lx: int, y: int, lz: int, block_id: int) -> None:
        """Set block ID at local column coordinates."""
        sub, ly = self._get_subchunk(y)
        sub.set(lx, ly, lz, BlockState.create(block_id))

    def serialize(self) -> bytes:
        """Serialize the full 384m column with all 24 sub-chunks."""
        buf = io.BytesIO()
        buf.write(struct.pack("<iiH", self.cx, self.cz, NUM_SUBCHUNKS))
        for cy in range(MIN_CY, MAX_CY + 1):
            sub_bytes = self.subchunks[cy].serialize()
            buf.write(struct.pack("<I", len(sub_bytes)))
            buf.write(sub_bytes)
        return zlib.compress(buf.getvalue(), level=6)

    @classmethod
    def deserialize(cls, compressed_data: bytes) -> "ChunkColumn":
        """Deserialize a ChunkColumn from compressed binary data."""
        raw = zlib.decompress(compressed_data)
        buf = io.BytesIO(raw)
        cx, cz, count = struct.unpack("<iiH", buf.read(10))
        column = cls(cx, cz)
        for _ in range(count):
            (sub_len,) = struct.unpack("<I", buf.read(4))
            sub_data = buf.read(sub_len)
            sub = SubChunk.deserialize(sub_data)
            column.subchunks[sub.cy] = sub
        return column
