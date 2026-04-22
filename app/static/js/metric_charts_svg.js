/**
 * Сетка мини-графиков (чистый SVG): эталон human + значение пользователя.
 * Зависимостей нет; ожидается JSON как у metric_baselines_human.json.
 */
(function () {
  "use strict";

  var METRIC_ORDER = [
    "lexical_diversity",
    "burstiness",
    "average_sentence_length",
    "text_entropy",
    "stop_word_ratio",
    "word_length_variation",
    "punctuation_ratio",
    "repetition_score",
  ];

  var VB_W = 260;
  var VB_H = 112;
  var PAD_L = 10;
  var PAD_R = 10;
  var PAD_T = 6;
  var PAD_B = 16;
  var PLOT_W = VB_W - PAD_L - PAD_R;
  var PLOT_H = VB_H - PAD_T - PAD_B;

  function gaussianPdf(x, mu, sigma) {
    if (sigma < 1e-15) return 0;
    var z = (x - mu) / sigma;
    return Math.exp(-0.5 * z * z) / (sigma * Math.sqrt(2 * Math.PI));
  }

  function numOrNull(raw) {
    if (raw == null) return null;
    if (typeof raw === "number") {
      if (raw !== raw) return null;
      return raw;
    }
    var n = Number(raw);
    return n !== n ? null : n;
  }

  function el(name, attrs, text) {
    var e = document.createElementNS("http://www.w3.org/2000/svg", name);
    if (attrs) {
      Object.keys(attrs).forEach(function (k) {
        e.setAttribute(k, attrs[k]);
      });
    }
    if (text != null) e.textContent = text;
    return e;
  }

  function xToPx(x, xMin, xMax) {
    var span = xMax - xMin || 1e-9;
    return PAD_L + ((x - xMin) / span) * PLOT_W;
  }

  function yToPx(y, yMax) {
    var ym = yMax < 1e-20 ? 1 : yMax;
    return PAD_T + PLOT_H - (y / ym) * PLOT_H;
  }

  function placeholderSvg(msg) {
    var svg = el("svg", {
      viewBox: "0 0 " + VB_W + " " + VB_H,
      class: "metric-viz-cell__svg",
      role: "img",
      "aria-label": msg,
    });
    var t = el(
      "text",
      {
        x: String(VB_W / 2),
        y: String(VB_H / 2),
        "text-anchor": "middle",
        "dominant-baseline": "middle",
        fill: "#64748b",
        "font-size": "11",
      },
      msg
    );
    svg.appendChild(t);
    return svg;
  }

  function drawBernoulli(svg, p, val) {
    var H = PLOT_H * 0.72;
    var baseY = PAD_T + PLOT_H;
    var x0 = xToPx(0, -0.25, 1.25);
    var x1 = xToPx(1, -0.25, 1.25);
    var bw = Math.min((x1 - x0) * 0.35, 36);
    var h0 = (1 - p) * H;
    var h1 = p * H;
    svg.appendChild(
      el("rect", {
        x: String(x0 - bw / 2),
        y: String(baseY - h0),
        width: String(bw),
        height: String(h0),
        fill: "#e2e8f0",
        rx: "2",
      })
    );
    svg.appendChild(
      el("rect", {
        x: String(x1 - bw / 2),
        y: String(baseY - h1),
        width: String(bw),
        height: String(h1),
        fill: "#93c5fd",
        rx: "2",
      })
    );
    var xv = val >= 0.5 ? x1 : x0;
    var yTop = PAD_T + PLOT_H * 0.08;
    svg.appendChild(
      el("line", {
        x1: String(xv),
        y1: String(baseY),
        x2: String(xv),
        y2: String(yTop),
        stroke: "#ea580c",
        "stroke-width": "3",
      })
    );
    svg.appendChild(
      el("text", {
        x: String(x0),
        y: String(baseY + 12),
        "text-anchor": "middle",
        fill: "#64748b",
        "font-size": "9",
      }, "0")
    );
    svg.appendChild(
      el("text", {
        x: String(x1),
        y: String(baseY + 12),
        "text-anchor": "middle",
        fill: "#64748b",
        "font-size": "9",
      }, "1")
    );
  }

  function drawNormal(svg, b, val) {
    var mu = Number(b.mean);
    var sigma = Number(b.std);
    var xs = [];
    var ys = [];
    var xMin;
    var xMax;
    var i;
    if (sigma < 1e-12) {
      var xLo = Math.min(mu, val, Number(b.min != null ? b.min : mu));
      var xHi = Math.max(mu, val, Number(b.max != null ? b.max : mu));
      var rng = Math.max(xHi - xLo, 1e-9);
      for (i = 0; i <= 40; i++) {
        xs.push(xLo - 0.1 * rng + (i / 40) * (1.2 * rng));
        ys.push(0);
      }
      xMin = xs[0];
      xMax = xs[xs.length - 1];
    } else {
      xMin = Math.min(mu - 3.5 * sigma, Number(b.min), val);
      xMax = Math.max(mu + 3.5 * sigma, Number(b.max), val);
      var xr = (xMax - xMin) * 0.05;
      xMin -= xr;
      xMax += xr;
      for (i = 0; i < 120; i++) {
        var t = i / 119;
        var x = xMin + t * (xMax - xMin);
        xs.push(x);
        ys.push(gaussianPdf(x, mu, sigma));
      }
    }
    var ymax = 0;
    for (i = 0; i < ys.length; i++) if (ys[i] > ymax) ymax = ys[i];
    if (ymax < 1e-20) ymax = 1;
    var yMark = ymax * 1.08;

    var bottom = PAD_T + PLOT_H;
    var d =
      "M " +
      xToPx(xs[0], xMin, xMax).toFixed(2) +
      " " +
      yToPx(ys[0], ymax).toFixed(2);
    for (i = 1; i < xs.length; i++) {
      d +=
        " L " +
        xToPx(xs[i], xMin, xMax).toFixed(2) +
        " " +
        yToPx(ys[i], ymax).toFixed(2);
    }
    d +=
      " L " +
      xToPx(xs[xs.length - 1], xMin, xMax).toFixed(2) +
      " " +
      bottom.toFixed(2) +
      " L " +
      xToPx(xs[0], xMin, xMax).toFixed(2) +
      " " +
      bottom.toFixed(2) +
      " Z";
    svg.appendChild(
      el("path", {
        d: d,
        fill: "rgba(37, 99, 235, 0.18)",
        stroke: "#2563eb",
        "stroke-width": "2",
        "stroke-linejoin": "round",
      })
    );
    var vx = xToPx(val, xMin, xMax);
    var vy0 = yToPx(0, ymax);
    var vy1 = yToPx(yMark, ymax);
    svg.appendChild(
      el("line", {
        x1: vx.toFixed(2),
        y1: vy0.toFixed(2),
        x2: vx.toFixed(2),
        y2: vy1.toFixed(2),
        stroke: "#ea580c",
        "stroke-width": "3",
      })
    );
  }

  function renderCell(b, key, metrics) {
    var wrap = document.createElement("div");
    wrap.className = "metric-viz-cell";

    var title = document.createElement("div");
    title.className = "metric-viz-cell__title";
    title.textContent = (b && b.label_ru) || key;
    wrap.appendChild(title);

    var dist = (b && b.distribution) || "";
    var raw = metrics[key];
    var val = numOrNull(raw);

    if (dist === "empty" || !b || (b.n != null && b.n === 0)) {
      var phParts = dist === "empty" ? ["Нет эталона"] : ["Нет данных"];
      if (val != null) phParts.unshift("v=" + val.toPrecision(4));
      wrap.appendChild(placeholderSvg(phParts.join(" · ")));
      return wrap;
    }

    if (val == null) {
      wrap.appendChild(placeholderSvg("не посчитано"));
      return wrap;
    }

    var svg = el("svg", {
      viewBox: "0 0 " + VB_W + " " + VB_H,
      class: "metric-viz-cell__svg",
      role: "img",
      "aria-hidden": "true",
    });

    if (dist === "bernoulli") {
      var p = Number(b.mean);
      drawBernoulli(svg, p, val);
      wrap.appendChild(svg);
      return wrap;
    }

    drawNormal(svg, b, val);
    wrap.appendChild(svg);
    return wrap;
  }

  function render(container, payload, metrics) {
    if (!container) return;
    container.innerHTML = "";
    var bmap = (payload && payload.metrics) || {};
    METRIC_ORDER.forEach(function (key) {
      container.appendChild(renderCell(bmap[key], key, metrics || {}));
    });
  }

  window.MetricVizSvg = {
    METRIC_ORDER: METRIC_ORDER,
    render: render,
  };
})();
