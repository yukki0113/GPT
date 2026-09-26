"use strict";

const CACHE_NAME = "momotaro-newspaper-shell-v20";
const APP_SHELL = [
  "./",
  "./index.html",
  "./newspaper.html",
  "./predictions.html",
  "./fact-lite.html",
  "./manifest.webmanifest",
  "./momotaro.css?v=6",
  "./momotaro.js?v=17",
  "./predictions.js?v=6",
  "../style.css",
  "../newspaper.css?v=3",
  "../newspaper-v4.css?v=9",
  "../newspaper-v5.css?v=1",
  "../newspaper-v6.css?v=1",
  "../newspaper-v9.css?v=2",
  "../newspaper.js?v=3",
  "../newspaper-v2.js?v=3",
  "../newspaper-day.js?v=4",
  "../newspaper-v4.js?v=8",
  "../newspaper-v5.js?v=1",
  "../newspaper-v6.js?v=1",
  "../newspaper-v7.js?v=4",
  "../newspaper-v8.js?v=1",
  "../newspaper-v9.js?v=1",
  "../newspaper-v10.js?v=2",
  "../fact-lite.js?v=22",
  "../fact-lite-v3.js?v=4",
  "../fact-lite-sort.js?v=20",
  "../vendor/sql-wasm.js",
  "../vendor/sql-wasm.wasm"
];

self.addEventListener("install", function (event) {
  event.waitUntil(caches.open(CACHE_NAME).then(function (cache) { return cache.addAll(APP_SHELL); }));
  self.skipWaiting();
});

self.addEventListener("activate", function (event) {
  event.waitUntil(caches.keys().then(function (keys) {
    return Promise.all(keys.filter(function (key) {
      return key.startsWith("momotaro-newspaper-shell-") && key !== CACHE_NAME;
    }).map(function (key) { return caches.delete(key); }));
  }));
  self.clients.claim();
});

self.addEventListener("fetch", function (event) {
  if (event.request.method !== "GET") return;
  const url = new URL(event.request.url);
  if (url.origin !== self.location.origin || url.pathname.includes("/data/")) return;

  event.respondWith(fetch(event.request).then(function (response) {
    if (response && response.status === 200) {
      const copy = response.clone();
      caches.open(CACHE_NAME).then(function (cache) { cache.put(event.request, copy); });
    }
    return response;
  }).catch(function () {
    return caches.match(event.request).then(function (cached) {
      if (cached) return cached;
      if (event.request.mode === "navigate") return caches.match("./newspaper.html");
      throw new Error("Offline and no cached response");
    });
  }));
});
