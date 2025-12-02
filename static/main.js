let conversationId = null;

const chat = document.getElementById("chat");
const input = document.getElementById("input");
const sendBtn = document.getElementById("send");
const convMeta = document.getElementById("conv-meta");
const exportBtn = document.getElementById("export-chat");
const helpBtn = document.getElementById("help-shortcuts");
const themeBtn = document.getElementById("theme-toggle");
const settingsBtn = document.getElementById("settings-button");

// Sidebar elements
const sidebar = document.getElementById("sidebar");
const sidebarToggle = document.getElementById("sidebar-toggle");
const sidebarToggleHeader = document.getElementById("sidebar-toggle-header");
const sidebarToggleFloat = document.getElementById("sidebar-toggle-float");
const sidebarProjects = document.getElementById("sidebar-projects");
const sidebarSearch = document.getElementById("sidebar-search");
const deleteProjectBtn = document.getElementById("delete-project");

function escapeHtml(str) {
  return str.replace(/[&<>"']/g, s => ({
    "&":"&amp;","<":"&lt;",">":"&gt;","\"":"&quot;","'":"&#39;"
  }[s]));
}

function formatMessage(text) {
  // Simple markdown-like formatting
  return text
    .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
    .replace(/\*(.*?)\*/g, '<em>$1</em>')
    .replace(/• (.*?)(?=\n|$)/g, '<div class="bullet-point">• $1</div>')
    .replace(/\n\n/g, '</p><p>')
    .replace(/\n/g, '<br>')
    .replace(/^/, '<p>')
    .replace(/$/, '</p>');
}
function addMessage(role, text, mode = null) {
  const el = document.createElement("div");
  el.className = `msg ${role}`;
  
  const timestamp = new Date().toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'});
  const currentMode = mode || document.querySelector('input[name="mod"]:checked').value;
  
  // Add mode indicator for assistant messages
  let modeIndicator = '';
  if (role === 'assistant' && currentMode) {
    let modeIcon, modeName;
    if (currentMode === 'literature') {
      modeIcon = '🔍';
      modeName = 'Literature Review';
    } else if (currentMode === 'pico') {
      modeIcon = '📋';
      modeName = 'PICO Review';
    } else {
      modeIcon = '💬';
      modeName = 'RAG Chat';
    }
    modeIndicator = `<div class="mode-indicator">${modeIcon} ${modeName}</div>`;
  }
  
  el.innerHTML = `
    <div class="bubble">
      ${modeIndicator}
      <div class="message-content">${formatMessage(escapeHtml(text))}</div>
      <div class="message-time">${timestamp}</div>
    </div>
  `;
  
  chat.appendChild(el);
  chat.scrollTop = chat.scrollHeight;
  
  // Add fade-in animation
  el.style.opacity = '0';
  el.style.transform = 'translateY(10px)';
  setTimeout(() => {
    el.style.transition = 'all 0.3s ease';
    el.style.opacity = '1';
    el.style.transform = 'translateY(0)';
  }, 10);
}

