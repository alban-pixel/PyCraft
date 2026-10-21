#version 330

in vec3 in_pos;
in vec3 in_normal;
in float in_color;
in float in_ao;

uniform mat4 u_mvp;
uniform float u_time;

out vec3 v_world;
out vec3 v_normal;
out float v_ao;

void main() {
    vec3 p = in_pos;
    p.z += sin(u_time * 1.7 + in_pos.x * 0.8 + in_pos.y * 0.6) * 0.07;
    v_world = p;
    v_normal = normalize(in_normal + vec3(
        cos(u_time * 1.3 + in_pos.x * 0.9) * 0.12,
        cos(u_time * 1.1 + in_pos.y * 0.9) * 0.12,
        0.0));
    v_ao = in_ao;
    gl_Position = u_mvp * vec4(p, 1.0);
}
