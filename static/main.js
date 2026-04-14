let conversationId = null;

const chat = document.getElementById("chat");
const chatMessages = document.getElementById("chat-messages");
const input = document.getElementById("input");
const sendBtn = document.getElementById("send");
const convMeta = document.getElementById("conv-meta");
const headerControls = document.getElementById("header-controls");
const headerProjectInput = document.getElementById("header-project-id");
const headerPaperLimitInput = document.getElementById("header-paper-limit");
const exportBtn = document.getElementById("export-chat");
const helpBtn = document.getElementById("help-shortcuts");
const settingsBtn = document.getElementById("settings-button");

// Sidebar elements
const sidebar = document.getElementById("sidebar");
const sidebarToggle = document.getElementById("sidebar-toggle");
const sidebarToggleHeader = document.getElementById("sidebar-toggle-header");
const sidebarToggleFloat = document.getElementById("sidebar-toggle-float");
const sidebarProjects = document.getElementById("sidebar-projects");
const sidebarSearch = document.getElementById("sidebar-search");
const deleteProjectBtn = document.getElementById("delete-project");
const createProjectBtn = document.getElementById("create-project");

// Auth elements
const loginBtn = document.getElementById("login-btn");
const logoutBtn = document.getElementById("logout-btn");
const authUserInfo = document.getElementById("auth-user-info");
const userName = document.querySelector(".user-name");

function escapeHtml(str) {
  return str.replace(/[&<>"']/g, s => ({
    "&":"&amp;","<":"&lt;",">":"&gt;","\"":"&quot;","'":"&#39;"
  }[s]));
}

async function checkAuthStatus() {
  try {
    const response = await fetch("/auth/user");
    const data = await response.json();
    
    if (data.authenticated) {
      showLoggedInUser(data.user);
    } else {
      showLoggedOutUser();
    }
  } catch (error) {
    console.error("Failed to check auth status:", error);
    showLoggedOutUser();
  }
}

function showLoggedInUser(user) {
  if (loginBtn) loginBtn.style.display = "none";
  if (authUserInfo) authUserInfo.style.display = "flex";
  if (userName) userName.textContent = user.name || user.email;
}

function showLoggedOutUser() {
  if (loginBtn) loginBtn.style.display = "block";
  if (authUserInfo) authUserInfo.style.display = "none";
  if (userName) userName.textContent = "";
}

async function handleLogin() {
  try {
    const response = await fetch("/auth/login");
    const data = await response.json();
    
    if (data.auth_url) {
      window.location.href = data.auth_url;
    } else {
      console.error("No auth URL received");
      alert("Failed to initiate login. Please check configuration.");
    }
  } catch (error) {
    console.error("Login failed:", error);
    alert("Login failed: " + error.message);
  }
}

