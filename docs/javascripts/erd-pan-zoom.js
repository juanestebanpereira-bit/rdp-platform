(function () {
  function applyPanZoom(svgEl) {
    // Avoid double-initialising
    if (svgEl.dataset.panZoom) return;
    svgEl.dataset.panZoom = "1";

    // Give the container a fixed height so svg-pan-zoom has room to work
    var container = svgEl.closest(".mermaid");
    if (container && !container.style.height) {
      container.style.height = "520px";
    }

    svgPanZoom(svgEl, {
      zoomEnabled: true,
      controlIconsEnabled: true,
      fit: true,
      center: true,
      minZoom: 0.2,
      maxZoom: 10,
    });
  }

  // Watch for Mermaid inserting SVGs into .mermaid containers
  var observer = new MutationObserver(function (mutations) {
    mutations.forEach(function (mutation) {
      mutation.addedNodes.forEach(function (node) {
        if (node.nodeType !== 1) return;
        if (node.tagName === "svg" && node.closest && node.closest(".mermaid")) {
          applyPanZoom(node);
        }
        // Catch SVGs nested deeper (e.g. after re-render on navigation)
        if (node.querySelectorAll) {
          node.querySelectorAll(".mermaid svg").forEach(applyPanZoom);
        }
      });
    });
  });

  function start() {
    // Apply to any diagrams already on the page
    document.querySelectorAll(".mermaid svg").forEach(applyPanZoom);
    // Watch for future renders (SPA navigation, lazy render)
    observer.observe(document.body, { childList: true, subtree: true });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", start);
  } else {
    start();
  }
})();
