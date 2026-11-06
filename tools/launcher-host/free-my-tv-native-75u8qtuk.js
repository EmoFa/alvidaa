/* 75U8QTUK / V0000.09.60I.Q0813 adjustments to the shared native frontend.
 *
 * The shared free-my-tv-native.js is left untouched for the 55A7KAU lane.
 * Differences on this build, all source-verified against private vendor
 * copies in firmware/75u8qtuk/:
 *   - app icons are vendor HTTPS URLs on https://img.vidaahub.com/ (feed
 *     tiles) or app-service `img`/`httpIcon`/`icon_*` fields; the shared
 *     localIcon() rejects them, so every tile would lose its art.
 *   - KEYMAP.RETURN does not exist (BACK === BACKSPACE === 8); the shared
 *     handleKey comparison with undefined is harmless and stays as-is.
 *   - sdk.apc.CMDMETHOD / sdk.tts are populated by vendor services at
 *     runtime; guard the two shared methods that dereference them so a late
 *     or missing service degrades to a plain (silent) Home instead of a
 *     thrown key handler.
 */
(function (root) {
  "use strict";
  var base = root.AlvidaaFreeMyTV;
  if (typeof base !== "function") throw new Error("Shared native frontend is required");

  var LOCAL = /^(var\/local\/storeAppIcon\/|file:\/\/\/|\/(?!\/)|data:image\/(png|jpeg|webp);base64,)/i;
  var VENDOR_ICON = /^https:\/\/img\.vidaahub\.com\//i;

  root.AlvidaaFreeMyTV = function (sdk) {
    var component = base(sdk);
    var methods = component.methods;

    methods.localIcon = function (app) {
      var candidates = [app.img, app.httpIcon, app.icon_web_url, app.icon_local_url,
        app.presetImg, app.icon, app.appIcon];
      for (var i = 0; i < candidates.length; i++) {
        var value = candidates[i];
        if (typeof value !== "string" || !value) continue;
        if (VENDOR_ICON.test(value)) return value;
        if (LOCAL.test(value)) {
          return value.indexOf("var/local/storeAppIcon/") === 0 ? "file:///hisenseUI/" + value : value;
        }
      }
      return "";
    };

    var announce = methods.announce;
    methods.announce = function () {
      try { return announce.call(this); } catch (_) { return undefined; }
    };

    var routeFocus = methods.routeFocus;
    methods.routeFocus = function () {
      try { return routeFocus.call(this); }
      catch (_) {
        this.view = "home";
        this.zone = "shelf";
        this.index = 0;
        this.moving = false;
      }
    };

    return component;
  };
}(self));