function addPaperTable(papers) {
  const el = document.createElement("div");
  el.className = "msg assistant";
  
  const timestamp = new Date().toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'});
  const currentMode = document.querySelector('input[name="mod"]:checked').value;
  let modeIcon, modeName;
  if (currentMode === 'literature') {
    modeIcon = '🔍';
    modeName = 'Literature Review';
  } else if (currentMode === 'pico') {
    modeIcon = '📋';
    modeName = 'PICO Review';
  } else {
    modeIcon = '💬';
    modeName = 'RAG Chat';
  }
  
  let tableHTML = `
    <div class="bubble">
      <div class="mode-indicator">${modeIcon} ${modeName}</div>
      <div class="papers-header">
        <h3>📄 Research Papers Found</h3>
        <span class="papers-count">${papers.length} papers</span>
      </div>
      <div class="papers-table-container">
        <table class="papers-table">
          <thead>
            <tr>
              <th>Title</th>
              <th>Authors</th>
              <th>Year</th>
              <th>Abstract</th>
              <th>Rationale</th>
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
    const rationale = escapeHtml(paper.rationale || "");
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
    if (paper.openalex_url) {
      links.push(`<a href="${escapeHtml(paper.openalex_url)}" target="_blank" class="link-btn openalex-link">OpenAlex</a>`);
    }
    if (paper.semantic_scholar_url) {
      links.push(`<a href="${escapeHtml(paper.semantic_scholar_url)}" target="_blank" class="link-btn semantic-scholar-link">Semantic Scholar</a>`);
    }
    // Check if url is an OpenAlex URL (for papers stored with openalex_url in url field)
    if (paper.url && paper.url.includes("openalex.org") && !paper.openalex_url) {
      links.push(`<a href="${escapeHtml(paper.url)}" target="_blank" class="link-btn openalex-link">OpenAlex</a>`);
    }
    // Check if url is a Semantic Scholar URL
    if (paper.url && paper.url.includes("semanticscholar.org") && !paper.semantic_scholar_url) {
      links.push(`<a href="${escapeHtml(paper.url)}" target="_blank" class="link-btn semantic-scholar-link">Semantic Scholar</a>`);
    }
    if (paper.pdf_path) {
      links.push(`<a href="${escapeHtml(paper.pdf_path)}" target="_blank" class="link-btn pdf-link">PDF</a>`);
    }
    if (paper.url && !paper.doi_url && !paper.pubmed_url && !paper.openalex_url && !paper.semantic_scholar_url && !paper.url.includes("openalex.org") && !paper.url.includes("semanticscholar.org")) {
      links.push(`<a href="${escapeHtml(paper.url)}" target="_blank" class="link-btn url-link">Link</a>`);
    }
    
    const linksHTML = links.length > 0 ? links.join(" ") : "—";
    
    // Truncate abstract and rationale for display
    const shortAbstract = abstract.length > 200 ? abstract.substring(0, 200) + "..." : abstract;
    const shortRationale = rationale.length > 150 ? rationale.substring(0, 150) + "..." : rationale;
    
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
        <td class="rationale-cell">
          <div class="rationale-short">${shortRationale}</div>
          ${rationale.length > 150 ? `<button class="expand-btn" onclick="toggleRationale(this)">Show more</button>` : ""}
          <div class="rationale-full" style="display: none;">${rationale}</div>
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
      <div class="message-time">${timestamp}</div>
    </div>
  `;
  
  el.innerHTML = tableHTML;
  chat.appendChild(el);
  chat.scrollTop = chat.scrollHeight;
  
  // Add fade-in animation
  el.style.opacity = '0';
  el.style.transform = 'translateY(10px)';
  setTimeout(() => {
    el.style.transition = 'all 0.3s ease';
    el.style.opacity = '1';
    el.style.transform = 'translateY(0)';
  }, 10);
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

function toggleRationale(btn) {
  const row = btn.closest('tr');
  const shortRationale = row.querySelector('.rationale-short');
  const fullRationale = row.querySelector('.rationale-full');
  
  if (fullRationale.style.display === 'none') {
    shortRationale.style.display = 'none';
    fullRationale.style.display = 'block';
    btn.textContent = 'Show less';
  } else {
    shortRationale.style.display = 'block';
    fullRationale.style.display = 'none';
    btn.textContent = 'Show more';
  }
}

function showLoadingIndicator() {
  const loadingEl = document.createElement("div");
  loadingEl.className = "loading-indicator show";
  loadingEl.innerHTML = `
    <div class="loading-spinner"></div>
    <span id="loading-text">Starting literature review...</span>
  `;
  chat.appendChild(loadingEl);
  chat.scrollTop = chat.scrollHeight;
  return loadingEl;
}

function updateLoadingMessage(loadingEl, message) {
  const textEl = loadingEl.querySelector('#loading-text');
  if (textEl) {
    textEl.textContent = message;
  }
}

function startProgressUpdates(loadingEl) {
  const stages = [
    "Starting literature review...",
    "Expanding query with keywords...",
    "Generating search concepts...",
    "Building PubMed query...",
    "Fetching papers from PubMed...",
    "Stage 1: Basic screening...",
    "Stage 2: PICO analysis with rationale...",
    "Saving papers to database...",
    "Finalizing results..."
  ];
  
  let currentStage = 0;
  
  // Update immediately
  updateLoadingMessage(loadingEl, stages[currentStage]);
  
  // Update every 3-5 seconds
  const interval = setInterval(() => {
    currentStage = (currentStage + 1) % stages.length;
    updateLoadingMessage(loadingEl, stages[currentStage]);
  }, 4000); // Update every 4 seconds
  
  return interval;
}

function hideLoadingIndicator(loadingEl) {
  if (loadingEl && loadingEl.parentNode) {
    loadingEl.parentNode.removeChild(loadingEl);
  }
}

function showTypingIndicator() {
  const el = document.createElement("div");
  el.className = "msg assistant typing-indicator";
  el.innerHTML = `
    <div class="bubble">
      <div class="mode-indicator">💬 ${document.querySelector('input[name="mod"]:checked').value === 'literature' ? 'Literature Review' : 'RAG Chat'}</div>
      <div class="typing-content">
        <div class="typing-dots">
          <span></span>
          <span></span>
          <span></span>
        </div>
        <span class="typing-text">Assistant is typing...</span>
      </div>
    </div>
  `;
  chat.appendChild(el);
  chat.scrollTop = chat.scrollHeight;
  return el;
}

function hideTypingIndicator(typingEl) {
  if (typingEl && typingEl.parentNode) {
    typingEl.parentNode.removeChild(typingEl);
  }
}

function exportChatHistory() {
  const messages = Array.from(chat.querySelectorAll('.msg')).map(msg => {
    const role = msg.classList.contains('user') ? 'User' : 'Assistant';
    const content = msg.querySelector('.message-content');
    const time = msg.querySelector('.message-time');
    const modeIndicator = msg.querySelector('.mode-indicator');
    
    let text = content ? content.textContent.trim() : '';
    if (modeIndicator) {
      text = `[${modeIndicator.textContent}] ${text}`;
    }
    
    return `${role} (${time ? time.textContent : 'Unknown time'}): ${text}`;
  }).join('\n\n');
  
  const blob = new Blob([`AI4SR Literature Review Chat Export\nSession #${conversationId || 'Unknown'}\nExported: ${new Date().toLocaleString()}\n\n${messages}`], { type: 'text/plain' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `ai4sr-chat-${conversationId || 'export'}-${new Date().toISOString().split('T')[0]}.txt`;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

function showKeyboardShortcuts() {
  const shortcuts = [
    { key: 'Enter', description: 'Send message' },
    { key: 'Ctrl/Cmd + Enter', description: 'Send message (alternative)' },
    { key: 'Ctrl/Cmd + E', description: 'Export chat history' },
    { key: 'Ctrl/Cmd + /', description: 'Focus input field' }
  ];
  
  const shortcutsHTML = shortcuts.map(s => 
    `<div class="shortcut-item">
      <kbd class="shortcut-key">${s.key}</kbd>
      <span class="shortcut-desc">${s.description}</span>
    </div>`
  ).join('');
  
  addMessage("assistant", `⌨️ **Keyboard Shortcuts**\n\n${shortcutsHTML}\n\n*Tip: You can switch between Literature Review and RAG Chat modes anytime - your conversation history will be preserved!*`);
}

// Dark Mode Functions
function initTheme() {
  const savedTheme = localStorage.getItem('ai4sr-theme') || 'light';
  setTheme(savedTheme);
}

function setTheme(theme) {
  document.documentElement.setAttribute('data-theme', theme);
  localStorage.setItem('ai4sr-theme', theme);
  
  const themeIcon = themeBtn.querySelector('.theme-icon');
  const themeText = themeBtn.querySelector('.theme-text');
  
  if (theme === 'dark') {
    themeIcon.textContent = '☀️';
    themeText.textContent = 'Light';
    themeBtn.title = 'Switch to Light Mode';
  } else {
    themeIcon.textContent = '🌙';
    themeText.textContent = 'Dark';
    themeBtn.title = 'Switch to Dark Mode';
  }
}

function toggleTheme() {
  const currentTheme = document.documentElement.getAttribute('data-theme');
  const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
  setTheme(newTheme);
}

// Keyboard shortcuts
function handleKeyboardShortcuts(e) {
  // Ctrl/Cmd + Enter to send message
  if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
    e.preventDefault();
    sendMessage();
  }
  
  // Ctrl/Cmd + E to export chat
  if ((e.ctrlKey || e.metaKey) && e.key === 'e') {
    e.preventDefault();
    exportChatHistory();
  }
  
  // Ctrl/Cmd + / to focus input
  if ((e.ctrlKey || e.metaKey) && e.key === '/') {
    e.preventDefault();
    input.focus();
  }
}

async function startConversation() {
  const mod = document.querySelector('input[name="mod"]:checked').value;
  const projectName = document.getElementById("project_id")?.value?.trim() || "default";
  
  // Only start new conversation if we don't have one
  if (!conversationId) {
    const res = await fetch("/api/start", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ modality: mod, project_name: projectName })
    });
    const data = await res.json();
    conversationId = data.conversation_id;
  }
  
  let modeName;
  if (mod === 'literature') modeName = 'Literature Review';
  else if (mod === 'pico') modeName = 'PICO Review';
  else modeName = 'RAG Chat';
  convMeta.textContent = `Session #${conversationId} · ${modeName}`;
  
  // Show/hide delete button based on whether we have a project
  if (conversationId && projectName !== "default") {
    deleteProjectBtn.style.display = 'flex';
  } else {
    deleteProjectBtn.style.display = 'none';
  }
  
  // Refresh sidebar to show new conversation
  loadSidebarProjects();
  
  // Only show welcome message if chat is empty
  if (chat.children.length === 0) {
    if (mod === 'literature') {
      addMessage("assistant", `🔍 **Literature Review Mode Active**\n\nI can help you:\n• Find relevant papers for your research topic\n• Analyze and summarize research findings\n• Generate comprehensive literature reviews\n• Screen papers based on your criteria\n\nWhat research question or topic would you like me to explore?`, mod);
    } else if (mod === 'pico') {
      addMessage("assistant", `📋 **PICO Review Mode Active**\n\nSystematic review workflow:\n1. Fill in the PICO framework below\n2. Click "Save PICO" to store your review question\n3. Click "Expand PICO" to generate search queries\n4. Click "Generate Corpus" to fetch papers from PubMed and OpenAlex\n\nStart by entering your Population (required) and other PICO components.`, mod);
    } else {
      addMessage("assistant", `💬 **RAG Chat Mode Active**\n\nI can help you:\n• Answer questions about your existing documents\n• Search through your uploaded papers\n• Provide insights from your research collection\n\nWhat would you like to know about your documents?`, mod);
    }
  } else {
    // Add mode switch notification
    let modeName;
    if (mod === 'literature') modeName = 'Literature Review';
    else if (mod === 'pico') modeName = 'PICO Review';
    else modeName = 'RAG Chat';
    addMessage("assistant", `Mode switched to **${modeName}**. How can I help you?`, mod);
  }
}

