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

async function serveLapPage(request, env, name) {
  const asset = await env.ASSETS.fetch(new URL("/" + name, request.url));
  if (!asset.ok) return asset;
  let html = await asset.text();
  const stored = await store(env).fetch(new Request("https://store/" + name));
  if (stored.ok) {
    const old = await stored.text();
    const payload = extractPayloadJson(old);
    if (payload) html = applyPayloadJson(html, payload);
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
