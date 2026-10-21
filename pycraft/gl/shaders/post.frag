#version 330

in vec2 v_uv;
uniform sampler2D u_scene;
uniform sampler2D u_lut;
uniform vec3 u_tint;
uniform float u_vignette;
out vec4 frag_color;

void main() {
    vec3 color = clamp(texture(u_scene, v_uv).rgb, 0.0, 1.0);
    vec2 d = v_uv - 0.5;
    float vignette = 1.0 - u_vignette * dot(d, d) * 1.8;
    color *= u_tint * vignette;

    int r = min(int(clamp(color.r, 0.0, 1.0) * 31.999), 31);
    int g = min(int(clamp(color.g, 0.0, 1.0) * 31.999), 31);
    int b = min(int(clamp(color.b, 0.0, 1.0) * 31.999), 31);
    vec2 texel = vec2((float(r + 32 * g) + 0.5) / 1024.0, (float(b) + 0.5) / 32.0);
    float index = texture(u_lut, texel).r;
    frag_color = vec4(index, 0.0, 0.0, 1.0);
}
