/* Verst · variants A/B: static frame of the windshield scene (Canvas in the app, components §9).
   The scene is sized by its content (mirror + sign + a road strip), not the other way round:
   the horizon sits just under the sign, so only a strip of road and sun shows — the scene no longer
   fills half the screen (review problem 1). Colours come from the CSS variables of the active theme.
   Motion is unchanged from motion.md (lanes, posts, mirror sway); a mockup shows frame 0. */
(function () {
  function v(name) { return getComputedStyle(document.documentElement).getPropertyValue(name).trim(); }

  function draw() {
    var scene = document.querySelector('.scene');
    if (!scene) return;
    var sign = scene.querySelector('.sign');
    var W = scene.clientWidth, H = scene.clientHeight;
    var sb = sign.offsetTop + sign.offsetHeight;          // sign bottom
    var day = document.documentElement.dataset.theme === 'day';
    var horizon = Math.round(sb + Math.max(8, Math.min(26, (H - sb) * 0.4)));
    var bands = [v('--sky1'), v('--sky2'), v('--sky3'), v('--sky4'), v('--sky5')];
    var weights = day ? [0.30, 0.25, 0.2, 0.15, 0.10] : [0.30, 0.22, 0.2, 0.16, 0.12];
    var s = '';
    var y = 0;
    bands.forEach(function (c, i) {
      var h = Math.round(horizon * weights[i]);
      if (i === bands.length - 1) h = horizon - y;
      s += '<rect x="0" y="' + y + '" width="' + W + '" height="' + (h + 1) + '" fill="' + c + '"/>';
      y += h;
    });
    if (day) {
      // high, pale day sun and two flat clouds where the sky is visible (around the mirror)
      s += '<circle cx="' + (W - 52) + '" cy="34" r="17" fill="' + v('--sun') + '"/>';
      s += '<path d="M30 44 h40 a9 9 0 0 0 -9 -11 a13 13 0 0 0 -22 2 a8 8 0 0 0 -9 9 z" fill="' + v('--cloud') + '"/>';
      s += '<path d="M' + (W - 84) + ' 50 h46 a10 10 0 0 0 -10 -12 a14 14 0 0 0 -24 2 a8 8 0 0 0 -12 10 z" fill="' + v('--cloud') + '"/>';
    } else {
      s += '<circle cx="' + Math.round(W * 0.7) + '" cy="' + (horizon + 4) + '" r="24" fill="' + v('--sun') + '"/>';
    }
    // hills along the horizon
    var hp = 'M0 ' + (horizon - 6);
    var pts = [[0.1, -12], [0.21, -7], [0.33, -15], [0.44, -9], [0.52, -13], [0.64, -5], [0.77, -14], [0.9, -8], [1, -11]];
    pts.forEach(function (p) { hp += ' L' + Math.round(W * p[0]) + ' ' + (horizon + p[1]); });
    hp += ' L' + W + ' ' + (horizon + 2) + ' L0 ' + (horizon + 2) + ' Z';
    s += '<path d="' + hp + '" fill="' + v('--hills') + '"/>';
    // fields
    s += '<rect x="0" y="' + horizon + '" width="' + W + '" height="' + (H - horizon) + '" fill="' + v('--ground') + '"/>';
    if (day) s += '<rect x="0" y="' + horizon + '" width="' + W + '" height="6" fill="' + v('--ground-far') + '"/>';
    // road: vanishing point on the horizon, 230 dp wide at y = H (as components §9.1, scaled to the strip)
    var cx = W / 2, top = 6, bot = Math.min(W * 0.66, 260);
    s += '<path d="M' + (cx - top / 2) + ' ' + horizon + ' L' + (cx + top / 2) + ' ' + horizon + ' L' + (cx + bot / 2) + ' ' + H + ' L' + (cx - bot / 2) + ' ' + H + ' Z" fill="' + v('--road') + '"/>';
    s += '<path d="M' + (cx - top / 2) + ' ' + horizon + ' L' + (cx - bot / 2) + ' ' + H + '" stroke="' + v('--road-edge') + '" stroke-width="4"/>';
    s += '<path d="M' + (cx + top / 2) + ' ' + horizon + ' L' + (cx + bot / 2) + ' ' + H + '" stroke="' + v('--road-edge') + '" stroke-width="4"/>';
    var span = H - horizon;
    [[0.12, 0.2], [0.42, 0.62]].forEach(function (d) {
      var y1 = horizon + span * d[0], y2 = horizon + span * d[1];
      var w1 = 1 + 5 * d[0], w2 = 1 + 5 * d[1];
      s += '<path d="M' + (cx - w1 / 2) + ' ' + y1 + ' L' + (cx + w1 / 2) + ' ' + y1 + ' L' + (cx + w2 / 2) + ' ' + y2 + ' L' + (cx - w2 / 2) + ' ' + y2 + ' Z" fill="' + v('--road-edge') + '"/>';
    });
    // gantry legs under the sign
    var legBot = horizon + span * 0.55;
    s += '<rect x="34" y="' + (sb - 4) + '" width="8" height="' + (legBot - sb + 4) + '" fill="' + v('--pole') + '"/>';
    s += '<rect x="' + (W - 42) + '" y="' + (sb - 4) + '" width="8" height="' + (legBot - sb + 4) + '" fill="' + v('--pole') + '"/>';
    // roof liner and A-pillars
    s += '<path d="M0 0 H' + W + ' V14 Q' + (W / 2) + ' 30 0 14 Z" fill="' + v('--liner') + '"/>';
    s += '<path d="M0 0 L24 0 L10 ' + H + ' L0 ' + H + ' Z" fill="' + v('--liner') + '"/>';
    s += '<path d="M' + W + ' 0 L' + (W - 24) + ' 0 L' + (W - 10) + ' ' + H + ' L' + W + ' ' + H + ' Z" fill="' + v('--liner') + '"/>';
    var bg = scene.querySelector('.scene-bg');
    bg.innerHTML = '<svg width="' + W + '" height="' + H + '" viewBox="0 0 ' + W + ' ' + H + '" aria-hidden="true">' + s + '</svg>';
  }
  if (document.fonts && document.fonts.ready) document.fonts.ready.then(draw); else window.addEventListener('load', draw);
  window.addEventListener('resize', draw);
})();
