#version 330

in vec3 in_pos;
in vec3 in_normal;
in float in_color;
in float in_ao;

uniform mat4 u_mvp;

out vec3 v_normal;
out vec3 v_world;
out float v_color;
out float v_ao;

void main() {
    v_world = in_pos;
    v_normal = in_normal;
    v_color = in_color;
    v_ao = in_ao;
    gl_Position = u_mvp * vec4(in_pos, 1.0);
}