async function handleLogout() {
  try {
    await fetch("/auth/logout");
    showLoggedOutUser();
  } catch (error) {
    console.error("Logout failed:", error);
  }
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
function addMessage(role, text) {
  const el = document.createElement("div");
  el.className = `msg ${role}`;

  const timestamp = new Date().toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'});
  
  el.innerHTML = `
    <div class="bubble">
      <div class="message-content">${formatMessage(escapeHtml(text))}</div>
      <div class="message-time">${timestamp}</div>
    </div>
  `;
  
  chatMessages.appendChild(el);
  // Smooth scroll to bottom
  setTimeout(() => {
    chatMessages.scrollTo({
      top: chatMessages.scrollHeight,
      behavior: 'smooth'
    });
  }, 50);
  
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

  let tableHTML = `
    <div class="bubble">
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
  chatMessages.appendChild(el);
  // Smooth scroll to bottom
  setTimeout(() => {
    chatMessages.scrollTo({
      top: chatMessages.scrollHeight,
      behavior: 'smooth'
    });
  }, 50);
  
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
    <span id="loading-text">Processing request...</span>
  `;
  chatMessages.appendChild(loadingEl);
  chatMessages.scrollTop = chatMessages.scrollHeight;
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
    "Processing request...",
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
      <div class="typing-content">
        <div class="typing-dots">
          <span></span>
          <span></span>
          <span></span>
        </div>
        <span class="typing-text">Thinking...</span>
      </div>
    </div>
  `;
  chatMessages.appendChild(el);
  chatMessages.scrollTop = chatMessages.scrollHeight;
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

    let text = content ? content.textContent.trim() : '';
    
    return `${role} (${time ? time.textContent : 'Unknown time'}): ${text}`;
  }).join('\n\n');
  
  const blob = new Blob([`AI4SR Chat Export\nSession #${conversationId || 'Unknown'}\nExported: ${new Date().toLocaleString()}\n\n${messages}`], { type: 'text/plain' });
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
  
  addMessage("assistant", `⌨️ **Keyboard Shortcuts**\n\n${shortcutsHTML}\n\n*Tip: You can switch between RAG Chat, PICO Review, and Screening modes anytime - your conversation history will be preserved!*`);
}

// Dark Mode Functions
function initTheme() {
  const savedTheme = localStorage.getItem('ai4sr-theme') || 'light';
  setTheme(savedTheme);
}

function setTheme(theme) {
  document.documentElement.setAttribute('data-theme', theme);
  localStorage.setItem('ai4sr-theme', theme);
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
  let projectName;
  if (mod === "pico") {
    projectName = document.getElementById("pico-project-id")?.value?.trim() || "default";
  } else if (mod === "screening") {
    projectName = document.getElementById("screening-project-id")?.value?.trim() || "default";
  } else {
    projectName = document.getElementById("project_id")?.value?.trim() || "default";
  }
  
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
  if (mod === 'pico') modeName = 'PICO Review';
  else if (mod === 'screening') modeName = 'Screening';
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
  
  // Show welcome message only on first load (no messages yet)
  if (chatMessages.children.length === 0) {
    if (mod === 'rag') {
      addMessage("assistant", `**RAG Chat Mode**\n\nI can help you:\n• Answer questions about your existing documents\n• Search through your uploaded papers\n• Provide insights from your research collection\n\nWhat would you like to know about your documents?`);
    }
    // PICO and Screening have their own UI — no welcome message needed
  }
  // No "mode switched" messages — the active tab is the indicator
}

// Show/hide input sections based on mode
function updateInputSection() {
  const mod = document.querySelector('input[name="mod"]:checked').value;
  const ragComposer = document.getElementById("rag-composer");
  const picoSection = document.getElementById("pico-input-section");
  const screeningSection = document.getElementById("screening-input-section");
  
  if (mod === "pico") {
    // Hide chat composers, show PICO section
    if (ragComposer) ragComposer.style.display = "none";
    if (headerControls) headerControls.style.display = "none";
    if (picoSection) picoSection.style.display = "block";
    if (screeningSection) screeningSection.style.display = "none";
    // Sync project ID
    const projectId = headerProjectInput?.value ||
                     document.getElementById("project_id")?.value || "";
    if (projectId && document.getElementById("pico-project-id")) {
      document.getElementById("pico-project-id").value = projectId;
    }
  } else if (mod === "screening") {
    // Hide chat composers, show screening section
    if (ragComposer) ragComposer.style.display = "none";
    if (headerControls) headerControls.style.display = "none";
    if (picoSection) picoSection.style.display = "none";
    if (screeningSection) screeningSection.style.display = "block";
    // Sync project ID
    const projectId = headerProjectInput?.value ||
                     document.getElementById("project_id")?.value ||
                     document.getElementById("pico-project-id")?.value || "";
    if (projectId && document.getElementById("screening-project-id")) {
      document.getElementById("screening-project-id").value = projectId;
      // Check button visibility if project exists
      getOrCreateProject(projectId).then(id => {
        screeningProjectId = id;
        updateButtonVisibility(id).catch(console.error);
      }).catch(console.error);
    }
    // Initialize screening mode
    initScreeningMode();
  } else {
    // RAG mode - show RAG composer and header controls
    if (ragComposer) ragComposer.style.display = "block";
    if (headerControls) headerControls.style.display = "flex";
    if (picoSection) picoSection.style.display = "none";
    if (screeningSection) screeningSection.style.display = "none";
    // Sync project ID
    const picoProjectId = document.getElementById("pico-project-id")?.value || "";
    const screeningProjectId = document.getElementById("screening-project-id")?.value || "";
    const projectId = picoProjectId || screeningProjectId || "";
    if (projectId) {
      if (headerProjectInput) headerProjectInput.value = projectId;
      if (document.getElementById("project_id")) {
        document.getElementById("project_id").value = projectId;
      }
    }
  }
  
}

async function sendMessage() {
  const mod = document.querySelector('input[name="mod"]:checked').value;
  
  // Get the correct input field based on mode
  let textInput = input;
  let text = input.value.trim();
  
  if (!text || !conversationId) return;

  if (mod === "pico" || mod === "screening") {
    // PICO and Screening modes use separate handlers
    return;
  }

  // Get project ID and paper limit
  let pid = (headerProjectInput?.value || document.getElementById("project_id")?.value || "").trim();
  let paperLimit = Math.max(1, Math.min(50, parseInt(headerPaperLimitInput?.value || document.getElementById("paper_limit")?.value || "10")));

  addMessage("user", text);
  sendBtn.disabled = true;
  textInput.value = "";

  // Show typing indicator
  let typingIndicator = showTypingIndicator();

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
    
    // Hide typing indicator
    hideTypingIndicator(typingIndicator);

    // Handle structured response with papers
    if (data.papers && data.papers.length > 0) {
      addMessage("assistant", data.message);
      addPaperTable(data.papers);
    } else {
      // Handle simple reply for RAG mode or when no papers
      addMessage("assistant", data.reply || data.message);
    }
  } catch (error) {
    // Hide typing indicator on error
    hideTypingIndicator(typingIndicator);
    addMessage("assistant", `Error: ${error.message}`);
  } finally {
    sendBtn.disabled = false;
    textInput.focus();
  }
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

  // Get current project name (check the appropriate input based on current mode)
  const mod = document.querySelector('input[name="mod"]:checked')?.value;
  let currentProject = '';
  if (mod === 'pico') {
    currentProject = document.getElementById('pico-project-id')?.value?.trim() || '';
  } else if (mod === 'screening') {
    currentProject = document.getElementById('screening-project-id')?.value?.trim() || '';
  } else {
    currentProject = document.getElementById('project_id')?.value?.trim() || '';
  }

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
    // Set the project name in ALL input fields (for all modes)
    document.getElementById('project_id').value = projectName;
    document.getElementById('pico-project-id').value = projectName;
    document.getElementById('screening-project-id').value = projectName;
    // Also set in header controls
    if (headerProjectInput) headerProjectInput.value = projectName;
    
    // Always load PICO data if available (regardless of current mode)
    await loadPicoData(projectId);
    
    // Clear current chat
    chatMessages.innerHTML = '';
    
    // Reset conversation ID to start fresh
    conversationId = null;
    
    // Refresh sidebar FIRST to show the updated project immediately
    await loadSidebarProjects();
    
    // Start a new conversation for this project
    await startConversation();
    
    // Update conversation meta to show project
    convMeta.textContent = `Project: ${projectName} | New Conversation`;
    
    // Show project loaded message
    const mod = document.querySelector('input[name="mod"]:checked').value;
    addMessage("assistant", `📁 **Switched to Project: ${projectName}**\n\nYou can now ask questions about the papers in this project using RAG mode, review with PICO mode, or screen papers.`);
    
  } catch (error) {
    console.error('Error loading project:', error);
    addMessage("assistant", `Error loading project: ${error.message}`);
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
    chatMessages.innerHTML = '';
    
    // Set the project name in the input
    document.getElementById('project_id').value = projectName;
    if (headerProjectInput) headerProjectInput.value = projectName;
    
    // Load messages
    messages.forEach(msg => {
      addMessage(msg.role, msg.text);
    });
    
    // Set conversation ID
    conversationId = parseInt(conversationId);
    
    // Update conversation meta
    convMeta.textContent = `Project: ${projectName} | Conversation: ${conversationId}`;
    
    // Scroll to bottom
    setTimeout(() => {
      chatMessages.scrollTo({
        top: chatMessages.scrollHeight,
        behavior: 'smooth'
      });
    }, 50);
    
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
  
  // Category navigation
  const categoryButtons = document.querySelectorAll('.settings-category');
  const categoryContents = document.querySelectorAll('.settings-category-content');
  
  // Profile/Azure settings
  const testAzureConfig = document.getElementById("test-azure-config");
  const azureEndpointInput = document.getElementById("azure-endpoint");
  const azureDirectEndpointInput = document.getElementById("azure-direct-endpoint");
  const azureOpenAIDeploymentInput = document.getElementById("azure-openai-deployment");
  const azureEmbeddingDeploymentInput = document.getElementById("azure-embedding-deployment");
  const azureTenantIdInput = document.getElementById("azure-tenant-id");
  const azureClientIdInput = document.getElementById("azure-client-id");
  const azureClientSecretInput = document.getElementById("azure-client-secret");
  const toggleAzureSecret = document.getElementById("toggle-azure-secret");
  const azureStatus = document.getElementById("azure-status");
  const refreshModelsBtn = document.getElementById("refresh-models");

  // Fetch available models from Azure and populate datalists
  function refreshAzureModels() {
    if (refreshModelsBtn) refreshModelsBtn.textContent = "Loading...";
    fetch('/api/azure-deployments')
      .then(resp => resp.json())
      .then(data => {
        // Populate chat model datalist
        const chatList = document.getElementById("chat-model-options");
        if (chatList && data.chat_models) {
          chatList.innerHTML = '';
          data.chat_models.forEach(m => {
            const opt = document.createElement('option');
            opt.value = m.deployment;
            opt.textContent = `${m.model} (${m.account}) [${m.sku}]`;
            chatList.appendChild(opt);
          });
        }
        // Populate embedding model datalist
        const embList = document.getElementById("embedding-model-options");
        if (embList && data.embedding_models) {
          embList.innerHTML = '';
          data.embedding_models.forEach(m => {
            const opt = document.createElement('option');
            opt.value = m.deployment;
            opt.textContent = `${m.model} (${m.account}) [${m.sku}]`;
            embList.appendChild(opt);
          });
        }
        if (refreshModelsBtn) refreshModelsBtn.textContent = "Refresh models from Azure";
      })
      .catch(err => {
        console.error('Failed to fetch Azure models:', err);
        if (refreshModelsBtn) refreshModelsBtn.textContent = "Refresh models from Azure";
      });
  }

  if (refreshModelsBtn) {
    refreshModelsBtn.addEventListener('click', refreshAzureModels);
  }

  // Appearance settings
  const themeSelect = document.getElementById("theme-select");
  
  // Application settings
  const defaultPapersInput = document.getElementById("default-papers");
  const defaultProjectInput = document.getElementById("default-project");
  const screeningBatchSizeInput = document.getElementById("screening-batch-size");
  const screeningStrategyInput = document.getElementById("screening-strategy");
  const screeningClassifierInput = document.getElementById("screening-classifier");
  const coldStartBatchSizeInput = document.getElementById("cold-start-batch-size");
  
  // Advanced settings
  const autoLabelIncludeThresholdInput = document.getElementById("auto-label-include-threshold");
  const autoLabelExcludeThresholdInput = document.getElementById("auto-label-exclude-threshold");
  const defaultExportFormatInput = document.getElementById("default-export-format");

  // Category switching
  if (categoryButtons.length > 0) {
    categoryButtons.forEach(button => {
      button.addEventListener('click', (e) => {
        e.preventDefault();
        const category = button.getAttribute('data-category');
        if (!category) return;
        
        // Update active state
        categoryButtons.forEach(btn => btn.classList.remove('active'));
        button.classList.add('active');
        
        // Show/hide content
        categoryContents.forEach(content => content.classList.remove('active'));
        const targetContent = document.getElementById(`${category}-settings`);
        if (targetContent) {
          targetContent.classList.add('active');
        }
      });
    });
  }
  
  // Load saved settings
  function loadSettings() {
    // Load Azure settings from backend (server-side runtime settings)
    fetch('/api/settings')
      .then(resp => resp.json())
      .then(s => {
        if (s.AZURE_EXISTING_AIPROJECT_ENDPOINT) azureEndpointInput.value = s.AZURE_EXISTING_AIPROJECT_ENDPOINT;
        if (s.AZURE_OPENAI_DIRECT_ENDPOINT && azureDirectEndpointInput) azureDirectEndpointInput.value = s.AZURE_OPENAI_DIRECT_ENDPOINT;
        if (s.AZURE_OPENAI_DEPLOYMENT_NAME) azureOpenAIDeploymentInput.value = s.AZURE_OPENAI_DEPLOYMENT_NAME;
        if (s.AZURE_OPENAI_EMBEDDING_DEPLOYMENT_NAME) azureEmbeddingDeploymentInput.value = s.AZURE_OPENAI_EMBEDDING_DEPLOYMENT_NAME;
        if (s.MICROSOFT_TENANT_ID) azureTenantIdInput.value = s.MICROSOFT_TENANT_ID;
        if (s.MICROSOFT_CLIENT_ID) azureClientIdInput.value = s.MICROSOFT_CLIENT_ID;
        if (s.MICROSOFT_CLIENT_SECRET) azureClientSecretInput.value = s.MICROSOFT_CLIENT_SECRET;
      })
      .catch(() => { /* backend unavailable, fields stay at defaults */ });
    
    // Load theme
    if (themeSelect) {
      const savedTheme = localStorage.getItem('ai4sr-theme') || 'light';
      themeSelect.value = savedTheme;
    }
    
    // Load application settings
    const savedPapers = localStorage.getItem('default_papers');
    const savedProject = localStorage.getItem('default_project');
    const savedScreeningBatchSize = localStorage.getItem('screening_batch_size');
    const savedScreeningStrategy = localStorage.getItem('screening_strategy');
    const savedScreeningClassifier = localStorage.getItem('screening_classifier');
    const savedColdStartBatchSize = localStorage.getItem('cold_start_batch_size');
    
    if (savedPapers) defaultPapersInput.value = savedPapers;
    if (savedProject) defaultProjectInput.value = savedProject;
    if (savedScreeningBatchSize) screeningBatchSizeInput.value = savedScreeningBatchSize;
    if (savedScreeningStrategy) screeningStrategyInput.value = savedScreeningStrategy;
    if (savedScreeningClassifier) screeningClassifierInput.value = savedScreeningClassifier;
    if (savedColdStartBatchSize) coldStartBatchSizeInput.value = savedColdStartBatchSize;
    
    // Load advanced settings
    const savedIncludeThreshold = localStorage.getItem('auto_label_include_threshold');
    const savedExcludeThreshold = localStorage.getItem('auto_label_exclude_threshold');
    const savedExportFormat = localStorage.getItem('default_export_format');
    
    if (savedIncludeThreshold) autoLabelIncludeThresholdInput.value = savedIncludeThreshold;
    if (savedExcludeThreshold) autoLabelExcludeThresholdInput.value = savedExcludeThreshold;
    if (savedExportFormat) defaultExportFormatInput.value = savedExportFormat;
    
    // Apply default paper limit to input fields
    if (savedPapers) {
      const paperLimitInput = document.getElementById("paper_limit");
      if (paperLimitInput) paperLimitInput.value = savedPapers;
    }
  }

  // Save settings
  function saveSettingsToStorage() {
    // Collect Azure settings
    const azureEndpoint = azureEndpointInput.value.trim();
    const azureDirectEndpoint = azureDirectEndpointInput ? azureDirectEndpointInput.value.trim() : '';
    const azureOpenAIDeployment = azureOpenAIDeploymentInput.value.trim();
    const azureEmbeddingDeployment = azureEmbeddingDeploymentInput.value.trim();
    const azureTenantId = azureTenantIdInput.value.trim();
    const azureClientId = azureClientIdInput.value.trim();
    const azureClientSecret = azureClientSecretInput.value.trim();

    // Push Azure settings to backend (persisted server-side, used by agents)
    const azureSettings = {};
    if (azureEndpoint) azureSettings.AZURE_EXISTING_AIPROJECT_ENDPOINT = azureEndpoint;
    if (azureDirectEndpoint) azureSettings.AZURE_OPENAI_DIRECT_ENDPOINT = azureDirectEndpoint;
    if (azureOpenAIDeployment) azureSettings.AZURE_OPENAI_DEPLOYMENT_NAME = azureOpenAIDeployment;
    if (azureEmbeddingDeployment) azureSettings.AZURE_OPENAI_EMBEDDING_DEPLOYMENT_NAME = azureEmbeddingDeployment;
    if (azureTenantId) azureSettings.MICROSOFT_TENANT_ID = azureTenantId;
    if (azureClientId) azureSettings.MICROSOFT_CLIENT_ID = azureClientId;
    if (azureClientSecret) azureSettings.MICROSOFT_CLIENT_SECRET = azureClientSecret;

    fetch('/api/settings', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(azureSettings)
    }).catch(err => console.error('Failed to save settings to backend:', err));
    
    // Save theme
    if (themeSelect) {
      const theme = themeSelect.value;
      localStorage.setItem('ai4sr-theme', theme);
      setTheme(theme);
    }
    
    // Save application settings
    const papers = defaultPapersInput.value;
    const project = defaultProjectInput.value.trim();
    const screeningBatchSize = Math.max(1, Math.min(100, parseInt(screeningBatchSizeInput.value) || 10));
    const screeningStrategy = screeningStrategyInput.value;
    const screeningClassifier = screeningClassifierInput.value;
    const coldStartBatchSize = Math.max(1, Math.min(50, parseInt(coldStartBatchSizeInput.value) || 10));
    
    localStorage.setItem('default_papers', papers || '10');
    if (project) localStorage.setItem('default_project', project);
    localStorage.setItem('screening_batch_size', screeningBatchSize.toString());
    localStorage.setItem('screening_strategy', screeningStrategy);
    localStorage.setItem('screening_classifier', screeningClassifier);
    localStorage.setItem('cold_start_batch_size', coldStartBatchSize.toString());
    
    // Save advanced settings
    let includeThreshold = parseFloat(autoLabelIncludeThresholdInput.value) || 0.8;
    let excludeThreshold = parseFloat(autoLabelExcludeThresholdInput.value) || 0.2;
    
    // Validate thresholds: 0 <= exclude_threshold < include_threshold <= 1
    includeThreshold = Math.max(0, Math.min(1, includeThreshold));
    excludeThreshold = Math.max(0, Math.min(1, excludeThreshold));
    if (excludeThreshold >= includeThreshold) {
      excludeThreshold = Math.max(0, includeThreshold - 0.1);
    }
    
    const exportFormat = defaultExportFormatInput.value;
    
    localStorage.setItem('auto_label_include_threshold', includeThreshold.toString());
    localStorage.setItem('auto_label_exclude_threshold', excludeThreshold.toString());
    localStorage.setItem('default_export_format', exportFormat);
    
    // Update input values to reflect validated/clamped values
    autoLabelIncludeThresholdInput.value = includeThreshold;
    autoLabelExcludeThresholdInput.value = excludeThreshold;
    
    // Update UI with saved values
    if (papers) {
      const paperLimitInput = document.getElementById("paper_limit");
      if (paperLimitInput) paperLimitInput.value = papers;
    }
  }

  // Test Azure configuration
  async function testAzureConfigFunction() {
    azureStatus.textContent = "Testing...";
    azureStatus.className = "api-status";

    try {
      const response = await fetch('/api/test-azure-config', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        }
      });

      const result = await response.json();
      
      if (response.ok && result.success) {
        azureStatus.textContent = "✓ Azure configuration is valid";
        azureStatus.className = "api-status success";
      } else {
        azureStatus.textContent = "✗ Azure configuration error: " + (result.error || "Unknown error");
        azureStatus.className = "api-status error";
      }
    } catch (error) {
      azureStatus.textContent = "✗ Test failed: " + error.message;
      azureStatus.className = "api-status error";
    }
  }

  // Event listeners
  settingsBtn.addEventListener('click', () => {
    loadSettings();
    refreshAzureModels();
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

  if (testAzureConfig) {
    testAzureConfig.addEventListener('click', testAzureConfigFunction);
  }

  if (toggleAzureSecret) {
    toggleAzureSecret.addEventListener('click', () => {
      if (azureClientSecretInput.type === 'password') {
        azureClientSecretInput.type = 'text';
        toggleAzureSecret.textContent = '🙈';
        toggleAzureSecret.title = 'Hide Secret';
      } else {
        azureClientSecretInput.type = 'password';
        toggleAzureSecret.textContent = '👁️';
        toggleAzureSecret.title = 'Show Secret';
      }
    });
  }

  // Close modal when clicking outside
  settingsModal.addEventListener('click', (e) => {
    if (e.target === settingsModal) {
      settingsModal.style.display = 'none';
    }
  });

  // Load settings on page load
  loadSettings();
}

// Create project functionality
function initCreateProject() {
  createProjectBtn.addEventListener('click', async () => {
    const projectName = prompt('Enter a name for the new project:');
    
    if (!projectName || !projectName.trim()) {
      return; // User cancelled or entered empty name
    }
    
    const trimmedName = projectName.trim();
    
    if (trimmedName.toLowerCase() === "default") {
      showNotification("Project name 'default' is reserved", 'error');
      return;
    }
    
    // Optimistic UI update: add project to sidebar immediately
    const tempProject = {
      id: 'temp-' + Date.now(),
      name: trimmedName,
      conversation_count: 0,
      paper_count: 0,
      created_at: new Date().toISOString(),
      last_conversation: null
    };
    currentProjects.push(tempProject);
    renderSidebarProjects(currentProjects);
    
    try {
      const response = await fetch('/api/projects', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: trimmedName })
      });

      if (response.ok) {
        const data = await response.json();
        showNotification(`Project '${trimmedName}' created successfully`, 'success');
        
        // Replace temp project with real project data
        const tempIndex = currentProjects.findIndex(p => p.id === tempProject.id);
        if (tempIndex !== -1) {
          currentProjects[tempIndex] = {
            id: data.project_id,
            name: trimmedName,
            conversation_count: 0,
            paper_count: 0,
            created_at: new Date().toISOString(),
            last_conversation: null
          };
        }
        renderSidebarProjects(currentProjects);
        
        // Load the new project
        await loadProject(data.project_id, trimmedName);
      } else {
        // Revert optimistic update on error
        const tempIndex = currentProjects.findIndex(p => p.id === tempProject.id);
        if (tempIndex !== -1) {
          currentProjects.splice(tempIndex, 1);
        }
        renderSidebarProjects(currentProjects);
        
        const error = await response.json();
        showNotification(`Failed to create project: ${error.error}`, 'error');
      }
    } catch (error) {
      // Revert optimistic update on error
      const tempIndex = currentProjects.findIndex(p => p.id === tempProject.id);
      if (tempIndex !== -1) {
        currentProjects.splice(tempIndex, 1);
      }
      renderSidebarProjects(currentProjects);
      
      showNotification(`Error creating project: ${error.message}`, 'error');
    }
  });
}