// Show/hide input sections based on mode
function updateInputSection() {
  const mod = document.querySelector('input[name="mod"]:checked').value;
  const standardSection = document.getElementById("standard-input-section");
  const picoSection = document.getElementById("pico-input-section");
  
  if (mod === "pico") {
    standardSection.style.display = "none";
    picoSection.style.display = "block";
    // Sync project ID
    const projectId = document.getElementById("project_id")?.value || "";
    if (projectId) {
      document.getElementById("pico-project-id").value = projectId;
    }
  } else {
    standardSection.style.display = "block";
    picoSection.style.display = "none";
    // Sync project ID
    const picoProjectId = document.getElementById("pico-project-id")?.value || "";
    if (picoProjectId) {
      document.getElementById("project_id").value = picoProjectId;
    }
  }
}

async function sendMessage() {
  const text = input.value.trim();
  if (!text || !conversationId) return;

  const mod = document.querySelector('input[name="mod"]:checked').value;
  if (mod === "pico") {
    // PICO mode uses separate handlers
    return;
  }

  const pid = (document.getElementById("project_id")?.value || "").trim();
  const paperLimit = Math.max(1, Math.min(50, parseInt(document.getElementById("paper_limit")?.value || "10")));

  addMessage("user", text);
  sendBtn.disabled = true;
  input.value = "";

  // Show appropriate indicator based on mode
  let loadingIndicator = null;
  let typingIndicator = null;
  let progressInterval = null;
  
  if (mod === "literature") {
    loadingIndicator = showLoadingIndicator();
    progressInterval = startProgressUpdates(loadingIndicator);
  } else {
    typingIndicator = showTypingIndicator();
  }

  try {
    // Get API key from localStorage if available
    const apiKey = localStorage.getItem('openai_api_key');
    
    const res = await fetch("/api/message", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        conversation_id: conversationId,
        text,
        modality: mod,
        project_id: pid || "",
        paper_limit: paperLimit,
        api_key: apiKey
      })
    });
    const data = await res.json();
    
    // Hide indicators
    if (loadingIndicator) {
      if (progressInterval) {
        clearInterval(progressInterval);
      }
      hideLoadingIndicator(loadingIndicator);
    }
    if (typingIndicator) {
      hideTypingIndicator(typingIndicator);
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
    // Hide indicators on error
    if (loadingIndicator) {
      if (progressInterval) {
        clearInterval(progressInterval);
      }
      hideLoadingIndicator(loadingIndicator);
    }
    if (typingIndicator) {
      hideTypingIndicator(typingIndicator);
    }
    addMessage("assistant", `Error: ${error.message}`);
  }
  
  sendBtn.disabled = false;
}


