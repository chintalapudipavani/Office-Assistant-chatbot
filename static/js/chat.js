(function () {
  "use strict";

  var config = document.getElementById("chat-config");
  var askUrl = config.dataset.askUrl;
  var chatUrl = config.dataset.chatUrl;
  var sessionId = config.dataset.sessionId || null;

  var windowEl = document.getElementById("chat-window");
  var emptyState = document.getElementById("empty-state");
  var input = document.getElementById("question");
  var sendBtn = document.getElementById("send-btn");
  var errorBox = document.getElementById("chat-error");
  var counter = document.getElementById("char-count");
  var csrfToken = document.querySelector("[name=csrfmiddlewaretoken]").value;
  var busy = false;

  function appendInline(parent, text) {
    text.split(/(\*\*[^*]+\*\*)/g).forEach(function (part) {
      if (/^\*\*[^*]+\*\*$/.test(part)) {
        var b = document.createElement("strong");
        b.textContent = part.slice(2, -2);
        parent.appendChild(b);
      } else if (part) {
        parent.appendChild(document.createTextNode(part));
      }
    });
  }

  // Builds DOM nodes with textContent only (never innerHTML), so answers cannot inject HTML.
  function renderFormatted(container, text) {
    var ul = null;
    text.split(/\r?\n/).forEach(function (line) {
      var m = line.match(/^\s*(?:[-*\u2022])\s+(.*)$/);
      if (m) {
        if (!ul) { ul = document.createElement("ul"); ul.className = "mb-1"; container.appendChild(ul); }
        var li = document.createElement("li");
        appendInline(li, m[1]);
        ul.appendChild(li);
      } else {
        ul = null;
        if (line.trim() === "") { return; }
        var p = document.createElement("p");
        p.className = "mb-1";
        appendInline(p, line);
        container.appendChild(p);
      }
    });
  }

  function addMessage(msg) {
    if (emptyState) { emptyState.classList.add("d-none"); }
    var bubble = document.createElement("div");
    if (msg.role === "user") {
      bubble.className = "bubble bubble-user mb-2";
      bubble.textContent = msg.content;
    } else {
      bubble.className = "bubble bubble-bot mb-2";
      if (msg.is_error) { bubble.classList.add("is-error"); }
      else if (!msg.answer_found) { bubble.classList.add("not-found"); }
      renderFormatted(bubble, msg.content);
          }
    windowEl.appendChild(bubble);
    windowEl.scrollTop = windowEl.scrollHeight;
    return bubble;
  }

  function showError(text) {
    errorBox.textContent = text;
    errorBox.classList.remove("d-none");
  }

  function setBusy(state) {
    busy = state;
    sendBtn.disabled = state;
    input.disabled = state;
    sendBtn.textContent = state ? "Thinking..." : "Send";
  }

  function send(question) {
    question = question.trim();
    if (!question || busy) { return; }
    errorBox.classList.add("d-none");
    addMessage({ role: "user", content: question });
    input.value = "";
    counter.textContent = "0";
    setBusy(true);

    var typing = document.createElement("div");
    typing.className = "typing mb-2";
    typing.textContent = "Searching the documents...";
    windowEl.appendChild(typing);
    windowEl.scrollTop = windowEl.scrollHeight;

    fetch(askUrl, {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-CSRFToken": csrfToken },
      credentials: "same-origin",
      body: JSON.stringify({ question: question, session_id: sessionId })
    })
      .then(function (response) {
        return response.json().catch(function () { return {}; }).then(function (data) {
          return { ok: response.ok, status: response.status, data: data };
        });
      })
      .then(function (res) {
        typing.remove();
        if (!res.ok) {
          showError(res.data.error || "The server returned an error (" + res.status + "). Please try again.");
          return;
        }
        sessionId = String(res.data.session_id);
        history.replaceState(null, "", chatUrl + "?session=" + sessionId);
        addMessage({
          role: "assistant", content: res.data.answer, sources: res.data.sources,
          answer_found: res.data.answer_found, is_error: res.data.is_error
        });
      })
      .catch(function () {
        typing.remove();
        showError("Could not reach the server. Check that it is running and try again.");
      })
      .finally(function () {
        setBusy(false);
        input.focus();
      });
  }

  sendBtn.addEventListener("click", function () { send(input.value); });
  input.addEventListener("keydown", function (e) {
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(input.value); }
  });
  input.addEventListener("input", function () { counter.textContent = String(input.value.length); });
  document.querySelectorAll(".sample-q").forEach(function (btn) {
    btn.addEventListener("click", function () { send(btn.textContent); });
  });

  var initial = JSON.parse(document.getElementById("initial-messages").textContent);
  initial.forEach(addMessage);
})();
