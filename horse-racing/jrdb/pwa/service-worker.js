"use strict";

const CACHE_NAME = "jrdb-pwa-shell-v34";
const APP_SHELL = [
  "./",
  "./index.html",
  "./fact-lite.html",
  "./newspaper.html",
  "./style.css",
  "./newspaper.css?v=3",
  "./newspaper-v4.css?v=6",
  "./newspaper-v5.css?v=1",
  "./newspaper-v6.css?v=1",
  "./fact-lite.js?v=17",
  "./fact-lite-sort.js?v=18",
  "./newspaper.js?v=2",
  "./newspaper-v2.js?v=3",
  "./newspaper-day.js?v=3",
  "./newspaper-v4.js?v=7",
  "./newspaper-v5.js?v=1",
  "./newspaper-v6.js?v=1",
  "./manifest.webmanifest",
  "./vendor/sql-wasm.js",
  "./vendor/sql-wasm.wasm"
];

self.addEventListener("install", function (event) {
  event.waitUntil(
    caches.open(CACHE_NAME).then(function (cache) {
      return cache.addAll(APP_SHELL);
    })
  );
  self.skipWaiting();
});

self.addEventListener("activate", function (event) {
  event.waitUntil(
    caches.keys().then(function (cacheNames) {
      return Promise.all(
        cacheNames.map(function (cacheName) {
          if (cacheName === CACHE_NAME) return Promise.resolve(false);
          return caches.delete(cacheName);
        })
      );
    })
  );
  self.clients.claim();
});

self.addEventListener("fetch", function (event) {
  const request = event.request;
  if (request.method !== "GET") return;

  const requestUrl = new URL(request.url);
  if (requestUrl.origin !== self.location.origin) return;
  if (requestUrl.pathname.includes("/data/")) return;

  event.respondWith(
    fetch(request)
      .then(function (networkResponse) {
        if (!networkResponse || networkResponse.status !== 200) return networkResponse;
        const responseCopy = networkResponse.clone();
        caches.open(CACHE_NAME).then(function (cache) {
          cache.put(request, responseCopy);
        });
        return networkResponse;
      })
      .catch(function () {
        return caches.match(request).then(function (cachedResponse) {
          if (cachedResponse) return cachedResponse;
          if (request.mode === "navigate") {
            if (requestUrl.pathname.endsWith("/newspaper.html")) return caches.match("./newspaper.html");
            return caches.match("./fact-lite.html");
          }
          throw new Error("Offline and no cached response");
        });
      })
  );
});
