// Minimal flat-shaded software rasterizer with sun shadow map, fog and SSAA.
// usage: raster static.bin frames.bin W H SS > raw_rgb_stream
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include <stdint.h>

typedef struct { float x, y, z; } v3;
static v3 V(float x, float y, float z) { v3 r = {x, y, z}; return r; }
static v3 sub(v3 a, v3 b) { return V(a.x - b.x, a.y - b.y, a.z - b.z); }
static v3 add(v3 a, v3 b) { return V(a.x + b.x, a.y + b.y, a.z + b.z); }
static v3 mul(v3 a, float s) { return V(a.x * s, a.y * s, a.z * s); }
static float dot(v3 a, v3 b) { return a.x * b.x + a.y * b.y + a.z * b.z; }
static v3 cross(v3 a, v3 b) { return V(a.y * b.z - a.z * b.y, a.z * b.x - a.x * b.z, a.x * b.y - a.y * b.x); }
static v3 norm(v3 a) { float l = sqrtf(dot(a, a)); return l > 0 ? mul(a, 1.f / l) : a; }

typedef struct { int n; float *t; uint8_t *c; } Mesh;

static Mesh read_mesh(FILE *f) {
    Mesh m; if (fread(&m.n, 4, 1, f) != 1) { m.n = -1; return m; }
    m.t = malloc(sizeof(float) * 9 * (m.n ? m.n : 1));
    m.c = malloc(3 * (m.n ? m.n : 1));
    if (m.n) { fread(m.t, 4, 9 * m.n, f); fread(m.c, 1, 3 * m.n, f); }
    return m;
}

static float srgb2lin(float c) { c /= 255.f; return c <= 0.04045f ? c / 12.92f : powf((c + 0.055f) / 1.055f, 2.4f); }
static float lin2srgb(float c) { if (c < 0) c = 0; if (c > 1) c = 1; return c <= 0.0031308f ? c * 12.92f : 1.055f * powf(c, 1 / 2.4f) - 0.055f; }

// ---------------------------------------------------------------- shadow map (orthographic, sun)
#define SM 4096
static float *smap; static v3 sun, su, sv; static float smin_u, smin_v, sscale;

static void sm_tri(v3 a, v3 b, v3 c) {
    float ax = (dot(a, su) - smin_u) * sscale, ay = (dot(a, sv) - smin_v) * sscale, ad = dot(a, sun);
    float bx = (dot(b, su) - smin_u) * sscale, by = (dot(b, sv) - smin_v) * sscale, bd = dot(b, sun);
    float cx = (dot(c, su) - smin_u) * sscale, cy = (dot(c, sv) - smin_v) * sscale, cd = dot(c, sun);
    float area = (bx - ax) * (cy - ay) - (by - ay) * (cx - ax);
    if (fabsf(area) < 1e-9f) return;
    int x0 = (int)fmaxf(0, floorf(fminf(ax, fminf(bx, cx)))), x1 = (int)fminf(SM - 1, ceilf(fmaxf(ax, fmaxf(bx, cx))));
    int y0 = (int)fmaxf(0, floorf(fminf(ay, fminf(by, cy)))), y1 = (int)fminf(SM - 1, ceilf(fmaxf(ay, fmaxf(by, cy))));
    for (int y = y0; y <= y1; y++) for (int x = x0; x <= x1; x++) {
        float px = x + .5f, py = y + .5f;
        float w0 = ((bx - px) * (cy - py) - (by - py) * (cx - px)) / area;
        float w1 = ((cx - px) * (ay - py) - (cy - py) * (ax - px)) / area;
        float w2 = 1 - w0 - w1;
        if (w0 < 0 || w1 < 0 || w2 < 0) continue;
        float d = w0 * ad + w1 * bd + w2 * cd;   // larger = closer to the sun
        float *s = &smap[y * SM + x]; if (d > *s) *s = d;
    }
}

static float shadow_at(v3 p, v3 n) {
    v3 q = add(p, mul(n, 0.35f));
    float x = (dot(q, su) - smin_u) * sscale, y = (dot(q, sv) - smin_v) * sscale, d = dot(q, sun);
    float lit = 0; int cnt = 0;
    for (int dy = -1; dy <= 1; dy++) for (int dx = -1; dx <= 1; dx++) {
        int ix = (int)x + dx, iy = (int)y + dy; cnt++;
        if (ix < 0 || iy < 0 || ix >= SM || iy >= SM) { lit += 1; continue; }
        lit += (smap[iy * SM + ix] <= d + 0.25f) ? 1.f : 0.f;
    }
    return lit / cnt;
}

