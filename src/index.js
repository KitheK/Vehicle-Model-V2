import { Container, getContainer } from "@cloudflare/containers";

export class QssContainer extends Container {
  defaultPort = 18080;
  sleepAfter = "15m";
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    if (url.pathname === "/car.glb") {
      return env.ASSETS.fetch(request);
    }
    return getContainer(env.QSS_CONTAINER, "studio").fetch(request);
  },
};
