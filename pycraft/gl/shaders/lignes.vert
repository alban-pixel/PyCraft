#version 330

in vec3 in_pos;

uniform mat4 u_mvp;
uniform vec2 u_res;
uniform vec2 u_offset;  // décalage en pixels : épaissit le trait

void main() {
    gl_Position = u_mvp * vec4(in_pos, 1.0);
    // Décalage constant à l'écran, indépendant de la distance.
    gl_Position.xy += u_offset / u_res * 2.0 * gl_Position.w;
}
