const CACHE = "kayi-shell-v18-20260810-de";
const OFFLINE = "/app/";
const ASSETS = ["/static/css/app.css?v=20260809-0300", "/static/js/app.js?v=20260809-0300", "/static/manifest.webmanifest", "/privacy/", "/terms/"];
self.addEventListener("install", event => event.waitUntil(caches.open(CACHE).then(cache => cache.addAll(ASSETS)).then(() => self.skipWaiting())));
self.addEventListener("activate", event => event.waitUntil(caches.keys().then(keys => Promise.all(keys.filter(key => key !== CACHE).map(key => caches.delete(key)))).then(() => self.clients.claim())));
self.addEventListener("fetch", event => {
  if (event.request.method !== "GET") return;
  const url = new URL(event.request.url);
  if (url.pathname.startsWith("/api/")) {
    event.respondWith(fetch(event.request));
    return;
  }
  event.respondWith(fetch(event.request).then(response => {
    if (response.ok && response.type === "basic") caches.open(CACHE).then(cache => cache.put(event.request, response.clone()));
    return response;
  }).catch(() => caches.match(event.request).then(cached => cached || caches.match(OFFLINE))));
});

self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  const target = event.notification.data?.url || "/";
  event.waitUntil(clients.matchAll({type:"window",includeUncontrolled:true}).then((windows)=>{
    for(const client of windows){if("focus" in client){client.navigate(target);return client.focus();}}
    return clients.openWindow ? clients.openWindow(target) : undefined;
  }));
});
