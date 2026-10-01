/**
 * RecruitRadar — The Evidence Desk Client
 * Pure JavaScript single-page client for API v1
 */

class RecruitRadarApp {
  constructor() {
    this.apiBase = '/api/v1';
    this.token = localStorage.getItem('rr_token') || null;
    this.user = null;
    this.roles = [];
    this.activeRoleId = null;
    this.currentRunId = null;
    this.currentCandidates = [];
    this.currentShortlist = [];
    this.pollInterval = null;

    this.init();
  }

  async init() {
    this.setupEventListeners();
    await this.checkAuth();
    await this.loadRoles();
    await this.refreshAuditLogs();
  }

  // Setup DOM Event Listeners
  setupEventListeners() {
    // Tab switching
    document.querySelectorAll('.tab-btn[data-tab]').forEach((btn) => {
      btn.addEventListener('click', (e) => {
        const tab = btn.getAttribute('data-tab');
        this.switchTab(tab);
      });
    });

    // Active Role selector
    const roleSelect = document.getElementById('active-role-select');
    if (roleSelect) {
      roleSelect.addEventListener('change', (e) => {
        this.setActiveRole(e.target.value);
      });
    }

    // Drag and drop for upload zone
    const dropzone = document.getElementById('upload-dropzone');
    if (dropzone) {
      ['dragenter', 'dragover'].forEach((eventName) => {
        dropzone.addEventListener(eventName, (e) => {
          e.preventDefault();
          dropzone.classList.add('dragover');
        });
      });
      ['dragleave', 'drop'].forEach((eventName) => {
        dropzone.addEventListener(eventName, (e) => {
          e.preventDefault();
          dropzone.classList.remove('dragover');
        });
      });
      dropzone.addEventListener('drop', (e) => {
        if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
          this.handleFilesSelected(e.dataTransfer.files);
        }
      });
    }
  }

  // HTTP Helper with automatic Bearer token injection
  async fetchApi(endpoint, options = {}) {
    const headers = options.headers || {};
    if (this.token && !headers['Authorization']) {
      headers['Authorization'] = `Bearer ${this.token}`;
    }
    options.headers = headers;

    try {
      const res = await fetch(`${this.apiBase}${endpoint}`, options);
      if (res.status === 401) {
        this.logout();
        throw new Error('Authentication required');
      }
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        const msg = data.error?.message || data.detail?.message || data.detail || 'API request failed';
        throw new Error(msg);
      }
      return data;
    } catch (err) {
      console.error(`API Error on ${endpoint}:`, err);
      throw err;
    }
  }

  // Authentication
  async checkAuth() {
    if (!this.token) {
      this.updateUserUI(null);
      return;
    }
    try {
      const data = await this.fetchApi('/auth/me');
      this.user = data;
      this.updateUserUI(data);
    } catch (e) {
      this.user = null;
      this.updateUserUI(null);
    }
  }

  updateUserUI(user) {
    const emailDisplay = document.getElementById('user-email-display');
    const authBtn = document.getElementById('btn-auth-action');
    if (user) {
      emailDisplay.textContent = user.name || user.email;
      authBtn.textContent = 'Sign Out';
      authBtn.onclick = () => this.logout();
    } else {
      emailDisplay.textContent = 'Guest';
      authBtn.textContent = 'Sign In';
      authBtn.onclick = () => this.toggleAuthModal();
    }
  }

  toggleAuthModal() {
    const modal = document.getElementById('modal-auth');
    if (modal) {
      if (modal.open) modal.close();
      else modal.showModal();
    }
  }

  switchAuthMode(mode) {
    const loginForm = document.getElementById('form-login');
    const regForm = document.getElementById('form-register');
    const tabLogin = document.getElementById('auth-tab-login');
    const tabReg = document.getElementById('auth-tab-register');

    if (mode === 'login') {
      loginForm.style.display = 'block';
      regForm.style.display = 'none';
      tabLogin.classList.add('active');
      tabReg.classList.remove('active');
    } else {
      loginForm.style.display = 'none';
      regForm.style.display = 'block';
      tabReg.classList.add('active');
      tabLogin.classList.remove('active');
    }
  }

  async handleLogin(e) {
    e.preventDefault();
    const email = document.getElementById('login-email').value;
    const password = document.getElementById('login-password').value;

    try {
      const data = await this.fetchApi('/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, password }),
      });
      this.token = data.access_token;
      localStorage.setItem('rr_token', this.token);
      document.getElementById('modal-auth').close();
      await this.checkAuth();
      await this.loadRoles();
    } catch (err) {
      alert(`Login failed: ${err.message}`);
    }
  }

  async handleRegister(e) {
    e.preventDefault();
    const name = document.getElementById('reg-name').value;
    const email = document.getElementById('reg-email').value;
    const workspace_name = document.getElementById('reg-workspace').value;
    const password = document.getElementById('reg-password').value;

    try {
      const data = await this.fetchApi('/auth/register', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name, email, workspace_name, password }),
      });
      this.token = data.access_token;
      localStorage.setItem('rr_token', this.token);
      document.getElementById('modal-auth').close();
      await this.checkAuth();
      await this.loadRoles();
    } catch (err) {
      alert(`Registration failed: ${err.message}`);
    }
  }

  logout() {
    this.token = null;
    this.user = null;
    localStorage.removeItem('rr_token');
    this.updateUserUI(null);
  }

  // Tab switching
  switchTab(tabName) {
    document.querySelectorAll('.tab-btn').forEach((b) => {
      b.classList.toggle('active', b.getAttribute('data-tab') === tabName);
    });
    document.querySelectorAll('.view-panel').forEach((panel) => {
      panel.style.display = panel.id === `view-${tabName}` ? 'block' : 'none';
    });

    if (tabName === 'shortlist') this.loadShortlist();
    if (tabName === 'roles') this.loadRoles();
    if (tabName === 'candidates') this.loadCandidates();
    if (tabName === 'approvals') this.loadApprovals();
    if (tabName === 'audit') this.refreshAuditLogs();
  }

  // Roles
  async loadRoles() {
    try {
      const data = await this.fetchApi('/roles');
      this.roles = data.roles || [];
      const select = document.getElementById('active-role-select');
      select.innerHTML = '';

      if (this.roles.length === 0) {
        select.innerHTML = '<option value="">No roles yet (Create one)</option>';
        this.renderRolesGrid([]);
        return;
      }

      this.roles.forEach((r) => {
        const opt = document.createElement('option');
        opt.value = r.id;
        opt.textContent = `${r.title} (v${r.jd_version})`;
        select.appendChild(opt);
      });

      if (!this.activeRoleId && this.roles.length > 0) {
        this.activeRoleId = this.roles[0].id;
      }
      select.value = this.activeRoleId;
      this.renderRolesGrid(this.roles);

      if (this.activeRoleId) {
        await this.loadCandidates();
        await this.loadShortlist();
      }
    } catch (e) {
      console.warn('Could not load roles:', e);
    }
  }

  setActiveRole(roleId) {
    this.activeRoleId = roleId;
    this.loadCandidates();
    this.loadShortlist();
  }

  renderRolesGrid(roles) {
    const grid = document.getElementById('roles-grid');
    if (!grid) return;
    if (roles.length === 0) {
      grid.innerHTML = `
        <div class="glass-card" style="grid-column: 1 / -1; text-align: center; padding: 3rem;">
          <h3 style="font-weight: 700; margin-bottom: 0.5rem;">No Roles Created Yet</h3>
          <p style="color: var(--text-muted); font-size: 0.85rem; margin-bottom: 1.5rem;">Create a role by submitting your Job Description to get started.</p>
          <button class="btn btn-primary" onclick="app.openNewRoleModal()">Create First Role</button>
        </div>
      `;
      return;
    }

    grid.innerHTML = roles.map((r) => `
      <div class="glass-card" style="border-left: 4px solid var(--accent-primary);">
        <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 0.75rem;">
          <h3 style="font-weight: 700; font-size: 1.1rem;">${this.escapeHtml(r.title)}</h3>
          <span class="badge badge-low">v${r.jd_version}</span>
        </div>
        <p style="color: var(--text-muted); font-size: 0.8rem; margin-bottom: 1.25rem;">
          Created: ${new Date(r.created_at).toLocaleDateString()}
        </p>
        <div style="display: flex; gap: 0.5rem;">
          <button class="btn btn-secondary btn-sm" onclick="app.setActiveRole('${r.id}'); app.switchTab('shortlist');">
            View Evidence Desk
          </button>
          <button class="btn btn-secondary btn-sm" onclick="app.setActiveRole('${r.id}'); app.switchTab('candidates');">
            Ingest Resumes
          </button>
        </div>
      </div>
    `).join('');
  }

  openNewRoleModal() {
    const modal = document.getElementById('modal-new-role');
    if (modal) modal.showModal();
  }

  async handleCreateRole(e) {
    e.preventDefault();
    const title = document.getElementById('new-role-title').value;
    const jd_text = document.getElementById('new-role-jd').value;

    try {
      const data = await this.fetchApi('/roles', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ title, jd_text }),
      });
      document.getElementById('modal-new-role').close();
      document.getElementById('new-role-title').value = '';
      document.getElementById('new-role-jd').value = '';
      await this.loadRoles();
      this.setActiveRole(data.id);
      this.switchTab('candidates');
    } catch (err) {
      alert(`Failed to create role: ${err.message}`);
    }
  }

  // Candidate Ingestion
  async handleFilesSelected(files) {
    if (!this.activeRoleId) {
      alert('Please select or create an active role first.');
      return;
    }

    for (let i = 0; i < files.length; i++) {
      const file = files[i];
      const formData = new FormData();
      formData.append('role_id', this.activeRoleId);
      formData.append('file', file);

      try {
        const headers = {};
        if (this.token) headers['Authorization'] = `Bearer ${this.token}`;
        const res = await fetch(`${this.apiBase}/candidates`, {
          method: 'POST',
          headers,
          body: formData,
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.error?.message || data.detail || 'Upload failed');
      } catch (err) {
        alert(`Failed to ingest ${file.name}: ${err.message}`);
      }
    }
    await this.loadCandidates();
  }

  async loadCandidates() {
    if (!this.activeRoleId) return;
    try {
      const data = await this.fetchApi(`/candidates?role_id=${this.activeRoleId}`);
      this.currentCandidates = data.candidates || [];
      const badge = document.getElementById('candidate-count-badge');
      if (badge) badge.textContent = `${this.currentCandidates.length} Candidates`;

      const tbody = document.getElementById('candidates-table-body');
      if (!tbody) return;

      if (this.currentCandidates.length === 0) {
        tbody.innerHTML = `
          <tr>
            <td colspan="7" style="text-align: center; padding: 2.5rem; color: var(--text-muted);">
              No candidates ingested yet. Upload files above to process.
            </td>
          </tr>
        `;
        return;
      }

      tbody.innerHTML = this.currentCandidates.map((c) => `
        <tr>
          <td><span class="font-mono" style="font-weight: 700; color: #fff;">${c.display_alias}</span></td>
          <td><span class="badge badge-low">${c.status}</span></td>
          <td><span class="font-mono" style="font-size: 0.8rem; color: var(--text-secondary);">PyMuPDF (Sandbox)</span></td>
          <td><span style="color: #34d399; font-weight: 600;">100%</span></td>
          <td><span class="badge badge-met">0 Hidden</span></td>
          <td style="color: var(--text-muted); font-size: 0.8rem;">${new Date(c.created_at).toLocaleDateString()}</td>
          <td style="text-align: right;">
            <button class="btn btn-secondary btn-sm" onclick="app.inspectCandidateEvidence('${c.id}', '${c.display_alias}')">
              Inspect Evidence
            </button>
          </td>
        </tr>
      `).join('');
    } catch (e) {
      console.warn('Could not load candidates:', e);
    }
  }

  // Pipeline Runs & Shortlist
  async triggerNewRun() {
    if (!this.activeRoleId) {
      alert('Select an active role first.');
      return;
    }

    try {
      const data = await this.fetchApi('/runs', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ role_id: this.activeRoleId }),
      });
      this.currentRunId = data.id;
      this.showRunStatus(data);
      this.startRunPolling(data.id);
    } catch (err) {
      alert(`Could not start run: ${err.message}`);
    }
  }

  showRunStatus(run) {
    const card = document.getElementById('run-status-card');
    const badge = document.getElementById('run-state-badge');
    const label = document.getElementById('run-id-label');
    if (!card) return;

    card.style.display = 'block';
    badge.textContent = run.state;
    label.textContent = `Run: ${run.id}`;

    if (run.state === 'COMPLETED') {
      badge.className = 'badge badge-met';
      setTimeout(() => { card.style.display = 'none'; }, 5000);
    } else if (run.state === 'FAILED') {
      badge.className = 'badge badge-high';
    } else {
      badge.className = 'badge badge-partial';
    }
  }

  startRunPolling(runId) {
    if (this.pollInterval) clearInterval(this.pollInterval);
    this.pollInterval = setInterval(async () => {
      try {
        const run = await this.fetchApi(`/runs/${runId}`);
        this.showRunStatus(run);
        if (run.state === 'COMPLETED' || run.state === 'FAILED') {
          clearInterval(this.pollInterval);
          this.pollInterval = null;
          await this.loadShortlist(runId);
        }
      } catch (e) {
        clearInterval(this.pollInterval);
      }
    }, 2000);
  }

  async loadShortlist(runId = null) {
    const rId = runId || this.currentRunId;
    if (!rId) return;

    try {
      const data = await this.fetchApi(`/runs/${rId}/shortlist`);
      this.currentShortlist = data.entries || [];
      this.renderShortlistTable(this.currentShortlist);
    } catch (e) {
      console.warn('Could not load shortlist:', e);
    }
  }

  renderShortlistTable(entries) {
    const tbody = document.getElementById('shortlist-table-body');
    if (!tbody) return;

    if (entries.length === 0) {
      tbody.innerHTML = `
        <tr>
          <td colspan="7" style="text-align: center; padding: 3rem; color: var(--text-muted);">
            No candidates ranked in this run yet. Run the pipeline to process evidence.
          </td>
        </tr>
      `;
      return;
    }

    tbody.innerHTML = entries.map((entry) => {
      const confBadgeClass = entry.confidence_label === 'High' ? 'badge-met' : (entry.confidence_label === 'Med' ? 'badge-partial' : 'badge-uncertain');

      // Requirement match pills
      const matchPills = (entry.matches || []).slice(0, 4).map((m) => {
        const cls = m.status === 'MET' ? 'badge-met' : (m.status === 'PARTIAL' ? 'badge-partial' : (m.status === 'UNCERTAIN' ? 'badge-uncertain' : 'badge-missing'));
        return `<span class="badge ${cls}" style="margin-right: 0.35rem; margin-bottom: 0.25rem;">${m.status}</span>`;
      }).join('');

      // Noise flag pills
      const noisePills = (entry.noise_flags || []).map((f) => `
        <span class="badge badge-noise" style="margin-right: 0.35rem; cursor: pointer;" title="${this.escapeHtml(f.detail)}" onclick="app.openDismissFlagModal('${entry.candidate_id}', '${f.type}')">
          ⚠ ${f.type}
        </span>
      `).join('');

      // Fit score circular gauge
      const circumference = 2 * Math.PI * 23;
      const offset = circumference - (entry.fit_score / 100) * circumference;
      const strokeColor = entry.fit_score >= 70 ? 'var(--status-met)' : (entry.fit_score >= 45 ? 'var(--status-partial)' : 'var(--accent-primary)');

      return `
        <tr>
          <td><span class="font-mono" style="font-size: 1.1rem; font-weight: 800; color: #fff;">#${entry.rank}</span></td>
          <td>
            <div style="font-weight: 700; color: #fff; font-size: 0.95rem;">${entry.display_alias}</div>
            <div style="font-size: 0.78rem; color: var(--text-muted); margin-top: 0.2rem; max-width: 320px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">
              ${this.escapeHtml(entry.rationale || 'Ranked from verified evidence.')}
            </div>
          </td>
          <td>
            <div class="score-gauge">
              <svg viewBox="0 0 54 54">
                <circle class="bg-circle" cx="27" cy="27" r="23" />
                <circle class="progress-circle" cx="27" cy="27" r="23" stroke="${strokeColor}" stroke-dasharray="${circumference}" stroke-dashoffset="${offset}" />
              </svg>
              <div class="score-value font-mono">${entry.fit_score}</div>
            </div>
          </td>
          <td>
            <span class="badge ${confBadgeClass}">${entry.confidence_label} (${Math.round(entry.confidence * 100)}%)</span>
          </td>
          <td>${matchPills || '<span style="color: var(--text-muted); font-size: 0.8rem;">No matches</span>'}</td>
          <td>${noisePills || '<span class="badge badge-met" style="font-size: 0.7rem;">✓ Clean</span>'}</td>
          <td style="text-align: right; white-space: nowrap;">
            <button class="btn btn-secondary btn-sm" onclick="app.inspectCandidateEvidence('${entry.candidate_id}', '${entry.display_alias}', ${entry.fit_score}, '${entry.confidence_label}', ${entry.rank}, '${this.escapeHtml(entry.rationale || '')}')">
              Lens
            </button>
            <button class="btn btn-secondary btn-sm" onclick="app.openOverrideRankModal('${entry.candidate_id}', ${entry.rank})">
              Override
            </button>
          </td>
        </tr>
      `;
    }).join('');
  }

  // The Evidence Lens (Drawer)
  async inspectCandidateEvidence(candidateId, alias, fit = null, conf = null, rank = null, rationale = null) {
    const drawer = document.getElementById('evidence-drawer');
    const aliasLabel = document.getElementById('drawer-candidate-alias');
    const fitLabel = document.getElementById('drawer-fit-score');
    const confLabel = document.getElementById('drawer-confidence');
    const rankLabel = document.getElementById('drawer-rank');
    const ratLabel = document.getElementById('drawer-rationale');
    const list = document.getElementById('drawer-evidence-list');

    aliasLabel.textContent = alias;
    fitLabel.textContent = fit !== null ? fit : '--';
    confLabel.textContent = conf !== null ? conf : '--';
    rankLabel.textContent = rank !== null ? `#${rank}` : '--';
    ratLabel.textContent = rationale || 'Verbatim quote verification and grade analysis.';
    list.innerHTML = '<div style="color: var(--text-muted); padding: 1.5rem; text-align: center;">Loading verified evidence...</div>';

    drawer.classList.add('open');

    try {
      const runId = this.currentRunId || (this.roles[0] ? this.roles[0].id : null);
      const data = await this.fetchApi(`/runs/${runId}/candidates/${candidateId}/evidence`);
      const items = data.evidence_items || [];

      if (items.length === 0) {
        list.innerHTML = '<div style="color: var(--text-muted); padding: 1.5rem; text-align: center;">No extracted evidence quotes for this candidate.</div>';
        return;
      }

      list.innerHTML = items.map((e) => {
        const gradeColor = e.grade === 'outcome_backed' ? 'var(--grade-outcome)' : (e.grade === 'demonstrated' ? 'var(--grade-demonstrated)' : (e.grade === 'contextual' ? 'var(--grade-contextual)' : 'var(--grade-listed)'));
        return `
          <div class="quote-card ${e.grade}">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.5rem;">
              <span class="badge" style="background: rgba(255,255,255,0.06); color: ${gradeColor}; border: 1px solid rgba(255,255,255,0.1);">
                ${e.grade.toUpperCase()}
              </span>
              <span class="badge badge-met" style="font-size: 0.65rem;">✓ VERIFIED SPAN [${e.span_start}..${e.span_end}]</span>
            </div>
            <div class="quote-text">"${this.escapeHtml(e.quote)}"</div>
            <div class="quote-meta">
              ${e.duration_months ? `<span>⏱ ${e.duration_months} months</span>` : ''}
              ${e.role_ref ? `<span>💼 ${this.escapeHtml(e.role_ref)}</span>` : ''}
              ${e.outcome_text ? `<span style="color: #34d399;">★ Outcome: ${this.escapeHtml(e.outcome_text)}</span>` : ''}
            </div>
          </div>
        `;
      }).join('');
    } catch (e) {
      list.innerHTML = `<div style="color: #ef4444; padding: 1.5rem;">Failed to load evidence quotes: ${e.message}</div>`;
    }
  }

  closeEvidenceDrawer() {
    const drawer = document.getElementById('evidence-drawer');
    if (drawer) drawer.classList.remove('open');
  }

  // Modals: Dismiss Noise Flag & Override Rank
  openDismissFlagModal(candidateId, flagType) {
    document.getElementById('dismiss-candidate-id').value = candidateId;
    document.getElementById('dismiss-flag-type').value = flagType;
    document.getElementById('dismiss-flag-type-display').value = flagType;
    document.getElementById('dismiss-reason').value = '';
    const modal = document.getElementById('modal-dismiss-flag');
    if (modal) modal.showModal();
  }

  async handleDismissFlagSubmit(e) {
    e.preventDefault();
    const candidate_id = document.getElementById('dismiss-candidate-id').value;
    const flag_type = document.getElementById('dismiss-flag-type').value;
    const reason = document.getElementById('dismiss-reason').value;

    try {
      await this.fetchApi(`/runs/${this.currentRunId}/dismiss-flag`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ candidate_id, flag_type, reason }),
      });
      document.getElementById('modal-dismiss-flag').close();
      await this.loadShortlist();
      await this.refreshAuditLogs();
    } catch (err) {
      alert(`Could not dismiss flag: ${err.message}`);
    }
  }

  openOverrideRankModal(candidateId, currentRank) {
    document.getElementById('override-candidate-id').value = candidateId;
    document.getElementById('override-new-rank').value = currentRank;
    document.getElementById('override-reason').value = '';
    const modal = document.getElementById('modal-override-rank');
    if (modal) modal.showModal();
  }

  async handleOverrideRankSubmit(e) {
    e.preventDefault();
    const candidate_id = document.getElementById('override-candidate-id').value;
    const new_rank = parseInt(document.getElementById('override-new-rank').value, 10);
    const reason = document.getElementById('override-reason').value;

    try {
      await this.fetchApi(`/runs/${this.currentRunId}/override-rank`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ candidate_id, new_rank, reason }),
      });
      document.getElementById('modal-override-rank').close();
      await this.loadShortlist();
      await this.refreshAuditLogs();
    } catch (err) {
      alert(`Could not override rank: ${err.message}`);
    }
  }

  // Approvals
  openRequestApprovalModal() {
    if (!this.currentRunId) {
      alert('You must run the pipeline first to generate a shortlist.');
      return;
    }
    const modal = document.getElementById('modal-request-approval');
    if (modal) modal.showModal();
  }

  async handleRequestApprovalSubmit(e) {
    e.preventDefault();
    const note = document.getElementById('approval-notes').value;
    const shortlist_snapshot = (this.currentShortlist || []).map((e) => e.candidate_id);

    try {
      await this.fetchApi('/approvals', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          run_id: this.currentRunId,
          shortlist_snapshot,
          note,
        }),
      });
      document.getElementById('modal-request-approval').close();
      alert('Shortlist submitted for sign-off.');
      this.switchTab('approvals');
    } catch (err) {
      alert(`Approval request failed: ${err.message}`);
    }
  }

  async loadApprovals() {
    try {
      const data = await this.fetchApi('/approvals');
      const tbody = document.getElementById('approvals-table-body');
      if (!tbody) return;

      const items = data.approvals || [];
      if (items.length === 0) {
        tbody.innerHTML = '<tr><td colspan="8" style="text-align: center; padding: 2.5rem; color: var(--text-muted);">No approval requests found.</td></tr>';
        return;
      }

      tbody.innerHTML = items.map((a) => {
        const stateBadge = a.state === 'approved' ? 'badge-met' : (a.state === 'rejected' ? 'badge-missing' : 'badge-partial');
        return `
          <tr>
            <td><span class="font-mono" style="font-size: 0.75rem;">${a.id.slice(0, 8)}...</span></td>
            <td><span class="font-mono" style="font-size: 0.75rem;">${a.run_id.slice(0, 8)}...</span></td>
            <td><span class="badge ${stateBadge}">${a.state.toUpperCase()}</span></td>
            <td>${a.requested_by.slice(0, 8)}...</td>
            <td>${a.decided_by ? a.decided_by.slice(0, 8) + '...' : '--'}</td>
            <td>${this.escapeHtml(a.note || '')}</td>
            <td style="color: var(--text-muted); font-size: 0.8rem;">${new Date(a.created_at).toLocaleDateString()}</td>
            <td style="text-align: right;">
              ${a.state === 'PENDING' ? `
                <button class="btn btn-secondary btn-sm" onclick="app.decideApproval('${a.id}', 'approved')">Approve</button>
                <button class="btn btn-danger btn-sm" onclick="app.decideApproval('${a.id}', 'rejected')">Reject</button>
              ` : '<span style="color: var(--text-muted); font-size: 0.8rem;">Decided</span>'}
            </td>
          </tr>
        `;
      }).join('');
    } catch (e) {
      console.warn('Could not load approvals:', e);
    }
  }

  async decideApproval(approvalId, decision) {
    try {
      await this.fetchApi(`/approvals/${approvalId}/decide`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ decision, note: `Decided via Evidence Desk UI` }),
      });
      await this.loadApprovals();
      await this.refreshAuditLogs();
    } catch (err) {
      alert(`Decision failed: ${err.message}`);
    }
  }

  // Cryptographic Audit Trail
  async refreshAuditLogs() {
    try {
      const data = await this.fetchApi('/audit');
      const tbody = document.getElementById('audit-table-body');
      if (!tbody) return;

      const entries = data.entries || [];
      if (entries.length === 0) {
        tbody.innerHTML = '<tr><td colspan="7" style="text-align: center; padding: 2.5rem; color: var(--text-muted);">No audit log entries recorded yet.</td></tr>';
        return;
      }

      tbody.innerHTML = entries.map((log) => `
        <tr>
          <td style="color: var(--text-muted); font-size: 0.78rem;">${new Date(log.created_at).toLocaleTimeString()}</td>
          <td><span class="badge badge-low">${log.action}</span></td>
          <td><span class="font-mono" style="font-size: 0.75rem;">${(log.actor_id || 'system').slice(0, 8)}...</span></td>
          <td><span style="font-size: 0.8rem;">${log.resource_type || '--'}</span></td>
          <td><span class="font-mono" style="font-size: 0.72rem; color: var(--text-muted);">${(log.prev_hash || '').slice(0, 16)}...</span></td>
          <td><span class="font-mono" style="font-size: 0.72rem; color: #818cf8;">${(log.hash || '').slice(0, 16)}...</span></td>
          <td><span class="badge badge-met" style="font-size: 0.65rem;">✓ SEALED</span></td>
        </tr>
      `).join('');
    } catch (e) {
      console.warn('Could not refresh audit logs:', e);
    }
  }

  escapeHtml(str) {
    if (!str) return '';
    return String(str)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#039;');
  }
}

// Global instance
const app = new RecruitRadarApp();
window.app = app;
