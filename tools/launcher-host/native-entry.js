/* Runs after the private, unmodified vendor launcher bundle and our frontend.
 * Replace one component, not the shell or the launcher's other page contracts.
 */
(function (root) {
  "use strict";
  var original = root._V_M_ && root._V_M_.launcher;
  if (typeof original !== "function") throw new Error("Stock launcher factory is required");
  var wrapped = null;
  root._V_M_.launcher = function () {
    if (wrapped) return wrapped;
    var stock = original();
    var sdk = new root._V_SDK_.vre.SDK("launcher", { storagePrefix: "Alvidaa" });
    var route = stock.route.filter(function (r) { return r.path === "/Launcher"; })[0];
    if (!route) throw new Error("Stock Home route is missing");
    route.component = root.AlvidaaFreeMyTV(sdk);
    wrapped = stock;
    return stock;
  };
}(self));