// Delete project functionality
function initDeleteProject() {
  deleteProjectBtn.addEventListener('click', async () => {
    // Get project name from the current mode's input field
    const mod = document.querySelector('input[name="mod"]:checked')?.value;
    let projectName = '';
    if (mod === 'pico') {
      projectName = document.getElementById("pico-project-id")?.value?.trim() || '';
    } else if (mod === 'screening') {
      projectName = document.getElementById("screening-project-id")?.value?.trim() || '';
    } else {
      projectName = document.getElementById("project_id")?.value?.trim() || '';
    }
    
    if (!projectName || projectName === "default") {
      showNotification('No project selected to delete', 'error');
      return;
    }

    // Get the actual project ID from the project name
    let projectId;
    try {
      projectId = await getOrCreateProject(projectName);
    } catch (error) {
      showNotification(`Failed to find project: ${error.message}`, 'error');
      return;
    }
    
    if (confirm(`Are you sure you want to delete "${projectName}" and all its data (papers, conversations, PICO, etc.)? This action cannot be undone.`)) {
      try {
        const response = await fetch(`/api/projects/${projectId}`, {
          method: 'DELETE'
        });

        if (response.ok) {
          showNotification('Project deleted successfully', 'success');
          
          // Reset ALL project input fields
          conversationId = null;
          document.getElementById("project_id").value = "";
          document.getElementById("pico-project-id").value = "";
          document.getElementById("screening-project-id").value = "";
          if (headerProjectInput) headerProjectInput.value = "";
          
          // Clear chat
          chatMessages.innerHTML = '';
          
          // Hide delete button
          deleteProjectBtn.style.display = 'none';
          
          // Reset conversation metadata
          convMeta.textContent = '';
          
          // Refresh sidebar IMMEDIATELY (await to ensure it completes)
          await loadSidebarProjects();
          
          // Start fresh conversation
          await startConversation();
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
    addMessage('assistant', '✅ **PICO Saved**\n\nYour PICO framework has been saved. You can now expand it to generate search queries.');
    
    // Reload PICO data to ensure form is in sync
    await loadPicoData(projectId);
  } catch (error) {
    updatePicoStatus(`Error: ${error.message}`, 'error');
    addMessage('assistant', `❌ **Error saving PICO**\n\n${error.message}`);
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
    addMessage('assistant', message);
  } catch (error) {
    updatePicoStatus(`Error: ${error.message}`, 'error');
    addMessage('assistant', `❌ **Error expanding PICO**\n\n${error.message}`);
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
    addMessage('assistant', '⏳ **Generating Corpus**\n\nFetching papers from PubMed and OpenAlex. This may take a few minutes...');
    
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
    message += `**Inserted:** ${data.inserted_count} papers with status UNSCREENED\n`;
    
    // Add abstract coverage stats if available
    if (data.abstract_coverage) {
      const coverage = data.abstract_coverage;
      message += `**Abstract Coverage:** ${coverage.with_abstracts}/${data.total_unique} (${coverage.percentage}%)\n`;
      if (coverage.without_abstracts > 0) {
        message += `⚠️ ${coverage.without_abstracts} papers are missing abstracts\n`;
      }
    }
    
    message += '\n📚 **Next Steps:**\n';
    message += '1. **Start Screening** - Review and label papers as INCLUDE or EXCLUDE\n';
    message += '2. Papers are now available in your project for manual or AI-assisted screening\n';
    message += '3. RAG embeddings have been updated - you can ask questions about the corpus';
    
    addMessage('assistant', message);
  } catch (error) {
    updatePicoStatus(`Error: ${error.message}`, 'error');
    addMessage('assistant', `❌ **Error generating corpus**\n\n${error.message}`);
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

// ==================== Screening Mode Functions ====================

let currentBatch = [];
let paperDecisions = {}; // Map of paper_id -> action ('INCLUDE', 'EXCLUDE', 'SKIP')
let screeningProjectId = null;

// Initialize screening mode
function initScreeningMode() {
  const startBtn = document.getElementById('start-screening');
  const submitBtn = document.getElementById('submit-batch');
  const finalReviewBtn = document.getElementById('final-review-button');
  
  // Check button visibility when project input changes
  const projectInput = document.getElementById('screening-project-id');
  if (projectInput) {
    // Check on blur (when user leaves the input field)
    projectInput.addEventListener('blur', async () => {
      const projectName = projectInput.value?.trim();
      if (projectName) {
        try {
          const projectId = await getOrCreateProject(projectName);
          screeningProjectId = projectId;
          await updateButtonVisibility(projectId);
        } catch (e) {
          // Project might not exist yet, that's okay
          console.log('Could not check button visibility:', e);
        }
      }
    });
    
    // Also check when Enter is pressed
    projectInput.addEventListener('keypress', async (e) => {
      if (e.key === 'Enter') {
        const projectName = projectInput.value?.trim();
        if (projectName) {
          try {
            const projectId = await getOrCreateProject(projectName);
            screeningProjectId = projectId;
            await updateButtonVisibility(projectId);
          } catch (e) {
            console.log('Could not check button visibility:', e);
          }
        }
      }
    });
  }
  
  if (startBtn) {
    startBtn.addEventListener('click', async () => {
      const projectName = projectInput?.value?.trim();
      if (!projectName) {
        updateScreeningStatus('Please enter a project name', 'error');
        return;
      }
      
      try {
        const projectId = await getOrCreateProject(projectName);
        screeningProjectId = projectId;
        await startScreening(projectId);
      } catch (error) {
        updateScreeningStatus(`Error: ${error.message}`, 'error');
      }
    });
  }
  
  if (submitBtn) {
    submitBtn.addEventListener('click', async () => {
      if (!screeningProjectId) return;
      await submitBatch(screeningProjectId);
    });
  }
  
  if (finalReviewBtn) {
    finalReviewBtn.addEventListener('click', async () => {
      if (!screeningProjectId) {
        updateScreeningStatus('Please start a screening session first', 'error');
        return;
      }
      await startAgentReview(screeningProjectId);
    });
  }
  
  // View results button (in completion state)
  const viewResultsBtn = document.getElementById('view-results-button');
  if (viewResultsBtn) {
    viewResultsBtn.addEventListener('click', async () => {
      let projectId = screeningProjectId;
      if (!projectId) {
        // Try to get project from input
        const projectInput = document.getElementById('screening-project-id')?.value?.trim();
        if (projectInput) {
          try {
            projectId = await getOrCreateProject(projectInput);
            screeningProjectId = projectId;
          } catch (e) {
            updateScreeningStatus('Please enter a valid project name', 'error');
            return;
          }
        } else {
          updateScreeningStatus('Please enter a project name first', 'error');
          return;
        }
      }
      await showResultsView(projectId);
    });
  }
  
  // View results header button (always accessible)
  const viewResultsHeaderBtn = document.getElementById('view-results-header-button');
  if (viewResultsHeaderBtn) {
    viewResultsHeaderBtn.addEventListener('click', async () => {
      let projectId = screeningProjectId;
      if (!projectId) {
        // Try to get project from input
        const projectInput = document.getElementById('screening-project-id')?.value?.trim();
        if (projectInput) {
          try {
            projectId = await getOrCreateProject(projectInput);
            screeningProjectId = projectId;
          } catch (e) {
            updateScreeningStatus('Please enter a valid project name', 'error');
            return;
          }
        } else {
          updateScreeningStatus('Please enter a project name first', 'error');
          return;
        }
      }
      await showResultsView(projectId);
    });
  }
  
  // Close results button
  const closeResultsBtn = document.getElementById('close-results-button');
  if (closeResultsBtn) {
    closeResultsBtn.addEventListener('click', () => {
      document.getElementById('results-view').style.display = 'none';
      // Show appropriate section based on state
      const completionState = document.getElementById('completion-state');
      const papersContainer = document.getElementById('papers-container');
      if (completionState && completionState.style.display !== 'none') {
        completionState.style.display = 'block';
      } else if (papersContainer && papersContainer.style.display !== 'none') {
        papersContainer.style.display = 'block';
        document.getElementById('screening-actions').style.display = 'block';
        document.getElementById('screening-progress').style.display = 'block';
      }
    });
  }
  
  // Results tabs
  const resultsTabs = document.querySelectorAll('.results-tab');
  resultsTabs.forEach(tab => {
    tab.addEventListener('click', () => {
      const tabName = tab.dataset.tab;
      // Update active tab
      resultsTabs.forEach(t => t.classList.remove('active'));
      tab.classList.add('active');
      
      // Update content
      document.querySelectorAll('.results-tab-content').forEach(content => {
        content.classList.remove('active');
      });
      document.getElementById(`${tabName}-tab-content`).classList.add('active');
      
      // Load content if needed
      if (tabName === 'papers' && screeningProjectId) {
        loadIncludedPapers(screeningProjectId);
      } else if (tabName === 'overview' && screeningProjectId) {
        loadProjectOverview(screeningProjectId);
      }
    });
  });
  
  // Auto-label button
  const autoLabelBtn = document.getElementById('auto-label-button');
  if (autoLabelBtn) {
    autoLabelBtn.addEventListener('click', async () => {
      if (!screeningProjectId) {
        updateScreeningStatus('Please start a screening session first', 'error');
        return;
      }
      await autoLabelPapers(screeningProjectId);
    });
  }
  
  // Cold-start button
  const coldStartBtn = document.getElementById('cold-start-button');
  if (coldStartBtn) {
    coldStartBtn.addEventListener('click', async () => {
      let projectId = screeningProjectId;
      if (!projectId) {
        // Try to get project from input
        const projectInput = document.getElementById('screening-project-id')?.value?.trim();
        if (projectInput) {
          try {
            projectId = await getOrCreateProject(projectInput);
            screeningProjectId = projectId;
          } catch (e) {
            updateScreeningStatus('Please enter a valid project name', 'error');
            return;
          }
        } else {
          updateScreeningStatus('Please enter a project name first', 'error');
          return;
        }
      }
      await runColdStart(projectId);
    });
  }
  
  // Review included papers button
  const reviewIncludedBtn = document.getElementById('review-included-button');
  if (reviewIncludedBtn) {
    reviewIncludedBtn.addEventListener('click', async () => {
      if (!screeningProjectId) {
        // Try to get project from input
        const projectInput = document.getElementById('screening-project-id')?.value?.trim();
        if (projectInput) {
          try {
            const projectId = await getOrCreateProject(projectInput);
            screeningProjectId = projectId;
            await startAgentReview(projectId);
            return;
          } catch (e) {
            updateScreeningStatus('Please enter a valid project name', 'error');
            return;
          }
        }
        updateScreeningStatus('Please enter a project name first', 'error');
        return;
      }
      await startAgentReview(screeningProjectId);
    });
  }
  
  // Auto-label-all button (in header)
  const autoLabelAllBtn = document.getElementById('auto-label-all-button');
  if (autoLabelAllBtn) {
    autoLabelAllBtn.addEventListener('click', async () => {
      let projectId = screeningProjectId;
      if (!projectId) {
        // Try to get project from input
        const projectInput = document.getElementById('screening-project-id')?.value?.trim();
        if (projectInput) {
          try {
            projectId = await getOrCreateProject(projectInput);
            screeningProjectId = projectId;
          } catch (e) {
            updateScreeningStatus('Please enter a valid project name', 'error');
            return;
          }
        } else {
          updateScreeningStatus('Please enter a project name first', 'error');
          return;
        }
      }
      await autoLabelAllPapers(projectId);
    });
  }
  
  // Keyboard shortcuts
  document.addEventListener('keydown', (e) => {
    if (document.querySelector('input[name="mod"]:checked')?.value !== 'screening') return;
    if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return;
    
    if (e.key === 'i' || e.key === 'I') {
      e.preventDefault();
      const firstUnlabeled = document.querySelector('.paper-card:not([data-decision])');
      if (firstUnlabeled) {
        const paperId = parseInt(firstUnlabeled.dataset.paperId);
        handlePaperAction(paperId, 'INCLUDE');
      }
    } else if (e.key === 'e' || e.key === 'E') {
      e.preventDefault();
      const firstUnlabeled = document.querySelector('.paper-card:not([data-decision])');
      if (firstUnlabeled) {
        const paperId = parseInt(firstUnlabeled.dataset.paperId);
        handlePaperAction(paperId, 'EXCLUDE');
      }
    } else if (e.key === 's' || e.key === 'S') {
      e.preventDefault();
      const firstUnlabeled = document.querySelector('.paper-card:not([data-decision])');
      if (firstUnlabeled) {
        const paperId = parseInt(firstUnlabeled.dataset.paperId);
        handlePaperAction(paperId, 'SKIP');
      }
    }
  });
}

// Start screening session
async function startScreening(projectId) {
  document.getElementById('start-screening').disabled = true;
  updateScreeningStatus('Loading papers...', 'info');
  
  // Show progress bar
  document.getElementById('screening-progress').style.display = 'block';
  
  // Load initial stats
  await updateProgress(projectId);
  await updateButtonVisibility(projectId);
  
  // Load first batch
  await loadScreeningBatch(projectId);
}

// Load screening batch
async function loadScreeningBatch(projectId) {
  try {
    updateScreeningStatus('Fetching next batch...', 'info');
    
    // Get settings from localStorage with defaults
    const batchSize = parseInt(localStorage.getItem('screening_batch_size') || '10');
    const strategy = localStorage.getItem('screening_strategy') || 'relevance';
    const classifier = localStorage.getItem('screening_classifier') || 'random_forest';
    
    // Validate and clamp batch size
    const validBatchSize = Math.max(1, Math.min(100, batchSize));
    // Validate strategy
    const validStrategy = (strategy === 'relevance' || strategy === 'uncertainty') ? strategy : 'relevance';
    // Validate classifier
    const validClassifiers = ['logistic', 'svm', 'random_forest', 'naive_bayes'];
    const validClassifier = validClassifiers.includes(classifier) ? classifier : 'random_forest';
    
    const response = await fetch(`/api/projects/${projectId}/screening/next?batch_size=${validBatchSize}&strategy=${validStrategy}&classifier=${validClassifier}`);
    
    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.error || 'Failed to fetch papers');
    }
    
    const data = await response.json();
    
    // Check if screening is done
    if (data.done === true) {
      await showCompletionState(projectId);
      return;
    }
    
    currentBatch = data.papers || [];
    
    if (currentBatch.length === 0) {
      // Check if all papers are labeled
      await checkCompletion(projectId);
      return;
    }
    
    renderPaperCards(currentBatch);
    document.getElementById('papers-container').style.display = 'block';
    document.getElementById('screening-actions').style.display = 'block';
    
    // Update message
    const stats = await fetchScreeningStats(projectId);
    if (stats.n_unlabeled > 0) {
      updateScreeningMessage(`${stats.n_unlabeled} papers remaining to review`);
      if (stats.n_labeled >= 10) {
        updateScreeningMessage(`${stats.n_unlabeled} papers remaining. Model improving as you label.`);
      }
    }
    
    // Update button visibility
    await updateButtonVisibility(projectId);
    
    updateScreeningStatus('', '');
    
  } catch (error) {
    updateScreeningStatus(`Error: ${error.message}`, 'error');
    console.error('Error loading batch:', error);
  }
}

// Render paper cards
function renderPaperCards(papers) {
  const container = document.getElementById('papers-container');
  container.innerHTML = '';
  paperDecisions = {}; // Reset decisions for new batch
  
  papers.forEach((paper, index) => {
    const card = renderPaperCard(paper, index);
    container.appendChild(card);
  });
}

// Render single paper card
function renderPaperCard(paper, index) {
  const card = document.createElement('div');
  card.className = 'paper-card';
  card.dataset.paperId = paper.id;
  
  const prob = paper.predicted_probability;
  let probBadge = '';
  if (prob !== null && prob !== undefined) {
    const probPercent = (prob * 100).toFixed(0);
    let probClass = 'prob-medium';
    if (prob >= 0.7) {
      probClass = 'prob-high';
    } else if (prob <= 0.3) {
      probClass = 'prob-low';
    }
    probBadge = `<span class="prob-badge ${probClass}">${probPercent}% likely to include</span>`;
  } else {
    probBadge = `<span class="prob-badge prob-na">No prediction (cold start)</span>`;
  }
  
  const source = paper.venue || paper.source || 'Unknown';
  const year = paper.year || 'N/A';
  
  card.innerHTML = `
    <div class="paper-card-header">
      <span class="paper-index">#${index + 1}</span>
      ${probBadge}
    </div>
    <h4 class="paper-title">${escapeHtml(paper.title || 'No title')}</h4>
    <div class="paper-meta">
      <span class="paper-source">${escapeHtml(source)}</span>
      <span class="paper-year">${year}</span>
    </div>
    <div class="paper-abstract">${escapeHtml(paper.abstract || 'No abstract available')}</div>
    <div class="paper-actions">
      <button class="paper-action-btn action-include" data-action="INCLUDE" data-paper-id="${paper.id}">
        ✅ Include
      </button>
      <button class="paper-action-btn action-exclude" data-action="EXCLUDE" data-paper-id="${paper.id}">
        ❌ Exclude
      </button>
      <button class="paper-action-btn action-skip" data-action="SKIP" data-paper-id="${paper.id}">
        ⏭️ Skip
      </button>
    </div>
  `;
  
  // Add event listeners
  card.querySelectorAll('.paper-action-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      const paperId = parseInt(btn.dataset.paperId);
      const action = btn.dataset.action;
      handlePaperAction(paperId, action);
    });
  });
  
  return card;
}

// Handle paper action
function handlePaperAction(paperId, action) {
  paperDecisions[paperId] = action;
  
  // Update card visual state
  const card = document.querySelector(`.paper-card[data-paper-id="${paperId}"]`);
  if (card) {
    card.dataset.decision = action;
    card.classList.add(`decision-${action.toLowerCase()}`);
    
    // Update button states
    card.querySelectorAll('.paper-action-btn').forEach(btn => {
      if (btn.dataset.action === action) {
        btn.classList.add('active');
      } else {
        btn.classList.remove('active');
      }
    });
  }
  
  // Enable submit button if any decisions made
  const hasDecisions = Object.keys(paperDecisions).length > 0;
  document.getElementById('submit-batch').disabled = !hasDecisions;
}

// Submit batch
async function submitBatch(projectId) {
  const submitBtn = document.getElementById('submit-batch');
  submitBtn.disabled = true;
  submitBtn.textContent = '💾 Submitting...';
  
  try {
    // Prepare labels (skip SKIP decisions)
    const labels = Object.entries(paperDecisions)
      .filter(([_, action]) => action !== 'SKIP')
      .map(([paperId, action]) => ({
        paper_id: parseInt(paperId),
        label: action
      }));
    
    if (labels.length === 0) {
      updateScreeningStatus('No labels to submit. Use Skip to leave papers unlabeled.', 'warning');
      submitBtn.disabled = false;
      submitBtn.textContent = '💾 Submit Batch';
      return;
    }
    
    const response = await fetch(`/api/projects/${projectId}/screening/label`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ labels })
    });
    
    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.error || 'Failed to save labels');
    }
    
    const data = await response.json();
    updateScreeningStatus(`✓ Saved ${data.saved} labels`, 'success');
    
    // Clear current batch
    currentBatch = [];
    paperDecisions = {};
    document.getElementById('papers-container').innerHTML = '';
    
    // Update progress and button visibility
    await updateProgress(projectId);
    await updateButtonVisibility(projectId);
    
    // Auto-fetch next batch
    setTimeout(async () => {
      await loadScreeningBatch(projectId);
    }, 500);
    
  } catch (error) {
    updateScreeningStatus(`Error: ${error.message}`, 'error');
    console.error('Error submitting batch:', error);
  } finally {
    submitBtn.disabled = false;
    submitBtn.textContent = '💾 Submit Batch';
  }
}