document.querySelectorAll('input[name="mod"]').forEach(r => {
  r.addEventListener("change", async () => {
    updateInputSection();
    
    // If switching to PICO mode, load PICO data for current project
    if (r.value === 'pico') {
      const projectName = document.getElementById('pico-project-id')?.value?.trim() || 
                         document.getElementById('project_id')?.value?.trim();
      if (projectName) {
        try {
          const projectId = await getOrCreateProject(projectName);
          await loadPicoData(projectId);
        } catch (e) {
          // Project doesn't exist or error loading - clear form
          clearPicoForm();
        }
      }
    }
    
    startConversation();
  });
});
sendBtn.addEventListener("click", sendMessage);
exportBtn.addEventListener("click", exportChatHistory);
helpBtn.addEventListener("click", showKeyboardShortcuts);
themeBtn.addEventListener("click", toggleTheme);

// Keyboard event listeners
input.addEventListener("keydown", (e) => { 
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    sendMessage();
  }
});

document.addEventListener("keydown", handleKeyboardShortcuts);

// Add input focus enhancement
input.addEventListener("focus", () => {
  input.parentElement.classList.add("focused");
});

input.addEventListener("blur", () => {
  input.parentElement.classList.remove("focused");
});

// Refresh sidebar when project input changes
const projectInput = document.getElementById('project_id');
if (projectInput) {
  projectInput.addEventListener('input', () => {
    // Refresh sidebar to update active project highlighting
    loadSidebarProjects();
  });
}

// Sidebar functionality
let sidebarCollapsed = false;
let currentProjects = [];

// Toggle sidebar
function toggleSidebar() {
  sidebarCollapsed = !sidebarCollapsed;
  sidebar.classList.toggle('collapsed', sidebarCollapsed);
  
  // Update all toggle buttons
  const toggleIcon = sidebarToggle.querySelector('.toggle-icon');
  if (toggleIcon) {
    toggleIcon.textContent = sidebarCollapsed ? '→' : '←';
  }
  
  // Update floating button visibility
  if (sidebarToggleFloat) {
    sidebarToggleFloat.style.display = sidebarCollapsed ? 'block' : 'none';
  }
  
  localStorage.setItem('sidebarCollapsed', sidebarCollapsed);
}

// Load projects for sidebar
async function loadSidebarProjects() {
  try {
    const response = await fetch('/api/projects');
    const projects = await response.json();
    currentProjects = projects;
    renderSidebarProjects(projects);
  } catch (error) {
    console.error('Error loading projects:', error);
    sidebarProjects.innerHTML = '<div class="sidebar-error">Error loading projects</div>';
  }
}

// Render projects in sidebar
function renderSidebarProjects(projects) {
  if (projects.length === 0) {
    sidebarProjects.innerHTML = '<div class="sidebar-empty">No projects yet</div>';
    return;
  }

  // Get current project name
  const currentProject = document.getElementById('project_id')?.value?.trim() || '';

  sidebarProjects.innerHTML = projects.map(project => {
    const isActive = project.name === currentProject;
    return `
      <div class="project-item ${isActive ? 'active' : ''}" data-project-id="${project.id}">
        <div class="project-header">
          <span class="project-name">${escapeHtml(project.name)}</span>
          <div class="project-stats">
            <span class="project-count" title="Conversations">💬 ${project.conversation_count}</span>
            <span class="project-papers" title="Papers">📄 ${project.paper_count}</span>
          </div>
        </div>
        <div class="project-meta">
          <span class="project-date">${formatDate(project.last_conversation || project.created_at)}</span>
        </div>
        <div class="project-conversations" id="conversations-${project.id}">
          <!-- Conversations will be loaded here -->
        </div>
      </div>
    `;
  }).join('');

  // Add click handlers for projects
  document.querySelectorAll('.project-item').forEach(item => {
    item.addEventListener('click', () => {
      const projectId = item.dataset.projectId;
      const project = projects.find(p => p.id == projectId);
      loadProject(projectId, project.name);
    });
  });
}

