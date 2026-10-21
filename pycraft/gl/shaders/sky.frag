#version 330

in vec2 v_uv;

uniform vec3 u_right;
uniform vec3 u_up;
uniform vec3 u_fwd;
uniform vec2 u_res;
uniform float u_focal;
uniform vec3 u_sun;
uniform vec3 u_horizon;
uniform vec3 u_zenith;
uniform float u_time;
uniform float u_night;

out vec4 frag_color;

float hash21(vec2 p) {
    return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453);
}

float value_noise(vec2 p) {
    vec2 i = floor(p);
    vec2 f = fract(p);
    f = f * f * (3.0 - 2.0 * f);
    float a = hash21(i);
    float b = hash21(i + vec2(1.0, 0.0));
    float c = hash21(i + vec2(0.0, 1.0));
    float d = hash21(i + vec2(1.0, 1.0));
    return mix(mix(a, b, f.x), mix(c, d, f.x), f.y);
}

float hash31(vec3 p) {
    return fract(sin(dot(p, vec3(12.9898, 78.233, 45.164))) * 43758.5453);
}

void main() {
    vec2 ndc = v_uv * 2.0 - 1.0;
    vec3 dir = normalize(
        u_fwd
        + u_right * (ndc.x * u_res.x * 0.5 / u_focal)
        + u_up * (ndc.y * u_res.y * 0.5 / u_focal)
    );

    float t = clamp(dir.z * 1.5, 0.0, 1.0);
    vec3 col = mix(u_horizon, u_zenith, pow(t, 0.65));

    // Soleil : disque + halo
    float s = max(dot(dir, u_sun), 0.0);
    col += vec3(1.0, 0.86, 0.55) * pow(s, 400.0) * 2.0;
    col += vec3(1.0, 0.80, 0.50) * pow(s, 10.0) * 0.28;

    // Étoiles la nuit
    if (u_night > 0.01) {
        float h = hash31(floor(dir * 220.0));
        float star = step(0.9982, h) * smoothstep(0.02, 0.35, dir.z);
        col += vec3(star * u_night);
    }

    // Nuages : deux octaves de bruit, projetés sur un plan
    if (dir.z > 0.02) {
        vec2 p = dir.xy / max(dir.z, 0.15) * 0.55 + u_time * 0.008;
        float n = value_noise(p) * 0.65 + value_noise(p * 2.7) * 0.35;
        float cloud = smoothstep(0.56, 0.78, n) * smoothstep(0.02, 0.25, dir.z);
        col = mix(col, vec3(0.93, 0.94, 0.97), cloud * 0.55);
    }

    frag_color = vec4(col, 1.0);
}
