"use strict";

const CACHE_NAME = "jrdb-pwa-shell-v4";
const APP_SHELL = [
  "./",
  "./index.html",
  "./style.css",
  "./app.js",
  "./manifest.webmanifest"
];

/**
 * PWA shell を事前キャッシュする。
 */
self.addEventListener("install", function (event) {
  event.waitUntil(
    caches.open(CACHE_NAME).then(function (cache) {
      return cache.addAll(APP_SHELL);
    })
  );

  self.skipWaiting();
});

/**
 * 古い shell cache を削除する。
 */
self.addEventListener("activate", function (event) {
  event.waitUntil(
    caches.keys().then(function (cacheNames) {
      return Promise.all(
        cacheNames.map(function (cacheName) {
          if (cacheName === CACHE_NAME) {
            return Promise.resolve(false);
          }

          return caches.delete(cacheName);
        })
      );
    })
  );

  self.clients.claim();
});

/**
 * 同一originのGETは cache-first で処理する。
 * navigation失敗時は index.html を返し、オフライン起動を維持する。
 */
self.addEventListener("fetch", function (event) {
  const request = event.request;

  if (request.method !== "GET") {
    return;
  }

  const requestUrl = new URL(request.url);

  if (requestUrl.origin !== self.location.origin) {
    return;
  }

  event.respondWith(
    caches.match(request).then(function (cachedResponse) {
      if (cachedResponse) {
        return cachedResponse;
      }

      return fetch(request)
        .then(function (networkResponse) {
          if (!networkResponse || networkResponse.status !== 200) {
            return networkResponse;
          }

          const responseCopy = networkResponse.clone();
          caches.open(CACHE_NAME).then(function (cache) {
            cache.put(request, responseCopy);
          });

          return networkResponse;
        })
        .catch(function () {
          if (request.mode === "navigate") {
            return caches.match("./index.html");
          }

          throw new Error("Offline and no cached response");
        });
    })
  );
});
