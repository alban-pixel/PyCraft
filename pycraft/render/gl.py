"""Small helpers for OpenGL: the camera's matrices, the view's planes and the test of boxes against
them, and setting a program's uniforms."""

import math

import numpy as np


def perspective(fov, aspect, near, far):
    f = 1 / math.tan(math.radians(fov) / 2)
    return np.array([
        [f / aspect, 0, 0, 0],
        [0, f, 0, 0],
        [0, 0, (far + near) / (near - far), 2 * far * near / (near - far)],
        [0, 0, -1, 0],
    ], dtype="f4")
def depth_half(vp, far_half):
    """vp with its depths squeezed into the nearer or the farther half of the depth buffer. The
    blocks are drawn into the nearer half and the distant terrain into the farther one, each with
    the projection that suits it: whatever their real depths, a block is in front of the distant
    terrain, which is not even shaded where a block hides it."""
    m = np.array(vp, dtype="f4")
    m[2] = 0.5 * m[2] + (0.5 if far_half else -0.5) * m[3]
    return m
def look_at(eye, forward):
    eye = np.array(eye, dtype="f4")
    fw = np.array(forward, dtype="f4")
    fw /= np.linalg.norm(fw)
    right = np.cross(fw, [0, 1, 0])
    right /= np.linalg.norm(right)
    up = np.cross(right, fw)
    m = np.identity(4, dtype="f4")
    m[0, :3], m[1, :3], m[2, :3] = right, up, -fw
    m[:3, 3] = -m[:3, :3] @ eye
    return m
def frustum_planes(vp):
    """The 6 planes (a, b, c, d) of the view: a point p is inside when a*x + b*y + c*z + d >= 0 for all."""
    m = vp.astype(np.float64)
    return np.array([m[3] + m[0], m[3] - m[0], m[3] + m[1], m[3] - m[1], m[3] + m[2], m[3] - m[2]])
def boxes_visible(planes, lo, hi):
    """For boxes lo..hi (arrays (n, 3)), True for those that touch the view."""
    visible = np.ones(len(lo), dtype=bool)
    for a, b, c, d in planes:
        # The corner of each box farthest along the plane's normal
        px = np.where(a > 0, hi[:, 0], lo[:, 0])
        py = np.where(b > 0, hi[:, 1], lo[:, 1])
        pz = np.where(c > 0, hi[:, 2], lo[:, 2])
        visible &= a * px + b * py + c * pz + d >= 0
    return visible
def matrix_bytes(m):
    """A matrix in the column-major layout OpenGL expects."""
    return np.ascontiguousarray(np.asarray(m, dtype="f4").T).tobytes()
def set_uniforms(program, values):
    """Set the uniforms a program has among values (the others are skipped)."""
    for name, value in values.items():
        uniform = program.get(name, None)
        if uniform is None:
            continue
        if isinstance(value, np.ndarray):
            uniform.write(matrix_bytes(value))
        else:
            uniform.value = value
def jittered(proj, dx, dy, width, height):
    """A copy of a projection whose picture moves by (dx, dy) pixels (right and up): the screenshot
    averages frames moved by fractions of a pixel, which smooths every edge and texture."""
    m = np.array(proj, dtype="f4")
    m[0] += (2.0 * dx / width) * m[3]  # (in clip space: x / w moves by that much)
    m[1] += (2.0 * dy / height) * m[3]
    return m
