import { DurableObject } from "cloudflare:workers";

export class QssStore extends DurableObject {
  async fetch(request) {
    const url = new URL(request.url);
    const key = url.pathname.replace(/^\/+/, "") || "index";
    if (request.method === "PUT") {
      const buf = await request.arrayBuffer();
      await this.ctx.storage.put(key, buf);
      return new Response("ok");
    }
    const buf = await this.ctx.storage.get(key);
    if (!buf) return new Response("missing", { status: 404 });
    const type = key.endsWith(".html")
      ? "text/html; charset=utf-8"
      : key.endsWith(".json")
        ? "application/json; charset=utf-8"
        : "application/octet-stream";
    return new Response(buf, {
      headers: { "content-type": type, "cache-control": "no-store" },
    });
  }
}

function store(env) {
  return env.QSS_STORE.get(env.QSS_STORE.idFromName("studio"));
}

function extractPayloadJson(html) {
  const marker = "const D = ";
  const start = html.indexOf(marker);
  if (start < 0) return null;
  const i = html.indexOf("{", start);
  if (i < 0) return null;
  let depth = 0, inStr = false, escape = false, quote = "";
  for (let j = i; j < html.length; j++) {
    const ch = html[j];
    if (inStr) {
      if (escape) escape = false;
      else if (ch === "\\") escape = true;
      else if (ch === quote) inStr = false;
      continue;
    }
    if (ch === '"' || ch === "'") {
      inStr = true;
      quote = ch;
      continue;
    }
    if (ch === "{") depth++;
    else if (ch === "}") {
      depth--;
      if (depth === 0) return html.slice(i, j + 1);
    }
  }
  return null;
}

function applyPayloadJson(templateHtml, payloadJson) {
  if (templateHtml.includes("__PAYLOAD__")) {
    return templateHtml.replace("__PAYLOAD__", payloadJson);
  }
  const existing = extractPayloadJson(templateHtml);
  if (!existing) return templateHtml;
  return templateHtml.replace(existing, payloadJson);
}

function meshAspect(payload) {
  const xs = payload.x || [];
  const ys = payload.y || [];
  if (xs.length < 2 || ys.length < 2) return 0;
  let minX = xs[0], maxX = xs[0], minY = ys[0], maxY = ys[0];
  for (let i = 1; i < xs.length; i++) {
    if (xs[i] < minX) minX = xs[i];
    if (xs[i] > maxX) maxX = xs[i];
    if (ys[i] < minY) minY = ys[i];
    if (ys[i] > maxY) maxY = ys[i];
  }
  return (maxX - minX) / Math.max(maxY - minY, 1e-9);
}

function mergeMissingGeo(storedPayload, assetHtml) {
  /* Studio DO laps can lack OfficialLine; keep channels but restore geo from baked assets. */
  let stored;
  try {
    stored = JSON.parse(storedPayload);
  } catch {
    return storedPayload;
  }
  const assetRaw = extractPayloadJson(assetHtml);
  if (!assetRaw) return storedPayload;
  let asset;
  try {
    asset = JSON.parse(assetRaw);
  } catch {
    return storedPayload;
  }
  if (!Array.isArray(asset.officialLine) || asset.officialLine.length < 2) {
    return storedPayload;
  }
  /* Stale DO mesh (e.g. old Studio/runtime) — prefer the baked EV 2026 asset lap. */
  const aAsp = meshAspect(asset);
  const sAsp = meshAspect(stored);
  if (aAsp > 0 && sAsp > 0) {
    const ratio = sAsp / aAsp;
    if (ratio < 0.55 || ratio > 1.8) return assetRaw;
  }
  if (Array.isArray(stored.officialLine) && stored.officialLine.length >= 2) {
    return storedPayload;
  }
  for (const key of [
    "officialLine",
    "officialLineOriginal",
    "mapCorners",
    "mapCenter",
    "mapZoom",
    "followZoom",
    "locations",
    "activeLocation",
    "famousMaps",
    "activeMap",
    "mapScale",
  ]) {
    if (asset[key] != null) stored[key] = asset[key];
  }
  return JSON.stringify(stored);
}

async function serveLapPage(request, env, name) {
  const asset = await env.ASSETS.fetch(new URL("/" + name, request.url));
  if (!asset.ok) return asset;
  let html = await asset.text();
  const stored = await store(env).fetch(new Request("https://store/" + name));
  if (stored.ok) {
    const old = await stored.text();
    let payload = extractPayloadJson(old);
    if (payload) {
      payload = mergeMissingGeo(payload, html);
      html = applyPayloadJson(html, payload);
    }
  }
  if (!html.includes("ranking.html")) {
    html = html.replace(
      "</nav>",
      '<a href="ranking.html">Ranking</a>\n    </nav>'
    );
    if (!html.includes('href="ranking.html"')) {
      html = html.replace(
        '<a href="studio.html">Studio</a>',
        '<a href="studio.html">Studio</a>\n        <a href="ranking.html">Ranking</a>'
      );
    }
  }
  return new Response(html, {
    headers: { "content-type": "text/html; charset=utf-8", "cache-control": "no-store" },
  });
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    const path = url.pathname;

    if (path.startsWith("/api/artifact/")) {
      const name = path.slice("/api/artifact/".length);
      return store(env).fetch(new Request(new URL("https://store/" + name), request));
    }

    if (path === "/api/ranking") {
      if (request.method === "PUT") {
        return store(env).fetch(new Request(new URL("https://store/ranking.json"), request));
      }
      const stored = await store(env).fetch(new Request("https://store/ranking.json"));
      if (stored.ok) return stored;
      return new Response("[]", {
        headers: { "content-type": "application/json; charset=utf-8", "cache-control": "no-store" },
      });
    }

    if (path === "/api/defaults") {
      return env.ASSETS.fetch(new URL("/defaults.json", url));
    }

    if (path === "/hud.html" || path === "/results.html") {
      return serveLapPage(request, env, path.slice(1));
    }

    if (path === "/" || path === "/studio.html") {
      return env.ASSETS.fetch(new URL("/studio.html", request.url));
    }

    if (path === "/ranking.html") {
      return env.ASSETS.fetch(new URL("/ranking.html", request.url));
    }

    return env.ASSETS.fetch(request);
  },
};