// Load a project (switch to project context and start fresh conversation)
async function loadProject(projectId, projectName) {
  try {
    // Set the project name in the input field
    document.getElementById('project_id').value = projectName;
    document.getElementById('pico-project-id').value = projectName;
    
    // Always load PICO data if available (regardless of current mode)
    await loadPicoData(projectId);
    
    // Clear current chat
    chat.innerHTML = '';
    
    // Reset conversation ID to start fresh
    conversationId = null;
    
    // Start a new conversation for this project
    await startConversation();
    
    // Update conversation meta to show project
    convMeta.textContent = `Project: ${projectName} | New Conversation`;
    
    // Show project loaded message
    addMessage("assistant", `📁 **Switched to Project: ${projectName}**\n\nYou can now ask questions about the papers in this project using RAG mode, or search for new literature using Literature Review mode.`, "rag");
    
    // Refresh sidebar to show updated state
    loadSidebarProjects();
    
  } catch (error) {
    console.error('Error loading project:', error);
    addMessage("assistant", `Error loading project: ${error.message}`, "rag");
  }
}

// Load conversations for a project
async function loadProjectConversations(projectId, projectName) {
  try {
    const response = await fetch(`/api/conversations/${projectId}`);
    const conversations = await response.json();
    
    const container = document.getElementById(`conversations-${projectId}`);
    if (conversations.length === 0) {
      container.innerHTML = '<div class="conversation-empty">No conversations yet</div>';
      return;
    }

    container.innerHTML = conversations.map(conv => `
      <div class="conversation-item" data-conversation-id="${conv.id}">
        <div class="conversation-preview">
          <span class="conversation-time">${formatDate(conv.last_message)}</span>
          <span class="conversation-count">${conv.message_count} messages</span>
        </div>
      </div>
    `).join('');

    // Add click handlers for conversations
    container.querySelectorAll('.conversation-item').forEach(item => {
      item.addEventListener('click', (e) => {
        e.stopPropagation();
        const conversationId = item.dataset.conversationId;
        loadConversation(conversationId, projectName);
      });
    });

  } catch (error) {
    console.error('Error loading conversations:', error);
  }
}

// Load a specific conversation
async function loadConversation(conversationId, projectName) {
  try {
    const response = await fetch(`/api/conversations/${conversationId}/messages`);
    const messages = await response.json();
    
    // Clear current chat
    chat.innerHTML = '';
    
    // Set the project name in the input
    document.getElementById('project_id').value = projectName;
    
    // Load messages
    messages.forEach(msg => {
      addMessage(msg.role, msg.text);
    });
    
    // Set conversation ID
    conversationId = parseInt(conversationId);
    
    // Update conversation meta
    convMeta.textContent = `Project: ${projectName} | Conversation: ${conversationId}`;
    
    // Scroll to bottom
    chat.scrollTop = chat.scrollHeight;
    
  } catch (error) {
    console.error('Error loading conversation:', error);
  }
}

// Format date for display
function formatDate(dateString) {
  if (!dateString) return 'Unknown';
  const date = new Date(dateString);
  const now = new Date();
  const diffTime = Math.abs(now - date);
  const diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24));
  
  if (diffDays === 1) return 'Today';
  if (diffDays === 2) return 'Yesterday';
  if (diffDays <= 7) return `${diffDays - 1} days ago`;
  
  return date.toLocaleDateString();
}

// Search projects
function searchProjects(query) {
  const filtered = currentProjects.filter(project => 
    project.name.toLowerCase().includes(query.toLowerCase())
  );
  renderSidebarProjects(filtered);
}

// Initialize sidebar
function initSidebar() {
  // Load saved sidebar state
  const savedState = localStorage.getItem('sidebarCollapsed');
  if (savedState === 'true') {
    sidebarCollapsed = true;
    sidebar.classList.add('collapsed');
    const toggleIcon = sidebarToggle.querySelector('.toggle-icon');
    if (toggleIcon) {
      toggleIcon.textContent = '→';
    }
  }
  
  // Set initial floating button visibility
  if (sidebarToggleFloat) {
    sidebarToggleFloat.style.display = sidebarCollapsed ? 'block' : 'none';
  }
  
  // Load projects
  loadSidebarProjects();
  
  // Add event listeners
  if (sidebarToggle) {
    sidebarToggle.addEventListener('click', toggleSidebar);
  }
  if (sidebarToggleHeader) {
    sidebarToggleHeader.addEventListener('click', toggleSidebar);
  }
  if (sidebarToggleFloat) {
    sidebarToggleFloat.addEventListener('click', toggleSidebar);
  }
  if (sidebarSearch) {
    sidebarSearch.addEventListener('input', (e) => searchProjects(e.target.value));
  }
}

