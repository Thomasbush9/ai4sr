let conversationId = null;

const chat = document.getElementById("chat");
const input = document.getElementById("input");
const sendBtn = document.getElementById("send");
const convMeta = document.getElementById("conv-meta");
const exportBtn = document.getElementById("export-chat");
const helpBtn = document.getElementById("help-shortcuts");
const themeBtn = document.getElementById("theme-toggle");

// Sidebar elements
const sidebar = document.getElementById("sidebar");
const sidebarToggle = document.getElementById("sidebar-toggle");
const sidebarToggleHeader = document.getElementById("sidebar-toggle-header");
const sidebarToggleFloat = document.getElementById("sidebar-toggle-float");
const sidebarProjects = document.getElementById("sidebar-projects");
const sidebarSearch = document.getElementById("sidebar-search");

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
    const modeIcon = currentMode === 'literature' ? '🔍' : '💬';
    const modeName = currentMode === 'literature' ? 'Literature Review' : 'RAG Chat';
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
  const modeIcon = currentMode === 'literature' ? '🔍' : '💬';
  const modeName = currentMode === 'literature' ? 'Literature Review' : 'RAG Chat';
  
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
    if (paper.pdf_path) {
      links.push(`<a href="${escapeHtml(paper.pdf_path)}" target="_blank" class="link-btn pdf-link">PDF</a>`);
    }
    if (paper.url && !paper.doi_url && !paper.pubmed_url) {
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
  
  convMeta.textContent = `Session #${conversationId} · ${mod === 'literature' ? 'Literature Review' : 'RAG Chat'}`;
  
  // Refresh sidebar to show new conversation
  loadSidebarProjects();
  
  // Only show welcome message if chat is empty
  if (chat.children.length === 0) {
    if (mod === 'literature') {
      addMessage("assistant", `🔍 **Literature Review Mode Active**\n\nI can help you:\n• Find relevant papers for your research topic\n• Analyze and summarize research findings\n• Generate comprehensive literature reviews\n• Screen papers based on your criteria\n\nWhat research question or topic would you like me to explore?`, mod);
    } else {
      addMessage("assistant", `💬 **RAG Chat Mode Active**\n\nI can help you:\n• Answer questions about your existing documents\n• Search through your uploaded papers\n• Provide insights from your research collection\n\nWhat would you like to know about your documents?`, mod);
    }
  } else {
    // Add mode switch notification
    addMessage("assistant", `Mode switched to **${mod === 'literature' ? 'Literature Review' : 'RAG Chat'}**. How can I help you?`, mod);
  }
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
  r.addEventListener("change", startConversation);
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

// Initialize theme and start conversation
initTheme();
initSidebar();
startConversation();
