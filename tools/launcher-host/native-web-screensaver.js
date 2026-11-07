/* Coordinate Free My TV's photo saver with VIDAA's existing idle protection.
 * Uses the stock launcher request contract; never writes screensaver settings.
 */
(function (root) {
  "use strict";
  function createScreenSaver(sdk) {
    var request = "n2o://screen-saver/art-start-screensaver";
    var initialized = "o2n://sdk/init-finished";
    return function register(hold) {
      if (typeof hold !== "function") throw new Error("Screensaver predicate is required");
      var released = false;
      function home() { return !released && sdk.router.isCurrentPathEqualTo("/Launcher"); }
      function beforeStart() {
        if (!home()) return false;
        try { return !hold(); } catch { return true; }
      }
      function arm() {
        // Omit duration: the vendor honors its existing user-selected timeout,
        // disable switch, model restrictions, resume state and kids-mode guard.
        if (home()) sdk.message.emit(request, { beforeStart: beforeStart });
      }
      sdk.message.on(initialized, arm);
      try { arm(); }
      catch (error) { released = true; sdk.message.off(initialized, arm); throw error; }
      return function release() {
        if (released) return;
        released = true;
        sdk.message.off(initialized, arm);
        // Do not clear the shared vendor timer: another page may now own it.
        // Our old callback becomes inert, while other owners remain untouched.
      };
    };
  }
  if (typeof module !== "undefined" && module.exports) module.exports = createScreenSaver;
  else root.AlvidaaNativeWebScreenSaver = createScreenSaver;
}(typeof self !== "undefined" ? self : this));
