"use strict";

const CACHE_NAME = "jrdb-pwa-shell-v17";
const APP_SHELL = [
  "./",
  "./index.html",
  "./fact-lite.html",
  "./style.css",
  "./app.js",
  "./fact-lite.js?v=17",
  "./fact-lite-sort.js?v=17",
  "./manifest.webmanifest",
  "./vendor/sql-wasm.js",
  "./vendor/sql-wasm.wasm"
];

/**
 * PWA shell と SQLite 実行エンジンを事前キャッシュする。
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
 * data/ 配下は同期管理対象なのでService Workerへ保存しない。
 *
 * navigation / app shell はオンライン時に network-first とし、
 * UI更新後も旧cacheを握り続けないようにする。
 * オフライン時は最後に取得済みのshellへフォールバックする。
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

  if (requestUrl.pathname.includes("/data/")) {
    return;
  }

  event.respondWith(
    fetch(request)
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
        return caches.match(request).then(function (cachedResponse) {
          if (cachedResponse) {
            return cachedResponse;
          }

          if (request.mode === "navigate") {
            if (requestUrl.pathname.endsWith("/fact-lite.html")) {
              return caches.match("./fact-lite.html");
            }
            return caches.match("./index.html");
          }

          throw new Error("Offline and no cached response");
        });
      })
  );
});
