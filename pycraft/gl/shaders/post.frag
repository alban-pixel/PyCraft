#version 330

in vec2 v_uv;
uniform sampler2D u_scene;
uniform sampler2D u_lut;
uniform vec3 u_tint;
uniform float u_vignette;
uniform float u_rain;
uniform float u_time;
uniform float u_dither;

// Matrice de Bayer récursive (bruit ordonné) : casse les bandes du dégradé
// sans introduire de bruit haute fréquence.
float bayer2(vec2 a) {
    a = floor(a);
    return fract(a.x / 2.0 + a.y * a.y * 0.75);
}

#define bayer4(a) (bayer2(0.5 * (a)) * 0.25 + bayer2(a))
#define bayer8(a) (bayer4(0.5 * (a)) * 0.25 + bayer2(a))

float hash_pluie(vec2 p) {
    return fract(sin(dot(p, vec2(41.7, 289.3))) * 43758.5453);
}
out vec4 frag_color;

void main() {
    vec3 color = clamp(texture(u_scene, v_uv).rgb, 0.0, 1.0);
    vec2 d = v_uv - 0.5;
    float vignette = 1.0 - u_vignette * dot(d, d) * 1.8;
    color *= u_tint * vignette;

    if (u_rain > 0.01) {
        vec2 p = v_uv * vec2(120.0, 320.0);
        p.y -= u_time * 60.0;
        float goutte = step(0.955, hash_pluie(floor(p * vec2(1.0, 0.5)) + floor(u_time * 4.0)));
        color = mix(color, vec3(0.72, 0.80, 0.90), goutte * u_rain * 0.6);
    }

    // Un demi-pas de quantification (LUT 5 bits) suffit à casser les bandes.
    float grain = (bayer8(gl_FragCoord.xy) - 0.5) * u_dither / 16.0;
    color += vec3(grain);

    int r = min(int(clamp(color.r, 0.0, 1.0) * 31.999), 31);
    int g = min(int(clamp(color.g, 0.0, 1.0) * 31.999), 31);
    int b = min(int(clamp(color.b, 0.0, 1.0) * 31.999), 31);
    vec2 texel = vec2((float(r + 32 * g) + 0.5) / 1024.0, (float(b) + 0.5) / 32.0);
    float index = texture(u_lut, texel).r;
    frag_color = vec4(index, 0.0, 0.0, 1.0);
}
