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

function addPaperTable(papers) {
  const el = document.createElement("div");
  el.className = "msg assistant";
  
  let tableHTML = `
    <div class="bubble">
      <div class="papers-table-container">
        <table class="papers-table">
          <thead>
            <tr>
              <th>Title</th>
              <th>Authors</th>
              <th>Year</th>
              <th>Abstract</th>
              <th>DOI</th>
              <th>Links</th>
            </tr>
          </thead>
          <tbody>
  `;
  
  papers.forEach(paper => {
    const title = escapeHtml(paper.title || "Untitled");
    const authors = escapeHtml(paper.authors || "");
    const year = paper.year || "";
    const abstract = escapeHtml(paper.abstract || "");
    const doi = escapeHtml(paper.doi || "");
    const venue = escapeHtml(paper.venue || "");
    
    // Create links
    let links = [];
    if (paper.doi_url) {
      links.push(`<a href="${escapeHtml(paper.doi_url)}" target="_blank" class="link-btn doi-link">DOI</a>`);
    }
    if (paper.pubmed_url) {
      links.push(`<a href="${escapeHtml(paper.pubmed_url)}" target="_blank" class="link-btn pubmed-link">PubMed</a>`);
    }
    if (paper.pdf_path) {
      links.push(`<a href="${escapeHtml(paper.pdf_path)}" target="_blank" class="link-btn pdf-link">PDF</a>`);
    }
    if (paper.url && !paper.doi_url && !paper.pubmed_url) {
      links.push(`<a href="${escapeHtml(paper.url)}" target="_blank" class="link-btn url-link">Link</a>`);
    }
    
    const linksHTML = links.length > 0 ? links.join(" ") : "—";
    
    // Truncate abstract for display
    const shortAbstract = abstract.length > 200 ? abstract.substring(0, 200) + "..." : abstract;
    
    tableHTML += `
      <tr>
        <td class="title-cell">
          <div class="paper-title">${title}</div>
          ${venue ? `<div class="paper-venue">${venue}</div>` : ""}
        </td>
        <td class="authors-cell">${authors}</td>
        <td class="year-cell">${year}</td>
        <td class="abstract-cell">
          <div class="abstract-short">${shortAbstract}</div>
          ${abstract.length > 200 ? `<button class="expand-btn" onclick="toggleAbstract(this)">Show more</button>` : ""}
          <div class="abstract-full" style="display: none;">${abstract}</div>
        </td>
        <td class="doi-cell">${doi}</td>
        <td class="links-cell">${linksHTML}</td>
      </tr>
    `;
  });
  
  tableHTML += `
          </tbody>
        </table>
      </div>
    </div>
  `;
  
  el.innerHTML = tableHTML;
  chat.appendChild(el);
  chat.scrollTop = chat.scrollHeight;
}

function toggleAbstract(btn) {
  const row = btn.closest('tr');
  const shortAbstract = row.querySelector('.abstract-short');
  const fullAbstract = row.querySelector('.abstract-full');
  
  if (fullAbstract.style.display === 'none') {
    shortAbstract.style.display = 'none';
    fullAbstract.style.display = 'block';
    btn.textContent = 'Show less';
  } else {
    shortAbstract.style.display = 'block';
    fullAbstract.style.display = 'none';
    btn.textContent = 'Show more';
  }
}

function showLoadingIndicator() {
  const loadingEl = document.createElement("div");
  loadingEl.className = "loading-indicator show";
  loadingEl.innerHTML = `
    <div class="loading-spinner"></div>
    <span>Running literature review... This may take a moment.</span>
  `;
  chat.appendChild(loadingEl);
  chat.scrollTop = chat.scrollHeight;
  return loadingEl;
}

function hideLoadingIndicator(loadingEl) {
  if (loadingEl && loadingEl.parentNode) {
    loadingEl.parentNode.removeChild(loadingEl);
  }
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
  const paperLimit = Math.max(1, Math.min(50, parseInt(document.getElementById("paper_limit")?.value || "10")));

  addMessage("user", text);
  sendBtn.disabled = true;
  input.value = "";

  // Show loading indicator for literature mode
  let loadingIndicator = null;
  if (mod === "literature") {
    loadingIndicator = showLoadingIndicator();
  }

  try {
    const res = await fetch("/api/message", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        conversation_id: conversationId,
        text,
        modality: mod,
        project_id: pid || "",
        paper_limit: paperLimit
      })
    });
    const data = await res.json();
    
    // Hide loading indicator
    if (loadingIndicator) {
      hideLoadingIndicator(loadingIndicator);
    }
    
    // Handle structured response for literature mode
    if (data.papers && data.papers.length > 0) {
      addMessage("assistant", data.message);
      addPaperTable(data.papers);
    } else {
      // Handle simple reply for RAG mode or when no papers
      addMessage("assistant", data.reply || data.message);
    }
  } catch (error) {
    // Hide loading indicator on error
    if (loadingIndicator) {
      hideLoadingIndicator(loadingIndicator);
    }
    addMessage("assistant", `Error: ${error.message}`);
  }
  
  sendBtn.disabled = false;
}


document.querySelectorAll('input[name="mod"]').forEach(r => {
  r.addEventListener("change", startConversation);
});
sendBtn.addEventListener("click", sendMessage);
input.addEventListener("keydown", (e) => { if (e.key === "Enter") sendMessage(); });

startConversation();