// Settings functionality
function initSettings() {
  const settingsModal = document.getElementById("settings-modal");
  const settingsClose = document.getElementById("settings-close");
  const cancelSettings = document.getElementById("cancel-settings");
  const saveSettings = document.getElementById("save-settings");
  const testApiKey = document.getElementById("test-api-key");
  const openaiKeyInput = document.getElementById("openai-key");
  const toggleApiKey = document.getElementById("toggle-api-key");
  const additionalKeyInput = document.getElementById("additional-key");
  const toggleAdditionalKey = document.getElementById("toggle-additional-key");
  const defaultPapersInput = document.getElementById("default-papers");
  const defaultProjectInput = document.getElementById("default-project");
  const apiStatus = document.getElementById("api-status");

  // Load saved settings
  function loadSettings() {
    const savedKey = localStorage.getItem('openai_api_key');
    const savedAdditionalKey = localStorage.getItem('additional_api_key');
    const savedPapers = localStorage.getItem('default_papers');
    const savedProject = localStorage.getItem('default_project');
    
    if (savedKey) openaiKeyInput.value = savedKey;
    if (savedAdditionalKey) additionalKeyInput.value = savedAdditionalKey;
    if (savedPapers) defaultPapersInput.value = savedPapers;
    if (savedProject) defaultProjectInput.value = savedProject;
  }

  // Save settings
  function saveSettingsToStorage() {
    const apiKey = openaiKeyInput.value.trim();
    const additionalKey = additionalKeyInput.value.trim();
    const papers = defaultPapersInput.value;
    const project = defaultProjectInput.value.trim();
    
    if (apiKey) localStorage.setItem('openai_api_key', apiKey);
    else localStorage.removeItem('openai_api_key'); // Remove if empty
    if (additionalKey) localStorage.setItem('additional_api_key', additionalKey);
    else localStorage.removeItem('additional_api_key'); // Remove if empty
    if (papers) localStorage.setItem('default_papers', papers);
    if (project) localStorage.setItem('default_project', project);
    
    // Update UI with saved values
    if (papers) document.getElementById("papers").value = papers;
    if (project) document.getElementById("project").value = project;
  }

  // Test API key
  async function testApiKeyFunction() {
    const apiKey = openaiKeyInput.value.trim();
    if (!apiKey) {
      apiStatus.textContent = "Please enter an API key";
      apiStatus.className = "api-status error";
      return;
    }

    apiStatus.textContent = "Testing...";
    apiStatus.className = "api-status";

    try {
      const response = await fetch('/api/test-openai', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ api_key: apiKey })
      });

      const result = await response.json();
      
      if (response.ok && result.success) {
        apiStatus.textContent = "✓ API key is valid";
        apiStatus.className = "api-status success";
      } else {
        apiStatus.textContent = "✗ API key is invalid";
        apiStatus.className = "api-status error";
      }
    } catch (error) {
      apiStatus.textContent = "✗ Test failed";
      apiStatus.className = "api-status error";
    }
  }

  // Event listeners
  settingsBtn.addEventListener('click', () => {
    loadSettings();
    settingsModal.style.display = 'block';
  });

  settingsClose.addEventListener('click', () => {
    settingsModal.style.display = 'none';
  });

  cancelSettings.addEventListener('click', () => {
    settingsModal.style.display = 'none';
  });

  saveSettings.addEventListener('click', () => {
    saveSettingsToStorage();
    settingsModal.style.display = 'none';
    showNotification('Settings saved successfully!', 'success');
  });

  testApiKey.addEventListener('click', testApiKeyFunction);

      // Toggle API key visibility
      toggleApiKey.addEventListener('click', () => {
        if (openaiKeyInput.type === 'password') {
          openaiKeyInput.type = 'text';
          toggleApiKey.textContent = '🙈';
          toggleApiKey.title = 'Hide API Key';
        } else {
          openaiKeyInput.type = 'password';
          toggleApiKey.textContent = '👁️';
          toggleApiKey.title = 'Show API Key';
        }
      });

      // Toggle additional key visibility
      toggleAdditionalKey.addEventListener('click', () => {
        if (additionalKeyInput.type === 'password') {
          additionalKeyInput.type = 'text';
          toggleAdditionalKey.textContent = '🙈';
          toggleAdditionalKey.title = 'Hide Additional Key';
        } else {
          additionalKeyInput.type = 'password';
          toggleAdditionalKey.textContent = '👁️';
          toggleAdditionalKey.title = 'Show Additional Key';
        }
      });

  // Close modal when clicking outside
  settingsModal.addEventListener('click', (e) => {
    if (e.target === settingsModal) {
      settingsModal.style.display = 'none';
    }
  });

  // Load settings on page load
  loadSettings();
}

// Delete project functionality
function initDeleteProject() {
  deleteProjectBtn.addEventListener('click', async () => {
    if (!conversationId) {
      showNotification('No project selected to delete', 'error');
      return;
    }

    const projectName = document.getElementById("project_id")?.value || "current project";
    
    if (confirm(`Are you sure you want to delete "${projectName}" and all its conversations? This action cannot be undone.`)) {
      try {
        const response = await fetch(`/api/projects/${conversationId}`, {
          method: 'DELETE'
        });

        if (response.ok) {
          showNotification('Project deleted successfully', 'success');
          // Reset to default project
          conversationId = null;
          document.getElementById("project_id").value = "";
          loadProjects();
          startConversation();
        } else {
          const error = await response.json();
          showNotification(`Failed to delete project: ${error.error}`, 'error');
        }
      } catch (error) {
        showNotification(`Error deleting project: ${error.message}`, 'error');
      }
    }
  });
}

// PICO Mode Functions
function updatePicoStatus(message, type = 'info') {
  const statusEl = document.getElementById('pico-status');
  if (!statusEl) return;
  
  statusEl.textContent = message;
  statusEl.className = `pico-status pico-status-${type}`;
  
  if (type === 'success' || type === 'error') {
    setTimeout(() => {
      statusEl.textContent = '';
      statusEl.className = 'pico-status';
    }, 5000);
  }
}

