let conversationId = null;

const chat = document.getElementById("chat");
const input = document.getElementById("input");
const sendBtn = document.getElementById("send");
const convMeta = document.getElementById("conv-meta");

function escapeHtml(str) {
  return str.replace(/[&<>"']/g, s => ({
    "&":"&amp;","<":"&lt;",">":"&gt;","\"":"&quot;","'":"&#39;"
  }[s]));
}
function addMessage(role, text) {
  const el = document.createElement("div");
  el.className = `msg ${role}`;
  el.innerHTML = `<div class="bubble">${escapeHtml(text)}</div>`;
  chat.appendChild(el);
  chat.scrollTop = chat.scrollHeight;
}

async function startConversation() {
  const mod = document.querySelector('input[name="mod"]:checked').value;
  const res = await fetch("/api/start", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ modality: mod })
  });
  const data = await res.json();
  conversationId = data.conversation_id;
  convMeta.textContent = `Conversation #${conversationId} · Mode: ${mod}`;
  chat.innerHTML = "";
  addMessage("assistant", `Mode set to "${mod}". How can I help?`);
}

async function sendMessage() {
  const text = input.value.trim();
  if (!text || !conversationId) return;

  const mod = document.querySelector('input[name="mod"]:checked').value;
  const pid = (document.getElementById("project_id")?.value || "").trim();

  addMessage("user", text);
  sendBtn.disabled = true;
  input.value = "";

  const res = await fetch("/api/message", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      conversation_id: conversationId,
      text,
      modality: mod,
      project_id: pid || ""
    })
  });
  const data = await res.json();
  addMessage("assistant", data.reply);
  sendBtn.disabled = false;
}


document.querySelectorAll('input[name="mod"]').forEach(r => {
  r.addEventListener("change", startConversation);
});
sendBtn.addEventListener("click", sendMessage);
input.addEventListener("keydown", (e) => { if (e.key === "Enter") sendMessage(); });

startConversation();