// ---------------------------------------------------------------- main raster
static int W, H; static float *zbuf; static int *idbuf;
static int gl_lo = -1, gl_hi = -1; static long gl_try = 0, gl_won = 0, gl_blk = 0;
static v3 cpos, cf, cr, cu; static float fl; static int ortho; static float oscale;

typedef struct { float x, y, z; } sv3;   // screen x,y + view z

static void raster_screen_tri(sv3 a, sv3 b, sv3 c, int id) {
    float area = (b.x - a.x) * (c.y - a.y) - (b.y - a.y) * (c.x - a.x);
    if (fabsf(area) < 1e-12f) return;
    int x0 = (int)fmaxf(0, floorf(fminf(a.x, fminf(b.x, c.x)))), x1 = (int)fminf(W - 1, ceilf(fmaxf(a.x, fmaxf(b.x, c.x))));
    int y0 = (int)fmaxf(0, floorf(fminf(a.y, fminf(b.y, c.y)))), y1 = (int)fminf(H - 1, ceilf(fmaxf(a.y, fmaxf(b.y, c.y))));
    float ia = ortho ? a.z : 1.f / a.z, ib = ortho ? b.z : 1.f / b.z, ic = ortho ? c.z : 1.f / c.z;
    for (int y = y0; y <= y1; y++) for (int x = x0; x <= x1; x++) {
        float px = x + .5f, py = y + .5f;
        float w0 = ((b.x - px) * (c.y - py) - (b.y - py) * (c.x - px)) / area;
        float w1 = ((c.x - px) * (a.y - py) - (c.y - py) * (a.x - px)) / area;
        float w2 = 1 - w0 - w1;
        if (w0 < 0 || w1 < 0 || w2 < 0) continue;
        float iz = w0 * ia + w1 * ib + w2 * ic;
        float z = ortho ? iz : 1.f / iz;
        int k = y * W + x;
        int isg = (id >= gl_lo && id < gl_hi);
        if (isg) gl_try++;
        if (z < zbuf[k]) { zbuf[k] = z; idbuf[k] = id; if (isg) gl_won++; }
        else if (isg && idbuf[k] < gl_lo) gl_blk++;
    }
}

static sv3 project(v3 v) {  // v in view space (x right, y up, z fwd)
    sv3 s;
    if (ortho) { s.x = W * .5f + v.x * oscale; s.y = H * .5f - v.y * oscale; s.z = v.z; }
    else { s.x = W * .5f + v.x / v.z * fl; s.y = H * .5f - v.y / v.z * fl; s.z = v.z; }
    return s;
}

#define NEAR 0.2f
static void draw_tri(const float *t, int id) {
    v3 w[3], vs[3];
    for (int i = 0; i < 3; i++) {
        w[i] = V(t[i * 3], t[i * 3 + 1], t[i * 3 + 2]);
        v3 d = sub(w[i], cpos); vs[i] = V(dot(d, cr), dot(d, cu), dot(d, cf));
    }
    if (ortho) { raster_screen_tri(project(vs[0]), project(vs[1]), project(vs[2]), id); return; }
    // clip against near plane
    v3 out[4]; int n = 0;
    for (int i = 0; i < 3; i++) {
        v3 A = vs[i], B = vs[(i + 1) % 3];
        int ina = A.z > NEAR, inb = B.z > NEAR;
        if (ina) out[n++] = A;
        if (ina != inb) { float tt = (NEAR - A.z) / (B.z - A.z); out[n++] = add(A, mul(sub(B, A), tt)); }
    }
    if (n < 3) return;
    sv3 p0 = project(out[0]);
    for (int i = 1; i + 1 < n; i++) raster_screen_tri(p0, project(out[i]), project(out[i + 1]), id);
}