async function getOrCreateProject(projectName) {
  if (!projectName) {
    throw new Error('Project name is required');
  }
  
  const res = await fetch('/api/start', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ project_name: projectName })
  });
  
  if (!res.ok) {
    throw new Error('Failed to create/get project');
  }
  
  const data = await res.json();
  return data.project_id;
}

async function savePico() {
  const projectIdInput = document.getElementById('pico-project-id');
  const projectName = projectIdInput?.value.trim();
  
  if (!projectName) {
    updatePicoStatus('Please enter a project name', 'error');
    return;
  }
  
  const population = document.getElementById('pico-population')?.value.trim();
  if (!population) {
    updatePicoStatus('Population is required', 'error');
    return;
  }
  
  const intervention = document.getElementById('pico-intervention')?.value.trim() || null;
  const comparison = document.getElementById('pico-comparison')?.value.trim() || null;
  const outcome = document.getElementById('pico-outcome')?.value.trim() || null;
  const studyDesign = document.getElementById('pico-study-design')?.value.trim() || null;
  const extraTermsStr = document.getElementById('pico-extra-terms')?.value.trim() || '';
  const extraTerms = extraTermsStr ? extraTermsStr.split(',').map(t => t.trim()).filter(t => t) : null;
  
  try {
    updatePicoStatus('Saving PICO...', 'info');
    const projectId = await getOrCreateProject(projectName);
    
    const res = await fetch(`/api/projects/${projectId}/pico`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        population,
        intervention,
        comparison,
        outcome,
        study_design: studyDesign,
        extra_terms: extraTerms
      })
    });
    
    if (!res.ok) {
      const error = await res.json();
      throw new Error(error.error || 'Failed to save PICO');
    }
    
    updatePicoStatus('PICO saved successfully!', 'success');
    document.getElementById('expand-pico').disabled = false;
    addMessage('assistant', '✅ **PICO Saved**\n\nYour PICO framework has been saved. You can now expand it to generate search queries.', 'pico');
    
    // Reload PICO data to ensure form is in sync
    await loadPicoData(projectId);
  } catch (error) {
    updatePicoStatus(`Error: ${error.message}`, 'error');
    addMessage('assistant', `❌ **Error saving PICO**\n\n${error.message}`, 'pico');
  }
}

async function expandPico() {
  const projectIdInput = document.getElementById('pico-project-id');
  const projectName = projectIdInput?.value.trim();
  
  if (!projectName) {
    updatePicoStatus('Please enter a project name', 'error');
    return;
  }
  
  try {
    updatePicoStatus('Expanding PICO... This may take a moment.', 'info');
    const projectId = await getOrCreateProject(projectName);
    const apiKey = localStorage.getItem('openai_api_key');
    
    const res = await fetch(`/api/projects/${projectId}/expand-pico`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ api_key: apiKey || undefined })
    });
    
    if (!res.ok) {
      const error = await res.json();
      throw new Error(error.error || 'Failed to expand PICO');
    }
    
    const data = await res.json();
    updatePicoStatus('PICO expanded successfully!', 'success');
    document.getElementById('generate-corpus').disabled = false;
    
    let message = '✅ **PICO Expanded**\n\n';
    message += `**Question Summary:**\n${data.question_summary}\n\n`;
    message += `**PubMed Query:**\n\`${data.pubmed_query}\`\n\n`;
    message += `**OpenAlex Query:**\n\`${data.openalex_query}\`\n\n`;
    message += 'You can now generate the corpus.';
    addMessage('assistant', message, 'pico');
  } catch (error) {
    updatePicoStatus(`Error: ${error.message}`, 'error');
    addMessage('assistant', `❌ **Error expanding PICO**\n\n${error.message}`, 'pico');
  }
}

async function generateCorpus() {
  const projectIdInput = document.getElementById('pico-project-id');
  const projectName = projectIdInput?.value.trim();
  
  if (!projectName) {
    updatePicoStatus('Please enter a project name', 'error');
    return;
  }
  
  try {
    updatePicoStatus('Generating corpus... This may take several minutes.', 'info');
    const projectId = await getOrCreateProject(projectName);
    const apiKey = localStorage.getItem('openai_api_key');
    
    // Show loading message
    addMessage('assistant', '⏳ **Generating Corpus**\n\nFetching papers from PubMed and OpenAlex. This may take a few minutes...', 'pico');
    
    const res = await fetch(`/api/projects/${projectId}/generate-corpus`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ api_key: apiKey || undefined })
    });
    
    if (!res.ok) {
      const error = await res.json();
      throw new Error(error.error || 'Failed to generate corpus');
    }
    
    const data = await res.json();
    updatePicoStatus('Corpus generated successfully!', 'success');
    
    let message = '✅ **Corpus Generated**\n\n';
    message += `**PubMed:** ${data.sources.pubmed.fetched} fetched, ${data.sources.pubmed.unique} unique\n`;
    message += `**OpenAlex:** ${data.sources.openalex.fetched} fetched, ${data.sources.openalex.unique} unique\n`;
    message += `**Total Unique Papers:** ${data.total_unique}\n`;
    message += `**Inserted:** ${data.inserted_count} papers with status UNSCREENED\n\n`;
    message += 'Papers are now available in your project for screening.';
    
    addMessage('assistant', message, 'pico');
  } catch (error) {
    updatePicoStatus(`Error: ${error.message}`, 'error');
    addMessage('assistant', `❌ **Error generating corpus**\n\n${error.message}`, 'pico');
  }
}

