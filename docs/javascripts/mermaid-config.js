// Intercept when the Mermaid CDN script sets window.mermaid and wrap
// mermaid.initialize so that er.layoutDirection is always applied.
// This is needed because Material's strict securityLevel blocks %%{init}%%
// directives, so per-diagram config cannot override the layout direction.
(function () {
  var _mermaid;
  Object.defineProperty(window, "mermaid", {
    configurable: true,
    enumerable: true,
    get: function () {
      return _mermaid;
    },
    set: function (val) {
      if (val && typeof val.initialize === "function") {
        var orig = val.initialize.bind(val);
        val.initialize = function (config) {
          config = Object.assign({}, config);
          config.er = Object.assign({ layoutDirection: "RL" }, config.er || {});
          return orig(config);
        };
      }
      _mermaid = val;
      Object.defineProperty(window, "mermaid", {
        configurable: true,
        enumerable: true,
        writable: true,
        value: _mermaid,
      });
    },
  });
})();
