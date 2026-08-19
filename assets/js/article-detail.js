(function () {
  'use strict';

  var commentReply = document.getElementById('commentReply');
  if (!commentReply) {
    return;
  }

  document.querySelectorAll('a[href="#commentForm"], a[href="#commentReply"]').forEach(function (link) {
    link.addEventListener('click', function () {
      commentReply.open = true;
    });
  });
})();
