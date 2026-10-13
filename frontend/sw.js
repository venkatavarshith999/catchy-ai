// Only paths from this public manifest can enter the offline cache. APIs never do.
const CACHE = "catchy-shell-v2.1";
let allowed;
async function publicPaths() {
  if (allowed) return allowed;
  let response;
  try {
    response = await fetch("/shell-assets.json", { cache: "no-cache" });
    if (!response.ok) throw Error("manifest");
  } catch {
    response = await caches.match("/shell-assets.json");
  }
  if (!response) throw Error("Offline shell unavailable");
  allowed = await response.json();
  return allowed;
}
self.addEventListener("install", (event) =>
  event.waitUntil(
    publicPaths().then(async (paths) => {
      const cache = await caches.open(CACHE);
      await cache.addAll(["/shell-assets.json", ...paths]);
    }),
  ),
);
self.addEventListener("activate", (event) =>
  event.waitUntil(
    caches
      .keys()
      .then((keys) =>
        Promise.all(
          keys
            .filter((key) => key.startsWith("catchy-shell-") && key !== CACHE)
            .map((key) => caches.delete(key)),
        ),
      )
      .then(() => self.clients.claim()),
  ),
);
self.addEventListener("fetch", (event) => {
  const url = new URL(event.request.url);
  if (
    event.request.method !== "GET" ||
    url.origin !== self.location.origin ||
    url.pathname.startsWith("/api/")
  )
    return;
  event.respondWith(
    (async () => {
      const paths = await publicPaths();
      if (!paths.includes(url.pathname)) return fetch(event.request);
      try {
        const response = await fetch(event.request);
        if (response.ok) {
          const cache = await caches.open(CACHE);
          await cache.put(url.pathname, response.clone());
        }
        return response;
      } catch {
        return (await caches.match(url.pathname)) || Response.error();
      }
    })(),
  );
});