// Update progress bar
async function updateProgress(projectId) {
  try {
    const stats = await fetchScreeningStats(projectId);
    
    const progressBar = document.getElementById('progress-bar-fill');
    const progressLabeled = document.getElementById('progress-labeled');
    const progressTotal = document.getElementById('progress-total');
    const counterLabeled = document.getElementById('counter-labeled');
    const counterTotal = document.getElementById('counter-total');
    const counterIncluded = document.getElementById('counter-included');
    const counterExcluded = document.getElementById('counter-excluded');
    
    const percentage = stats.n_total_corpus > 0 
      ? (stats.n_labeled / stats.n_total_corpus) * 100 
      : 0;
    
    progressBar.style.width = `${percentage}%`;
    progressLabeled.textContent = stats.n_labeled;
    progressTotal.textContent = stats.n_total_corpus;
    
    // Update counters
    if (counterLabeled) counterLabeled.textContent = stats.n_labeled;
    if (counterTotal) counterTotal.textContent = stats.n_total_corpus;
    if (counterIncluded) counterIncluded.textContent = stats.n_included || 0;
    if (counterExcluded) counterExcluded.textContent = stats.n_excluded || 0;
    
    // Check classifier readiness during screening
    if (stats.classifier_ready && stats.n_unlabeled > 0) {
      const messageEl = document.getElementById('screening-message');
      if (messageEl) {
        messageEl.textContent = `${stats.n_unlabeled} papers remaining. Classifier ready for auto-labeling.`;
      }
    }
    
  } catch (error) {
    console.error('Error updating progress:', error);
  }
}

