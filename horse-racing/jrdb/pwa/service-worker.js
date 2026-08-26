"use strict";

const CACHE_NAME = "jrdb-pwa-shell-v2";
const SQL_JS_URL = "https://cdn.jsdelivr.net/npm/sql.js@1.14.1/dist/sql-wasm.js";
const SQL_WASM_URL = "https://cdn.jsdelivr.net/npm/sql.js@1.14.1/dist/sql-wasm.wasm";
const APP_SHELL = [
  "./",
  "./index.html",
  "./style.css",
  "./app.js",
  "./manifest.webmanifest",
  SQL_JS_URL,
  SQL_WASM_URL
];

self.addEventListener("install", function (event) {
  event.waitUntil(caches.open(CACHE_NAME).then(function (cache) { return cache.addAll(APP_SHELL); }));
  self.skipWaiting();
});

self.addEventListener("activate", function (event) {
  event.waitUntil(
    caches.keys().then(function (cacheNames) {
      return Promise.all(cacheNames.map(function (cacheName) {
        if (cacheName === CACHE_NAME) {
          return Promise.resolve(false);
        }
        return caches.delete(cacheName);
      }));
    })
  );
  self.clients.claim();
});

self.addEventListener("fetch", function (event) {
  const request = event.request;
  if (request.method !== "GET") {
    return;
  }

  event.respondWith(
    caches.match(request).then(function (cachedResponse) {
      if (cachedResponse) {
        return cachedResponse;
      }

      return fetch(request).then(function (networkResponse) {
        if (!networkResponse || (networkResponse.status !== 200 && networkResponse.type !== "opaque")) {
          return networkResponse;
        }

        const responseCopy = networkResponse.clone();
        caches.open(CACHE_NAME).then(function (cache) { cache.put(request, responseCopy); });
        return networkResponse;
      }).catch(function () {
        if (request.mode === "navigate") {
          return caches.match("./index.html");
        }
        throw new Error("Offline and no cached response");
      });
    })
  );
});