int main(int argc, char **argv) {
    if (argc < 6) { fprintf(stderr, "usage\n"); return 1; }
    FILE *fs = fopen(argv[1], "rb"); Mesh st = read_mesh(fs); fclose(fs);
    int OW = atoi(argv[3]), OH = atoi(argv[4]), SS = atoi(argv[5]);
    W = OW * SS; H = OH * SS;
    zbuf = malloc(sizeof(float) * W * H); idbuf = malloc(sizeof(int) * W * H);
    smap = malloc(sizeof(float) * SM * SM);
    uint8_t *outb = malloc(OW * OH * 3);
    float *acc = malloc(sizeof(float) * OW * OH * 3);

    sun = norm(V(-0.52f, -0.55f, 0.66f));   // direction TO the sun (warm, from south-west)
    su = norm(cross(V(0, 0, 1), sun)); sv = cross(sun, su);
    // shadow-map bounds from static scene
    smin_u = 1e30f; smin_v = 1e30f; float maxu = -1e30f, maxv = -1e30f;
    float bx0 = -1e30f, by0 = -1e30f, bx1 = 1e30f, by1 = 1e30f;
    if (getenv("SMBOX")) sscanf(getenv("SMBOX"), "%f %f %f %f", &bx0, &by0, &bx1, &by1);
    char *inbox = malloc(st.n);
    for (int i = 0; i < st.n; i++) {
        float cx = (st.t[i * 9] + st.t[i * 9 + 3] + st.t[i * 9 + 6]) / 3, cy = (st.t[i * 9 + 1] + st.t[i * 9 + 4] + st.t[i * 9 + 7]) / 3;
        inbox[i] = cx > bx0 && cx < bx1 && cy > by0 && cy < by1;
    }
    for (int i = 0; i < st.n * 3; i++) {
        if (!inbox[i / 3]) continue;
        v3 p = V(st.t[i * 3], st.t[i * 3 + 1], st.t[i * 3 + 2]);
        float u = dot(p, su), v = dot(p, sv);
        if (u < smin_u) smin_u = u; if (v < smin_v) smin_v = v; if (u > maxu) maxu = u; if (v > maxv) maxv = v;
    }
    sscale = (SM - 2) / fmaxf(maxu - smin_u, maxv - smin_v);

    // precompute linear albedo + normals for static
    FILE *ff = fopen(argv[2], "rb");
    int nf; fread(&nf, 4, 1, ff);
    float *stalb = malloc(sizeof(float) * 3 * st.n); v3 *stn = malloc(sizeof(v3) * st.n);
    for (int i = 0; i < st.n; i++) {
        for (int k = 0; k < 3; k++) stalb[i * 3 + k] = srgb2lin(st.c[i * 3 + k]);
        float *t = st.t + i * 9;
        stn[i] = norm(cross(sub(V(t[3], t[4], t[5]), V(t[0], t[1], t[2])), sub(V(t[6], t[7], t[8]), V(t[0], t[1], t[2]))));
    }
    v3 sky_top = V(srgb2lin(126), srgb2lin(150), srgb2lin(222));
    v3 sky_hor = V(srgb2lin(230), srgb2lin(224), srgb2lin(238));
    v3 sun_col = V(1.62f, 1.34f, 1.00f);
    v3 amb_sky = V(0.40f, 0.40f, 0.48f), amb_gnd = V(0.30f, 0.24f, 0.17f);
    v3 fog_col = V(srgb2lin(204), srgb2lin(208), srgb2lin(236));

    float *smap_static = NULL;
    for (int fi = 0; fi < nf; fi++) {
        float cam[13]; fread(cam, 4, 13, ff);
        Mesh dy = read_mesh(ff);
        cpos = V(cam[0], cam[1], cam[2]); cf = norm(V(cam[3], cam[4], cam[5]));
        v3 upv = V(cam[6], cam[7], cam[8]);
        cr = norm(cross(cf, upv)); cu = cross(cr, cf);
        float fov = cam[9]; float fogk = cam[10]; float fogs = cam[11]; int ngl = (int)cam[12];
        gl_lo = st.n; gl_hi = st.n + ngl; gl_try = gl_won = gl_blk = 0;
        ortho = fov < 0; if (ortho) oscale = W / (-fov); else fl = (W * .5f) / tanf(fov * .5f * (float)M_PI / 180.f);

        // shadow map: cached static part + dynamic
        if (!smap_static) {
            for (int i = 0; i < SM * SM; i++) smap[i] = -1e30f;
            for (int i = 0; i < st.n; i++) { if (!inbox[i]) continue; float *t = st.t + i * 9; sm_tri(V(t[0], t[1], t[2]), V(t[3], t[4], t[5]), V(t[6], t[7], t[8])); }
            smap_static = malloc(sizeof(float) * SM * SM); memcpy(smap_static, smap, sizeof(float) * SM * SM);
        } else memcpy(smap, smap_static, sizeof(float) * SM * SM);
        for (int i = 0; i < dy.n; i++) { float *t = dy.t + i * 9; sm_tri(V(t[0], t[1], t[2]), V(t[3], t[4], t[5]), V(t[6], t[7], t[8])); }

        for (int i = 0; i < W * H; i++) { zbuf[i] = 1e30f; idbuf[i] = -1; }
        for (int i = 0; i < st.n; i++) draw_tri(st.t + i * 9, i);
        for (int i = 0; i < dy.n; i++) draw_tri(dy.t + i * 9, st.n + i);

        memset(acc, 0, sizeof(float) * OW * OH * 3);
        long nearpix = 0, skypix = 0;
        for (int y = 0; y < H; y++) for (int x = 0; x < W; x++) {
            int k = y * W + x, id = idbuf[k];
            v3 col;
            // view ray
            v3 rd;
            if (ortho) rd = cf;
            else rd = norm(add(cf, add(mul(cr, (x + .5f - W * .5f) / fl), mul(cu, -(y + .5f - H * .5f) / fl))));
            if (id < 0) {
                skypix++;
                float h = fmaxf(0, rd.z);
                float t = powf(h, 0.55f);
                col = add(mul(sky_hor, 1 - t), mul(sky_top, t));
                float sd = fmaxf(0, dot(rd, sun));
                col = add(col, mul(V(1.0f, 0.85f, 0.6f), 0.35f * powf(sd, 24.f) + 1.2f * powf(sd, 900.f)));
            } else {
                v3 alb, n;
                if (id < st.n) { alb = V(stalb[id * 3], stalb[id * 3 + 1], stalb[id * 3 + 2]); n = stn[id]; }
                else {
                    int j = id - st.n; float *t = dy.t + j * 9;
                    alb = V(srgb2lin(dy.c[j * 3]), srgb2lin(dy.c[j * 3 + 1]), srgb2lin(dy.c[j * 3 + 2]));
                    n = norm(cross(sub(V(t[3], t[4], t[5]), V(t[0], t[1], t[2])), sub(V(t[6], t[7], t[8]), V(t[0], t[1], t[2]))));
                }
                if (dot(n, rd) > 0) n = mul(n, -1);
                float z = zbuf[k];
                v3 p;
                if (ortho) p = add(add(cpos, mul(cr, (x + .5f - W * .5f) / oscale)), add(mul(cu, -(y + .5f - H * .5f) / oscale), mul(cf, z)));
                else p = add(cpos, mul(rd, z / dot(rd, cf)));
                int unlit = id >= st.n && dy.c[(id - st.n) * 3] >= 246 && dy.c[(id - st.n) * 3 + 2] == 248;
                float ndl = fmaxf(0, dot(n, sun));
                float sh = ndl > 0 ? shadow_at(p, n) : 0;
                float hemi = 0.5f + 0.5f * n.z;
                v3 amb = add(mul(amb_sky, hemi), mul(amb_gnd, 1 - hemi));
                v3 light = add(amb, mul(sun_col, ndl * sh));
                col = unlit ? mul(alb, 1.05f) : V(alb.x * light.x, alb.y * light.y, alb.z * light.z);
                float dist = ortho ? 0 : sqrtf(dot(sub(p, cpos), sub(p, cpos)));
                float f = 1 - expf(-fmaxf(0, dist - fogs) / fogk);
                if (id < st.n && dist < 150.f) nearpix++;
                col = add(mul(col, 1 - f), mul(fog_col, f));
            }
            int ox = x / SS, oy = y / SS, o = (oy * OW + ox) * 3;
            acc[o] += col.x; acc[o + 1] += col.y; acc[o + 2] += col.z;
        }
        float inv = 1.f / (SS * SS);
        for (int i = 0; i < OW * OH * 3; i++) outb[i] = (uint8_t)(lin2srgb(acc[i] * inv) * 255.f + .5f);
        fwrite(outb, 1, OW * OH * 3, stdout); fflush(stdout);
        free(dy.t); free(dy.c);
        if (getenv("RSTATS")) { FILE *sf = fopen(getenv("RSTATS"), "a"); fprintf(sf, "%d %ld %ld %ld %.5f %.5f\n", fi, gl_try, gl_won, gl_blk, nearpix / (double)(W * H), skypix / (double)(W * H)); fclose(sf); }
    }
    return 0;
}