// Fetch screening stats
async function fetchScreeningStats(projectId) {
  const response = await fetch(`/api/projects/${projectId}/screening/status`);
  if (!response.ok) {
    throw new Error('Failed to fetch stats');
  }
  return await response.json();
}

// Check completion
async function checkCompletion(projectId) {
  try {
    const stats = await fetchScreeningStats(projectId);
    
    if (stats.n_unlabeled === 0 && stats.n_total_corpus > 0) {
      await showCompletionState(projectId);
    }
  } catch (error) {
    console.error('Error checking completion:', error);
  }
}

// Show completion state
async function showCompletionState(projectId) {
  try {
    const stats = await fetchScreeningStats(projectId);
    
    // Hide batch area
    document.getElementById('papers-container').style.display = 'none';
    document.getElementById('screening-actions').style.display = 'none';
    document.getElementById('completion-state').style.display = 'block';
    
    // Update completion message with included count
    const completionMessage = document.querySelector('#completion-state .completion-message p');
    if (completionMessage) {
      if (stats.n_unlabeled === 0) {
        completionMessage.textContent = `All papers have been reviewed. ${stats.n_included} papers included.`;
      } else {
        completionMessage.textContent = `Screening complete. ${stats.n_included} papers included. ${stats.n_unlabeled} papers remaining unlabeled (stopping rules triggered).`;
      }
    }
    
    // Check classifier readiness and show auto-label button if ready
    if (stats.classifier_ready !== undefined) {
      await checkClassifierReadiness(projectId);
    }
    
    updateScreeningStatus('Screening complete!', 'success');
    await updateProgress(projectId); // Update progress one last time
  } catch (error) {
    console.error('Error showing completion state:', error);
  }
}

