#version 330

in vec3 v_normal;
in vec3 v_world;
in float v_color;
in float v_ao;

uniform vec3 u_colors[16];
uniform vec3 u_sun;
uniform vec3 u_camera;
uniform vec3 u_sky;
uniform float u_fog_start;
uniform float u_fog_end;

out vec4 frag_color;

void main() {
    vec3 base = u_colors[int(v_color + 0.5)];
    vec3 n = normalize(v_normal);
    float diffuse = max(dot(n, u_sun), 0.0);
    float light = 0.38 + 0.62 * diffuse;
    vec3 color = base * light * v_ao;

    float dist = distance(v_world, u_camera);
    float fog = clamp((dist - u_fog_start) / (u_fog_end - u_fog_start), 0.0, 1.0);
    color = mix(color, u_sky, fog * 0.85);

    frag_color = vec4(color, 1.0);
}
