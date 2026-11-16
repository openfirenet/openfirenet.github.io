// Download page: puts the installer for the visitor's system first, and shows the number of the latest version.
(function () {
  var list = document.querySelector('.dl-list');
  if (!list) return;
  var ua = navigator.userAgent;
  var os = null;
  // iPads report themselves as Macs: a Mac with a touch screen is taken for a tablet.
  if (/Android|iPhone|iPad|iPod/.test(ua) || (/Mac/.test(ua) && navigator.maxTouchPoints > 1)) os = 'mobile';
  else if (/Windows/.test(ua)) os = 'windows';
  else if (/Mac/.test(ua)) os = 'mac';
  else if (/Linux|X11|CrOS/.test(ua)) os = 'linux';
  if (os === 'mobile') {
    var phone = document.querySelector('.dl-phone');
    if (phone) phone.hidden = false;
  } else if (os) {
    var card = list.querySelector('.dl[data-os="' + os + '"]');
    if (card) {
      card.classList.add('primary');
      var rec = card.querySelector('.dl-rec');
      if (rec) rec.hidden = false;
      list.insertBefore(card, list.firstChild);
    }
  }
  var version = document.querySelector('.dl-version');
  if (!version || !window.fetch) return;
  fetch('https://api.github.com/repos/openfirenet/open-firenet-installer/releases/latest')
    .then(function (r) { return r.ok ? r.json() : null; })
    .then(function (rel) {
      if (!rel || !rel.tag_name) return;
      version.textContent = version.getAttribute('data-prefix') + ' ' + rel.tag_name.replace(/^v/, '');
      version.hidden = false;
    })
    .catch(function () { /* the links work without the version number */ });
})();