// Check classifier readiness
async function checkClassifierReadiness(projectId) {
  try {
    const stats = await fetchScreeningStats(projectId);
    const classifierStatusEl = document.getElementById('classifier-status');
    const classifierStatusText = document.getElementById('classifier-status-text');
    const autoLabelButton = document.getElementById('auto-label-button');
    
    if (stats.classifier_ready) {
      // Classifier is ready
      classifierStatusEl.style.display = 'block';
      classifierStatusText.textContent = '✓ Classifier ready for auto-labeling';
      classifierStatusText.className = 'classifier-status-text classifier-ready';
      
      // Show auto-label button if there are unlabeled papers
      if (stats.n_unlabeled > 0) {
        autoLabelButton.style.display = 'inline-block';
      } else {
        autoLabelButton.style.display = 'none';
      }
    } else {
      // Classifier not ready yet
      classifierStatusEl.style.display = 'block';
      classifierStatusText.textContent = `⚠ Classifier not ready. Need more labeled papers (${stats.n_labeled} labeled).`;
      classifierStatusText.className = 'classifier-status-text classifier-not-ready';
      autoLabelButton.style.display = 'none';
    }
  } catch (error) {
    console.error('Error checking classifier readiness:', error);
  }
}

// Auto-label papers
async function autoLabelPapers(projectId) {
  const button = document.getElementById('auto-label-button');
  const originalText = button.textContent;
  button.disabled = true;
  button.textContent = '🤖 Auto-labeling...';
  updateScreeningStatus('Auto-labeling papers...', 'info');
  
  try {
    // Get settings from localStorage with defaults
    const classifier = localStorage.getItem('screening_classifier') || 'random_forest';
    const includeThreshold = parseFloat(localStorage.getItem('auto_label_include_threshold') || '0.8');
    const excludeThreshold = parseFloat(localStorage.getItem('auto_label_exclude_threshold') || '0.2');
    
    // Validate classifier
    const validClassifiers = ['logistic', 'svm', 'random_forest', 'naive_bayes'];
    const validClassifier = validClassifiers.includes(classifier) ? classifier : 'random_forest';
    
    // Validate thresholds
    const validIncludeThreshold = Math.max(0, Math.min(1, includeThreshold));
    const validExcludeThreshold = Math.max(0, Math.min(1, excludeThreshold));
    
    const response = await fetch(`/api/projects/${projectId}/screening/auto-label?classifier=${validClassifier}&include_threshold=${validIncludeThreshold}&exclude_threshold=${validExcludeThreshold}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' }
    });
    
    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.error || 'Failed to auto-label papers');
    }
    
    const result = await response.json();
    updateScreeningStatus(
      `✓ Auto-labeled: ${result.auto_included} included, ${result.auto_excluded} excluded, ${result.borderline} borderline`,
      'success'
    );
    
    // Update progress
    await updateProgress(projectId);
    
    // Re-check classifier readiness
    await checkClassifierReadiness(projectId);
    
  } catch (error) {
    updateScreeningStatus(`Error: ${error.message}`, 'error');
    console.error('Error auto-labeling papers:', error);
  } finally {
    button.disabled = false;
    button.textContent = originalText;
  }
}

// Start agent review
async function startAgentReview(projectId) {
  const button = document.getElementById('final-review-button');
  const originalText = button.textContent;
  button.disabled = true;
  button.textContent = '📊 Reviewing...';
  updateScreeningStatus('Starting agent review...', 'info');
  
  try {
    // Get PICO if available
    let pico = null;
    try {
      const picoResponse = await fetch(`/api/projects/${projectId}/pico`);
      if (picoResponse.ok) {
        pico = await picoResponse.json();
      }
    } catch (e) {
      // PICO not available, continue without it
    }
    
    const requestBody = { pico };
    
    // Get API key from settings if available
    const apiKeyInput = document.getElementById('openai-key');
    if (apiKeyInput && apiKeyInput.value) {
      requestBody.api_key = apiKeyInput.value;
    }
    
    const response = await fetch(`/api/projects/${projectId}/agent-review`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(requestBody)
    });
    
    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.error || 'Failed to start agent review');
    }
    
    const result = await response.json();
    updateScreeningStatus(
      `✓ Agent review complete: ${result.n_summarized} papers summarized${result.overview_generated ? ', overview generated' : ''}`,
      'success'
    );
    
    // Show view results button if we have included papers
    const viewResultsBtn = document.getElementById('view-results-button');
    if (viewResultsBtn && result.n_summarized > 0) {
      viewResultsBtn.style.display = 'inline-block';
    }
    
    // Update button visibility
    await updateButtonVisibility(screeningProjectId);
    
  } catch (error) {
    updateScreeningStatus(`Error: ${error.message}`, 'error');
    console.error('Error starting agent review:', error);
  } finally {
    button.disabled = false;
    button.textContent = originalText;
  }
}

// Update screening status message
function updateScreeningStatus(message, type) {
  const statusEl = document.getElementById('screening-status');
  if (!statusEl) return;
  
  statusEl.textContent = message;
  statusEl.className = `screening-status ${type}`;
}

// Run cold-start agent
async function runColdStart(projectId) {
  const button = document.getElementById('cold-start-button');
  const originalText = button.textContent;
  button.disabled = true;
  button.textContent = '🧊 Running...';
  updateScreeningStatus('Running cold-start agent...', 'info');
  
  try {
    // Get API key from settings if available
    const apiKeyInput = document.getElementById('openai-key');
    const requestBody = {};
    if (apiKeyInput && apiKeyInput.value) {
      requestBody.api_key = apiKeyInput.value;
    }
    
    // Get cold start batch size from localStorage with default
    const coldStartBatchSize = parseInt(localStorage.getItem('cold_start_batch_size') || '10');
    const validColdStartBatchSize = Math.max(1, Math.min(50, coldStartBatchSize));
    requestBody.n = validColdStartBatchSize;
    
    const response = await fetch(`/api/projects/${projectId}/screening/cold-start`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(requestBody)
    });
    
    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.error || 'Failed to run cold-start agent');
    }
    
    const result = await response.json();
    updateScreeningStatus(
      `✓ Cold-start complete: ${result.n_labeled_by_agent} papers labeled (${result.included_count} included, ${result.excluded_count} excluded)`,
      'success'
    );
    
    // Update progress and hide button
    await updateProgress(projectId);
    await updateButtonVisibility(projectId);
    
    // Reload batch if screening is active
    if (document.getElementById('papers-container').style.display !== 'none') {
      await loadScreeningBatch(projectId);
    }
    
  } catch (error) {
    updateScreeningStatus(`Error: ${error.message}`, 'error');
    console.error('Error running cold-start:', error);
  } finally {
    button.disabled = false;
    button.textContent = originalText;
  }
}

// Auto-label all remaining papers
async function autoLabelAllPapers(projectId) {
  const button = document.getElementById('auto-label-all-button');
  const originalText = button.textContent;
  button.disabled = true;
  button.textContent = '🤖 Auto-labeling all...';
  updateScreeningStatus('Auto-labeling all remaining papers...', 'info');
  
  try {
    // Get settings from localStorage with defaults
    const classifier = localStorage.getItem('screening_classifier') || 'random_forest';
    const includeThreshold = parseFloat(localStorage.getItem('auto_label_include_threshold') || '0.8');
    const excludeThreshold = parseFloat(localStorage.getItem('auto_label_exclude_threshold') || '0.2');
    
    // Validate classifier
    const validClassifiers = ['logistic', 'svm', 'random_forest', 'naive_bayes'];
    const validClassifier = validClassifiers.includes(classifier) ? classifier : 'random_forest';
    
    // Validate thresholds
    const validIncludeThreshold = Math.max(0, Math.min(1, includeThreshold));
    const validExcludeThreshold = Math.max(0, Math.min(1, excludeThreshold));
    
    const response = await fetch(`/api/projects/${projectId}/screening/auto-label?classifier=${validClassifier}&include_threshold=${validIncludeThreshold}&exclude_threshold=${validExcludeThreshold}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' }
    });
    
    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.error || 'Failed to auto-label papers');
    }
    
    const result = await response.json();
    updateScreeningStatus(
      `✓ Auto-labeled: ${result.auto_included} included, ${result.auto_excluded} excluded, ${result.borderline} borderline, ${result.still_unscreened} still unscreened`,
      'success'
    );
    
    // Update progress
    await updateProgress(projectId);
    await updateButtonVisibility(projectId);
    
    // Reload batch if screening is active
    if (document.getElementById('papers-container').style.display !== 'none') {
      await loadScreeningBatch(projectId);
    }
    
  } catch (error) {
    updateScreeningStatus(`Error: ${error.message}`, 'error');
    console.error('Error auto-labeling all papers:', error);
  } finally {
    button.disabled = false;
    button.textContent = originalText;
  }
}

