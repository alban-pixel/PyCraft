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
uniform sampler2D u_shadow;
uniform mat4 u_light_mvp;
uniform float u_shadow_on;

out vec4 frag_color;

float hash12(vec2 p) {
    return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453);
}

vec2 uv_texture(vec3 n, vec3 p) {
    vec3 a = abs(n);
    if (a.z > 0.5) return p.xy;
    if (a.x > 0.5) return p.yz;
    return p.xz;
}

float facteur_ombre(vec3 world) {
    if (u_shadow_on < 0.5) {
        return 1.0;
    }
    vec4 clip = u_light_mvp * vec4(world, 1.0);
    vec3 ndc = clip.xyz / clip.w;
    if (ndc.x < -1.0 || ndc.x > 1.0 || ndc.y < -1.0 || ndc.y > 1.0 || ndc.z > 1.0) {
        return 1.0;
    }
    vec2 uv = ndc.xy * 0.5 + 0.5;
    float z = ndc.z * 0.5 + 0.5;
    float biais = 0.0022;
    vec2 texel = vec2(1.0 / 2048.0);
    float eclaire = 0.0;
    for (int dx = -1; dx <= 1; dx++) {
        for (int dy = -1; dy <= 1; dy++) {
            float d = texture(u_shadow, uv + vec2(float(dx), float(dy)) * texel).r;
            eclaire += step(z - biais, d);
        }
    }
    return eclaire / 9.0;
}

void main() {
    vec3 base = u_colors[int(v_color + 0.5)];
    vec3 n = normalize(v_normal);
    // Texture procédurale : moucheture 8×8 par bloc, stable dans le monde.
    vec2 tu = floor(uv_texture(n, v_world) * 8.0);
    float grain = hash12(tu);
    base *= 0.86 + 0.26 * grain;
    float diffuse = max(dot(n, u_sun), 0.0);
    float ciel = 0.5 + 0.5 * n.z;          // éclairage d'ambiance hémisphérique
    float light = 0.30 + 0.40 * diffuse + 0.36 * ciel;
    float ombre = facteur_ombre(v_world);
    vec3 color = base * light * v_ao * mix(0.45, 1.0, ombre);

    float dist = distance(v_world, u_camera);
    float fog = clamp((dist - u_fog_start) / (u_fog_end - u_fog_start), 0.0, 1.0);
    color = mix(color, u_sky, fog * 0.85);

    frag_color = vec4(color, 1.0);
}
