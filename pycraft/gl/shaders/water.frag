#version 330

in vec3 v_world;
in vec3 v_normal;
in float v_ao;

uniform vec3 u_camera;
uniform vec3 u_water;
uniform vec3 u_sky;
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
    vec3 n = normalize(v_normal);
    float fresnel = pow(1.0 - max(dot(vue, n), 0.0), 3.0);
    vec3 couleur = mix(u_water, u_sky, 0.20 + 0.55 * fresnel);
    couleur += vec3(0.05) * sin(u_time * 2.0 + v_world.x * 1.7 + v_world.y * 1.3);

    // transparence tramée : ~35 % des pixels laissent voir le fond
    if (bayer4(gl_FragCoord.xy) > 0.65) {
        discard;
    }
    frag_color = vec4(couleur, 1.0);
}
