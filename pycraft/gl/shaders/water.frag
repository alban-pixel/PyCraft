#version 330

in vec3 v_world;
in vec3 v_normal;
in float v_ao;

uniform vec3 u_camera;
uniform vec3 u_water;
uniform vec3 u_sky;
uniform vec3 u_sun;
uniform float u_time;

out vec4 frag_color;

float bayer4(vec2 p) {
    int x = int(mod(p.x, 4.0));
    int y = int(mod(p.y, 4.0));
    const float m[16] = float[16](
        0.0, 8.0, 2.0, 10.0,
        12.0, 4.0, 14.0, 6.0,
        3.0, 11.0, 1.0, 9.0,
        15.0, 7.0, 13.0, 5.0
    );
    return (m[y * 4 + x] + 0.5) / 16.0;
}

void main() {
    vec3 vue = normalize(u_camera - v_world);
    // Vagues : deux sinusoïdes croisées donnent la pente de la surface.
    float phase = u_time * 1.7;
    float pente_x = 0.09 * cos(v_world.x * 3.7 + phase)
                  + 0.05 * cos((v_world.x + v_world.y) * 6.1 - phase * 1.3);
    float pente_y = 0.09 * cos(v_world.y * 4.3 - phase * 1.1)
                  + 0.05 * cos((v_world.x - v_world.y) * 5.3 + phase);
    vec3 n = normalize(vec3(pente_x, pente_y, 1.0));

    float fresnel = pow(1.0 - max(dot(vue, n), 0.0), 3.0);
    vec3 couleur = mix(u_water, u_sky, 0.16 + 0.62 * fresnel);
    // Reflet du soleil sur les vagues (glitter).
    vec3 reflet = reflect(-vue, n);
    float spec = pow(max(dot(reflet, u_sun), 0.0), 180.0);
    couleur += vec3(1.0, 0.94, 0.78) * spec * 0.9;

    // Opaque : une eau transparente laissait voir les ombres du fond, qui se
    // lisaient comme des bandes diagonales à travers la palette.
    frag_color = vec4(couleur, 1.0);
}