// Update button visibility based on project state
async function updateButtonVisibility(projectId) {
  try {
    const stats = await fetchScreeningStats(projectId);
    
    // Check if PICO exists
    let hasPico = false;
    try {
      const picoResponse = await fetch(`/api/projects/${projectId}/pico`);
      hasPico = picoResponse.ok;
    } catch (e) {
      hasPico = false;
    }
    
    // Cold-start button: show if PICO exists, unscreened papers exist, and not already used
    const coldStartBtn = document.getElementById('cold-start-button');
    if (coldStartBtn) {
      const coldStartUsed = stats.cold_start_used || false;
      if (hasPico && stats.n_unlabeled > 0 && !coldStartUsed) {
        coldStartBtn.style.display = 'inline-block';
      } else {
        coldStartBtn.style.display = 'none';
      }
    }
    
    // Review button: show if there are included papers
    const reviewBtn = document.getElementById('review-included-button');
    if (reviewBtn) {
      if (stats.n_included > 0) {
        reviewBtn.style.display = 'inline-block';
      } else {
        reviewBtn.style.display = 'none';
      }
    }
    
    // View results button (in completion state): show if there are included papers
    const viewResultsBtn = document.getElementById('view-results-button');
    if (viewResultsBtn) {
      if (stats.n_included > 0) {
        viewResultsBtn.style.display = 'inline-block';
      } else {
        viewResultsBtn.style.display = 'none';
      }
    }
    
    // View results header button: show if there are included papers
    const viewResultsHeaderBtn = document.getElementById('view-results-header-button');
    if (viewResultsHeaderBtn) {
      if (stats.n_included > 0) {
        viewResultsHeaderBtn.style.display = 'inline-block';
      } else {
        viewResultsHeaderBtn.style.display = 'none';
      }
    }
    
    // Auto-label-all button: show if classifier ready and unscreened papers exist
    const autoLabelAllBtn = document.getElementById('auto-label-all-button');
    if (autoLabelAllBtn) {
      if (stats.classifier_ready && stats.n_unlabeled > 0) {
        autoLabelAllBtn.style.display = 'inline-block';
      } else {
        autoLabelAllBtn.style.display = 'none';
      }
    }
  } catch (error) {
    console.error('Error updating button visibility:', error);
  }
}

// Show results view
async function showResultsView(projectId) {
  // Hide completion state if it exists
  const completionState = document.getElementById('completion-state');
  if (completionState) {
    completionState.style.display = 'none';
  }
  
  // Hide other sections
  document.getElementById('papers-container').style.display = 'none';
  document.getElementById('screening-actions').style.display = 'none';
  document.getElementById('screening-progress').style.display = 'none';
  
  // Show results view
  document.getElementById('results-view').style.display = 'block';
  
  // Load papers tab by default
  await loadIncludedPapers(projectId);
}

