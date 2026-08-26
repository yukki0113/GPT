"use strict";

/**
 * JRDB PWA bootstrap.
 *
 * 現段階では Pages 配信、Service Worker、OPFS 利用可否の確認だけを行う。
 * SQLite 同期・sql.js 初期化・条件集計は次フェーズで追加する。
 */

const networkBadge = document.getElementById("network-badge");
const opfsStatus = document.getElementById("opfs-status");
const swStatus = document.getElementById("sw-status");

/**
 * ネットワーク状態表示を更新する。
 */
function updateNetworkStatus() {
  if (navigator.onLine) {
    networkBadge.textContent = "オンライン";
    networkBadge.classList.add("online");
    networkBadge.classList.remove("offline");
    return;
  }

  networkBadge.textContent = "オフライン";
  networkBadge.classList.add("offline");
  networkBadge.classList.remove("online");
}

/**
 * OPFS の利用可否を確認する。
 */
async function checkOpfsSupport() {
  if (!navigator.storage || !navigator.storage.getDirectory) {
    opfsStatus.textContent = "非対応";
    return;
  }

  try {
    await navigator.storage.getDirectory();
    opfsStatus.textContent = "利用可能";
  } catch (error) {
    console.error("OPFS check failed", error);
    opfsStatus.textContent = "利用不可";
  }
}

/**
 * Service Worker を登録する。
 */
async function registerServiceWorker() {
  if (!("serviceWorker" in navigator)) {
    swStatus.textContent = "非対応";
    return;
  }

  try {
    await navigator.serviceWorker.register("./service-worker.js", {
      scope: "./"
    });
    swStatus.textContent = "登録済み";
  } catch (error) {
    console.error("Service Worker registration failed", error);
    swStatus.textContent = "登録失敗";
  }
}

window.addEventListener("online", updateNetworkStatus);
window.addEventListener("offline", updateNetworkStatus);

updateNetworkStatus();
checkOpfsSupport();
registerServiceWorker();
