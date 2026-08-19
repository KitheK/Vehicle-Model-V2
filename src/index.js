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
      : "application/octet-stream";
    return new Response(buf, {
      headers: { "content-type": type, "cache-control": "no-store" },
    });
  }
}

function store(env) {
  return env.QSS_STORE.get(env.QSS_STORE.idFromName("studio"));
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    const path = url.pathname;

    if (path.startsWith("/api/artifact/")) {
      const name = path.slice("/api/artifact/".length);
      return store(env).fetch(new Request(new URL("https://store/" + name), request));
    }

    if (path === "/api/defaults") {
      return env.ASSETS.fetch(new URL("/defaults.json", url));
    }

    if (path === "/hud.html" || path === "/results.html") {
      const stored = await store(env).fetch(new Request("https://store/" + path.slice(1)));
      if (stored.ok) return stored;
    }

    if (path === "/" || path === "/studio.html") {
      return env.ASSETS.fetch(new URL("/studio.html", request.url));
    }

    return env.ASSETS.fetch(request);
  },
};
