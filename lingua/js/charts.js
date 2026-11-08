/* Lingua · 零依赖 SVG 图表（环形 / 柱状 / 折线 / 雷达 / 热力图） */
(function () {
  let uid = 0;

  function ring(pct, opts) {
    opts = opts || {};
    const size = opts.size || 140;
    const stroke = opts.stroke || 12;
    const r = (size - stroke) / 2;
    const c = 2 * Math.PI * r;
    const p = Math.max(0, Math.min(100, pct)) / 100;
    const fillClass = opts.tone === 'accent' ? 'ring-fill accent' : 'ring-fill';
    const value = opts.valueText != null ? opts.valueText : Math.round(pct) + '%';
    return '<svg class="ring" width="' + size + '" height="' + size + '" viewBox="0 0 ' + size + ' ' + size + '" role="img">' +
      '<circle class="ring-track" cx="' + size / 2 + '" cy="' + size / 2 + '" r="' + r + '" fill="none" stroke-width="' + stroke + '"/>' +
      '<circle class="' + fillClass + '" cx="' + size / 2 + '" cy="' + size / 2 + '" r="' + r + '" fill="none" stroke-width="' + stroke +
      '" stroke-linecap="round" stroke-dasharray="' + c.toFixed(1) + '" stroke-dashoffset="' + (c * (1 - p)).toFixed(1) +
      '" transform="rotate(-90 ' + size / 2 + ' ' + size / 2 + ')"/>' +
      '<text x="50%" y="50%" class="ring-num" text-anchor="middle" dy="' + (opts.label ? '-0.05em' : '0.34em') + '">' + value + '</text>' +
      (opts.label ? '<text x="50%" y="50%" class="ring-label" text-anchor="middle" dy="1.45em">' + opts.label + '</text>' : '') +
      '</svg>';
  }

  function bars(values, labels, opts) {
    opts = opts || {};
    const w = 560, h = opts.height || 210, padL = 30, padR = 10, padT = 24, padB = 30;
    const max = Math.max.apply(null, values.concat([20]));
    const innerW = w - padL - padR, innerH = h - padT - padB;
    const step = innerW / values.length;
    const bw = Math.min(34, step * 0.46);
    let svg = '<svg class="chart-svg" viewBox="0 0 ' + w + ' ' + h + '" preserveAspectRatio="xMidYMid meet" role="img">';
    for (let g = 0; g <= 3; g++) {
      const y = padT + (innerH / 3) * g;
      const val = Math.round(max - (max / 3) * g);
      svg += '<line class="chart-grid" x1="' + padL + '" y1="' + y + '" x2="' + (w - padR) + '" y2="' + y + '"/>';
      svg += '<text class="chart-label" x="' + (padL - 6) + '" y="' + (y + 3) + '" text-anchor="end">' + val + '</text>';
    }
    values.forEach(function (v, i) {
      const bh = innerH * (v / max);
      const x = padL + step * i + (step - bw) / 2;
      const y = padT + innerH - bh;
      svg += '<rect class="chart-bar' + (labels && labels[i] === '今天' ? ' is-today' : '') + '" x="' + x + '" y="' + y +
        '" width="' + bw + '" height="' + Math.max(bh, 2) + '" rx="7"/>';
      if (v > 0) svg += '<text class="chart-value" x="' + (x + bw / 2) + '" y="' + (y - 7) + '" text-anchor="middle">' + v + '</text>';
      svg += '<text class="chart-label" x="' + (x + bw / 2) + '" y="' + (h - 8) + '" text-anchor="middle">' + (labels ? labels[i] : '') + '</text>';
    });
    return svg + '</svg>';
  }

  function line(values, labels, opts) {
    opts = opts || {};
    const w = 560, h = opts.height || 220, padL = 32, padR = 14, padT = 24, padB = 30;
    const max = Math.max.apply(null, values.concat([20]));
    const innerW = w - padL - padR, innerH = h - padT - padB;
    const step = innerW / Math.max(1, values.length - 1);
    const gid = 'lg' + (++uid);
    const pts = values.map(function (v, i) {
      return { x: padL + step * i, y: padT + innerH - innerH * (v / max), v: v };
    });
    let svg = '<svg class="chart-svg" viewBox="0 0 ' + w + ' ' + h + '" preserveAspectRatio="xMidYMid meet" role="img">' +
      '<defs><linearGradient id="' + gid + '" x1="0" y1="0" x2="0" y2="1">' +
      '<stop offset="0%" stop-color="#1e5b4a" stop-opacity="0.22"/><stop offset="100%" stop-color="#1e5b4a" stop-opacity="0"/>' +
      '</linearGradient></defs>';
    for (let g = 0; g <= 3; g++) {
      const y = padT + (innerH / 3) * g;
      svg += '<line class="chart-grid" x1="' + padL + '" y1="' + y + '" x2="' + (w - padR) + '" y2="' + y + '"/>';
      svg += '<text class="chart-label" x="' + (padL - 6) + '" y="' + (y + 3) + '" text-anchor="end">' + Math.round(max - (max / 3) * g) + '</text>';
    }
    let d = '';
    pts.forEach(function (p, i) { d += (i === 0 ? 'M' : 'L') + p.x + ' ' + p.y + ' '; });
    const area = d + 'L' + pts[pts.length - 1].x + ' ' + (padT + innerH) + ' L' + pts[0].x + ' ' + (padT + innerH) + ' Z';
    svg += '<path d="' + area + '" fill="url(#' + gid + ')"/>';
    svg += '<path class="chart-line" d="' + d + '"/>';
    pts.forEach(function (p, i) {
      svg += '<circle class="chart-dot' + (i === pts.length - 1 ? ' is-now' : '') + '" cx="' + p.x + '" cy="' + p.y + '" r="' + (i === pts.length - 1 ? 5 : 3.5) + '"/>';
      if (labels) svg += '<text class="chart-label" x="' + p.x + '" y="' + (h - 8) + '" text-anchor="middle">' + labels[i] + '</text>';
    });
    return svg + '</svg>';
  }

  function radar(items) {
    const w = 320, h = 286, cx = 160, cy = 144, R = 94;
    const n = items.length;
    const ang = function (i) { return (-90 + i * (360 / n)) * Math.PI / 180; };
    const pt = function (i, ratio) {
      const a = ang(i);
      return { x: cx + Math.cos(a) * R * ratio, y: cy + Math.sin(a) * R * ratio };
    };
    let svg = '<svg class="chart-svg radar-svg" viewBox="0 0 ' + w + ' ' + h + '" role="img">';
    for (let g = 1; g <= 4; g++) {
      const poly = [];
      for (let i = 0; i < n; i++) { const p = pt(i, g / 4); poly.push(p.x.toFixed(1) + ',' + p.y.toFixed(1)); }
      svg += '<polygon class="chart-grid' + (g === 4 ? ' strong' : '') + '" points="' + poly.join(' ') + '"/>';
    }
    for (let i = 0; i < n; i++) {
      const p = pt(i, 1);
      svg += '<line class="chart-grid" x1="' + cx + '" y1="' + cy + '" x2="' + p.x.toFixed(1) + '" y2="' + p.y.toFixed(1) + '"/>';
    }
    const pts = items.map(function (item, i) { return pt(i, Math.max(0, Math.min(100, item.value)) / 100); });
    svg += '<polygon class="radar-area" points="' + pts.map(function (p) { return p.x.toFixed(1) + ',' + p.y.toFixed(1); }).join(' ') + '"/>';
    pts.forEach(function (p) { svg += '<circle class="radar-dot" cx="' + p.x.toFixed(1) + '" cy="' + p.y.toFixed(1) + '" r="3.5"/>'; });
    items.forEach(function (item, i) {
      const p = pt(i, 1);
      const dx = p.x - cx, dy = p.y - cy;
      const lx = cx + dx * 1.22, ly = cy + dy * 1.22;
      const anchor = Math.abs(dx) < 6 ? 'middle' : (dx > 0 ? 'start' : 'end');
      svg += '<text class="radar-label" x="' + lx.toFixed(1) + '" y="' + (ly + 4).toFixed(1) + '" text-anchor="' + anchor + '">' + item.label + '</text>';
      svg += '<text class="radar-value" x="' + lx.toFixed(1) + '" y="' + (ly + 18).toFixed(1) + '" text-anchor="' + anchor + '">' + item.value + '</text>';
    });
    return svg + '</svg>';
  }

  function heatmap(days) {
    const cell = 12, gap = 3, left = 22, top = 6;
    const first = new Date(days[0].date + 'T00:00:00');
    const offset = (first.getDay() + 6) % 7;
    const cols = Math.ceil((offset + days.length) / 7);
    const w = left + cols * (cell + gap);
    const h = top + 7 * (cell + gap) + 4;
    let svg = '<svg class="heat-svg" viewBox="0 0 ' + w + ' ' + h + '" role="img">';
    ['一', '三', '五'].forEach(function (t, i) {
      svg += '<text class="heat-week" x="' + (left - 6) + '" y="' + (top + (i * 2) * (cell + gap) + cell - 2) + '" text-anchor="end">' + t + '</text>';
    });
    days.forEach(function (d, i) {
      const row = (offset + i) % 7;
      const col = Math.floor((offset + i) / 7);
      let bucket = 0;
      if (d.minutes > 0) bucket = d.minutes < 10 ? 1 : d.minutes < 20 ? 2 : d.minutes < 40 ? 3 : 4;
      svg += '<rect class="heat-cell heat-' + bucket + (i === days.length - 1 ? ' heat-today' : '') + '" x="' + (left + col * (cell + gap)) +
        '" y="' + (top + row * (cell + gap)) + '" width="' + cell + '" height="' + cell + '" rx="3">' +
        '<title>' + d.date + ' · ' + d.minutes + ' 分钟</title></rect>';
    });
    return svg + '</svg>';
  }

  window.Charts = { ring: ring, bars: bars, line: line, radar: radar, heatmap: heatmap };
})();