// Load PICO data for a project
async function loadPicoData(projectId) {
  try {
    const res = await fetch(`/api/projects/${projectId}/pico`);
    
    if (res.ok) {
      const pico = await res.json();
      
      // Populate form fields
      document.getElementById('pico-population').value = pico.population || '';
      document.getElementById('pico-intervention').value = pico.intervention || '';
      document.getElementById('pico-comparison').value = pico.comparison || '';
      document.getElementById('pico-outcome').value = pico.outcome || '';
      document.getElementById('pico-study-design').value = pico.study_design || '';
      
      // Handle extra_terms (array to comma-separated string)
      if (pico.extra_terms && Array.isArray(pico.extra_terms)) {
        document.getElementById('pico-extra-terms').value = pico.extra_terms.join(', ');
      } else if (pico.extra_terms) {
        document.getElementById('pico-extra-terms').value = pico.extra_terms;
      } else {
        document.getElementById('pico-extra-terms').value = '';
      }
      
      // Enable expand button since PICO is saved
      document.getElementById('expand-pico').disabled = false;
      
      // Check if expansion exists and enable generate corpus button
      try {
        const expansionRes = await fetch(`/api/projects/${projectId}/queries`);
        if (expansionRes.ok) {
          document.getElementById('generate-corpus').disabled = false;
        }
      } catch (e) {
        // Expansion doesn't exist yet, that's fine
      }
    } else if (res.status === 404) {
      // No PICO saved yet - clear form and disable buttons
      clearPicoForm();
    }
  } catch (error) {
    console.error('Error loading PICO:', error);
    // Don't show error to user - just leave form empty
  }
}

// Clear PICO form
function clearPicoForm() {
  document.getElementById('pico-population').value = '';
  document.getElementById('pico-intervention').value = '';
  document.getElementById('pico-comparison').value = '';
  document.getElementById('pico-outcome').value = '';
  document.getElementById('pico-study-design').value = '';
  document.getElementById('pico-extra-terms').value = '';
  document.getElementById('expand-pico').disabled = true;
  document.getElementById('generate-corpus').disabled = true;
}

// Initialize PICO mode
function initPicoMode() {
  updateInputSection();
  
  // PICO button handlers
  const savePicoBtn = document.getElementById('save-pico');
  const expandPicoBtn = document.getElementById('expand-pico');
  const generateCorpusBtn = document.getElementById('generate-corpus');
  
  if (savePicoBtn) {
    savePicoBtn.addEventListener('click', savePico);
  }
  if (expandPicoBtn) {
    expandPicoBtn.addEventListener('click', expandPico);
  }
  if (generateCorpusBtn) {
    generateCorpusBtn.addEventListener('click', generateCorpus);
  }
  
  // Sync project IDs when switching modes
  const projectIdInput = document.getElementById('project_id');
  const picoProjectIdInput = document.getElementById('pico-project-id');
  
  if (projectIdInput && picoProjectIdInput) {
    projectIdInput.addEventListener('change', async () => {
      if (document.querySelector('input[name="mod"]:checked').value !== 'pico') {
        picoProjectIdInput.value = projectIdInput.value;
      } else {
        // If in PICO mode and project changes, load PICO data
        const projectName = projectIdInput.value.trim();
        if (projectName) {
          try {
            const projectId = await getOrCreateProject(projectName);
            await loadPicoData(projectId);
          } catch (e) {
            clearPicoForm();
          }
        } else {
          clearPicoForm();
        }
      }
    });
    
    picoProjectIdInput.addEventListener('change', async () => {
      if (document.querySelector('input[name="mod"]:checked').value === 'pico') {
        projectIdInput.value = picoProjectIdInput.value;
        // Load PICO data when project changes in PICO mode
        const projectName = picoProjectIdInput.value.trim();
        if (projectName) {
          try {
            const projectId = await getOrCreateProject(projectName);
            await loadPicoData(projectId);
          } catch (e) {
            clearPicoForm();
          }
        } else {
          clearPicoForm();
        }
      }
    });
  }
}

// Database viewer button handler
function initDbViewer() {
  const dbViewerBtn = document.getElementById('db-viewer');
  if (dbViewerBtn) {
    dbViewerBtn.addEventListener('click', async () => {
      // Get current project ID from active project in sidebar
      const activeProject = document.querySelector('.project-item.active');
      let projectId = null;
      
      if (activeProject) {
        projectId = activeProject.dataset.projectId;
      } else {
        // Try to get project ID from project name by looking up in projects list
        const projectName = document.getElementById('project_id')?.value?.trim();
        if (projectName && projectName !== 'default') {
          try {
            const response = await fetch('/api/projects');
            const projects = await response.json();
            const project = projects.find(p => p.name === projectName);
            if (project) {
              projectId = project.id;
            }
          } catch (e) {
            console.error('Error getting project ID:', e);
          }
        }
      }
      
      let url = '/api/db-viewer';
      if (projectId) {
        url += '?project_id=' + projectId;
      }
      
      window.open(url, '_blank');
    });
  }
}

// Initialize theme and start conversation
initTheme();
initSidebar();
initSettings();
initDeleteProject();
initPicoMode();
initDbViewer();
startConversation();