// Load included papers with summaries
async function loadIncludedPapers(projectId) {
  const container = document.getElementById('included-papers-list');
  container.innerHTML = '<p>Loading papers...</p>';
  
  try {
    const response = await fetch(`/api/projects/${projectId}/included-papers`);
    if (!response.ok) {
      throw new Error('Failed to load papers');
    }
    
    const data = await response.json();
    const papers = data.papers || [];
    
    if (papers.length === 0) {
      container.innerHTML = '<p>No included papers found.</p>';
      return;
    }
    
    container.innerHTML = '';
    
    papers.forEach((paper, index) => {
      const paperCard = document.createElement('div');
      paperCard.className = 'included-paper-card';
      
      const authors = paper.authors && paper.authors.trim() ? paper.authors : 'Authors not available';
      const year = paper.year ? `(${paper.year})` : '';
      const venue = paper.venue && paper.venue.trim() ? paper.venue : 'Unknown venue';
      
      let linksHtml = '';
      if (paper.doi_url) {
        linksHtml += `<a href="${paper.doi_url}" target="_blank" class="paper-link">DOI</a>`;
      }
      if (paper.pubmed_url) {
        linksHtml += `<a href="${paper.pubmed_url}" target="_blank" class="paper-link">PubMed</a>`;
      }
      if (paper.url && paper.url !== paper.doi_url && paper.url !== paper.pubmed_url) {
        linksHtml += `<a href="${paper.url}" target="_blank" class="paper-link">View</a>`;
      }
      
      let summaryHtml = '';
      if (paper.summary) {
        summaryHtml = `
          <div class="paper-summary">
            <h4>📋 Agent Summary</h4>
            ${paper.abstract ? `<div class="summary-section"><strong>Abstract:</strong> ${escapeHtml(paper.abstract)}</div>` : ''}
            <div class="summary-section">
              <strong>Population:</strong> ${escapeHtml(paper.summary.population || 'N/A')}
            </div>
            <div class="summary-section">
              <strong>Intervention:</strong> ${escapeHtml(paper.summary.intervention || 'N/A')}
            </div>
            <div class="summary-section">
              <strong>Comparator:</strong> ${escapeHtml(paper.summary.comparator || 'N/A')}
            </div>
            <div class="summary-section">
              <strong>Outcomes:</strong> ${escapeHtml(paper.summary.outcomes || 'N/A')}
            </div>
            <div class="summary-section">
              <strong>Main Findings:</strong> ${escapeHtml(paper.summary.main_findings || 'N/A')}
            </div>
            <div class="summary-section">
              <strong>Sample Size:</strong> ${escapeHtml(paper.summary.sample_size || 'N/A')}
            </div>
            ${paper.summary.notes ? `<div class="summary-section"><strong>Notes:</strong> ${escapeHtml(paper.summary.notes)}</div>` : ''}
          </div>
        `;
      } else {
        summaryHtml = '<div class="paper-summary"><p class="no-summary">No summary available. Run agent review to generate summaries.</p></div>';
      }
      
      paperCard.innerHTML = `
        <div class="included-paper-header">
          <h3>${index + 1}. ${escapeHtml(paper.title || 'No title')}</h3>
          <div class="paper-meta-info">
            <div class="paper-authors">
              <strong>Authors:</strong> 
              <span class="${authors === 'Authors not available' ? 'missing-data' : ''}">${escapeHtml(authors)}</span>
            </div>
            <div class="paper-venue-year">
              <strong>Venue:</strong> ${escapeHtml(venue)} ${year}
            </div>
            ${paper.doi ? `<div class="paper-ids"><strong>DOI:</strong> ${escapeHtml(paper.doi)}</div>` : ''}
            ${paper.pmid ? `<div class="paper-ids"><strong>PMID:</strong> ${escapeHtml(paper.pmid)}</div>` : ''}
            ${linksHtml ? `<div class="paper-links">${linksHtml}</div>` : ''}
          </div>
        </div>
        <div class="paper-abstract-section">
          <strong>Abstract:</strong>
          <p>${escapeHtml(paper.abstract || 'No abstract available')}</p>
        </div>
        ${summaryHtml}
      `;
      
      container.appendChild(paperCard);
    });
    
  } catch (error) {
    container.innerHTML = `<p class="error">Error loading papers: ${error.message}</p>`;
    console.error('Error loading included papers:', error);
  }
}

// Load project overview
async function loadProjectOverview(projectId) {
  const container = document.getElementById('project-overview');
  container.innerHTML = '<p>Loading overview...</p>';
  
  try {
    const response = await fetch(`/api/projects/${projectId}/overview`);
    if (!response.ok) {
      if (response.status === 404) {
        container.innerHTML = '<p class="no-overview">No overview available. Run agent review to generate an overview.</p>';
        return;
      }
      throw new Error('Failed to load overview');
    }
    
    const overview = await response.json();
    
    container.innerHTML = `
      <div class="overview-content">
        <div class="overview-header">
          <h3>Project Overview</h3>
          <p class="overview-meta">Based on ${overview.summary_count || 0} paper summaries</p>
        </div>
        <div class="overview-text">
          ${formatMessage(overview.overview || 'No overview available')}
        </div>
        ${overview.pico_context ? `
          <div class="overview-pico">
            <h4>PICO Context</h4>
            <pre>${escapeHtml(JSON.stringify(overview.pico_context, null, 2))}</pre>
          </div>
        ` : ''}
      </div>
    `;
    
  } catch (error) {
    container.innerHTML = `<p class="error">Error loading overview: ${error.message}</p>`;
    console.error('Error loading overview:', error);
  }
}

// Update screening message (below progress bar)
function updateScreeningMessage(message) {
  const messageEl = document.getElementById('screening-message');
  if (messageEl) {
    messageEl.textContent = message;
  }
}

// Export functionality
function initExport() {
  const exportButton = document.getElementById('export-button');
  const exportMenu = document.getElementById('export-menu');
  const exportOptions = document.querySelectorAll('.export-option');
  
  if (!exportButton || !exportMenu) return;
  
  // Toggle dropdown
  exportButton.addEventListener('click', (e) => {
    e.stopPropagation();
    const isVisible = exportMenu.style.display === 'block';
    exportMenu.style.display = isVisible ? 'none' : 'block';
  });
  
  // Close dropdown when clicking outside
  document.addEventListener('click', (e) => {
    if (!exportButton.contains(e.target) && !exportMenu.contains(e.target)) {
      exportMenu.style.display = 'none';
    }
  });
  
  // Handle export option clicks
  exportOptions.forEach(option => {
    option.addEventListener('click', async (e) => {
      e.stopPropagation();
      const format = option.dataset.format;
      await exportPapers(format);
      exportMenu.style.display = 'none';
    });
  });
}

// Export papers in specified format
async function exportPapers(format) {
  let projectId = screeningProjectId;
  if (!projectId) {
    // Try to get project from input
    const projectInput = document.getElementById('screening-project-id')?.value?.trim();
    if (projectInput) {
      try {
        projectId = await getOrCreateProject(projectInput);
        screeningProjectId = projectId;
      } catch (e) {
        updateScreeningStatus('Please enter a valid project name', 'error');
        return;
      }
    } else {
      updateScreeningStatus('Please enter a project name first', 'error');
      return;
    }
  }
  
  // Show loading state
  const exportButton = document.getElementById('export-button');
  const originalText = exportButton.innerHTML;
  exportButton.disabled = true;
  exportButton.innerHTML = '<span class="export-icon">⏳</span><span class="export-text">Exporting...</span><span class="export-arrow">▼</span>';
  
  try {
    const response = await fetch(`/api/projects/${projectId}/export?format=${format}`);
    
    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.error || 'Export failed');
    }
    
    // Get filename from Content-Disposition header or generate one
    const contentDisposition = response.headers.get('Content-Disposition');
    let filename = `export_${new Date().toISOString().split('T')[0]}.${format === 'bibtex' ? 'bib' : format === 'ris' ? 'ris' : format}`;
    if (contentDisposition) {
      const filenameMatch = contentDisposition.match(/filename="(.+)"/);
      if (filenameMatch) {
        filename = filenameMatch[1];
      }
    }
    
    // Download file
    const blob = await response.blob();
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    window.URL.revokeObjectURL(url);
    
    updateScreeningStatus(`✓ Exported ${format.toUpperCase()} successfully`, 'success');
    
  } catch (error) {
    updateScreeningStatus(`Error: ${error.message}`, 'error');
    console.error('Export error:', error);
  } finally {
    exportButton.disabled = false;
    exportButton.innerHTML = originalText;
  }
}

// Initialize header controls sync
if (headerProjectInput) {
  headerProjectInput.addEventListener('input', () => {
    const projectId = document.getElementById("project_id");
    if (projectId) projectId.value = headerProjectInput.value;
  });
}

if (headerPaperLimitInput) {
  headerPaperLimitInput.addEventListener('input', () => {
    const paperLimit = document.getElementById("paper_limit");
    if (paperLimit) paperLimit.value = headerPaperLimitInput.value;
  });
}

// Initialize theme and start conversation
initTheme();
initSidebar();
initSettings();
initCreateProject();
initDeleteProject();
initPicoMode();
initDbViewer();
initExport();

// Add auth event listeners
if (loginBtn) {
  loginBtn.addEventListener('click', handleLogin);
}
if (logoutBtn) {
  logoutBtn.addEventListener('click', handleLogout);
}

// Check auth status on page load
checkAuthStatus();

startConversation();
