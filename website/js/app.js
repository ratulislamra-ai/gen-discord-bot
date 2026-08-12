/**
 * GEN ESPORTS WEB PLATFORM APPLICATION CONTROLLER
 * Independent Competitive Tournament Platform Logic.
 */

document.addEventListener('DOMContentLoaded', () => {
    App.init();
});

const TEAM_PLACEHOLDER_LOGO = `data:image/svg+xml;utf8,<svg xmlns="http://www.w3.org/2000/svg" width="64" height="64" viewBox="0 0 64 64"><rect width="64" height="64" rx="12" fill="%231a2035"/><text x="50%" y="55%" dominant-baseline="middle" text-anchor="middle" fill="%2300f0ff" font-family="sans-serif" font-size="28">🛡️</text></svg>`;
const PLAYER_PLACEHOLDER_AVATAR = `data:image/svg+xml;utf8,<svg xmlns="http://www.w3.org/2000/svg" width="64" height="64" viewBox="0 0 64 64"><circle cx="32" cy="32" r="32" fill="%231a2035"/><text x="50%" y="55%" dominant-baseline="middle" text-anchor="middle" fill="%23ff0055" font-family="sans-serif" font-size="28">👤</text></svg>`;

const App = {
    currentView: 'home',
    discordInviteUrl: '',
    autoRefreshInterval: null,
    adminApiKey: sessionStorage.getItem('gen_admin_api_key') || '',
    userDiscordId: localStorage.getItem('gen_user_discord_id') || '',
    adminTab: 'overview',
    activeTournamentSlug: '',

    async init() {
        this.bindEvents();
        try {
            await this.loadConfig();
        } catch (e) {
            console.warn('Config load notice:', e);
        }
        try {
            await this.renderView('home');
        } catch (e) {
            console.error('Failed initial view render:', e);
        }
        this.startAutoRefresh();
    },

    startAutoRefresh() {
        if (this.autoRefreshInterval) {
            clearInterval(this.autoRefreshInterval);
        }
        // Poll every 15 seconds for automatic Discord -> Database -> Website sync
        this.autoRefreshInterval = setInterval(async () => {
            if (['home', 'tournaments', 'teams', 'players', 'matches', 'brackets', 'leaderboards'].includes(this.currentView)) {
                await this.refreshActiveViewData();
            }
        }, 15000);
    },

    async refreshActiveViewData() {
        try {
            if (this.currentView === 'home') {
                const stats = await Api.getStats();
                const statVals = document.querySelectorAll('.stats-banner .stat-val');
                if (statVals.length >= 4 && stats) {
                    statVals[0].textContent = stats.total_tournaments ?? 0;
                    statVals[1].textContent = stats.approved_registrations ?? 0;
                    statVals[2].textContent = stats.completed_matches ?? 0;
                    statVals[3].textContent = stats.registered_players ?? 0;
                }
            } else if (this.currentView === 'teams') {
                await this.renderTeamsView();
            } else if (this.currentView === 'players') {
                await this.renderPlayersView();
            } else if (this.currentView === 'tournaments') {
                await this.renderTournamentsView();
            } else if (this.currentView === 'matches') {
                await this.renderMatchesView();
            }
        } catch (err) {
            console.warn('Silent background refresh notice:', err);
        }
    },

    async loadConfig() {
        try {
            const config = await Api.getConfig();
            this.discordInviteUrl = (config && config.discord_invite_url) || '';
        } catch (e) {
            console.warn('Failed to fetch config:', e);
            this.discordInviteUrl = '';
        }
    },

    openDiscordInvite() {
        if (this.discordInviteUrl && this.discordInviteUrl.startsWith('http')) {
            window.open(this.discordInviteUrl, '_blank', 'noopener');
        } else {
            this.showModal(`
                <div style="text-align: center; padding: 1.5rem;">
                    <div style="font-size: 3rem; margin-bottom: 1rem; color: var(--accent-gold);">💬</div>
                    <h3 style="font-family: var(--font-heading); font-size: 1.5rem; margin-bottom: 0.75rem;">Discord Server Invite</h3>
                    <p style="color: var(--text-secondary); line-height: 1.6; font-size: 0.95rem;">
                        The GEN Esports Discord server invite link is currently being updated. Please check back shortly.
                    </p>
                </div>
            `);
        }
    },

    bindEvents() {
        const mobileToggle = document.getElementById('mobile-toggle-btn');
        const navMenu = document.getElementById('nav-menu');
        if (mobileToggle && navMenu) {
            mobileToggle.addEventListener('click', () => {
                navMenu.classList.toggle('active');
            });
        }

        document.querySelectorAll('[data-view]').forEach(link => {
            link.addEventListener('click', (e) => {
                const view = link.getAttribute('data-view');
                if (view) {
                    e.preventDefault();
                    if (navMenu) navMenu.classList.remove('active');
                    this.renderView(view);
                }
            });
        });

        const modalClose = document.getElementById('modal-close-btn');
        const modal = document.getElementById('details-modal');
        if (modalClose) {
            modalClose.addEventListener('click', () => this.hideModal());
        }
        if (modal) {
            modal.addEventListener('click', (e) => {
                if (e.target === modal) this.hideModal();
            });
        }
    },

    showModal(htmlContent) {
        const modal = document.getElementById('details-modal');
        const modalBody = document.getElementById('modal-body');
        if (modal && modalBody) {
            modalBody.innerHTML = htmlContent;
            modal.classList.remove('hidden');
        }
    },

    hideModal() {
        const modal = document.getElementById('details-modal');
        if (modal) modal.classList.add('hidden');
    },

    async renderView(viewName) {
        this.currentView = viewName;
        const container = document.getElementById('app-content');
        if (!container) return;

        // Update active nav links
        document.querySelectorAll('.nav-link').forEach(link => {
            if (link.getAttribute('data-view') === viewName) {
                link.classList.add('active');
            } else {
                link.classList.remove('active');
            }
        });

        try {
            switch (viewName) {
                case 'home':
                    await this.renderHomeView();
                    break;
                case 'tournaments':
                    await this.renderTournamentsView();
                    break;
                case 'teams':
                    await this.renderTeamsView();
                    break;
                case 'players':
                    await this.renderPlayersView();
                    break;
                case 'matches':
                    await this.renderMatchesView();
                    break;
                case 'brackets':
                    await this.renderBracketsView();
                    break;
                case 'leaderboards':
                    await this.renderLeaderboardsView();
                    break;
                case 'dashboard':
                    await this.renderDashboardView();
                    break;
                case 'admin':
                    await this.renderAdminView();
                    break;
                default:
                    await this.renderHomeView();
            }
        } catch (err) {
            console.error(`Error rendering view '${viewName}':`, err);
            container.innerHTML = `
                <div class="glass-panel" style="padding: 4rem 2rem; text-align: center; max-width: 600px; margin: 3rem auto;">
                    <div style="font-size: 3.5rem; margin-bottom: 1rem;">⚠️</div>
                    <h2 style="font-family: var(--font-heading); font-size: 1.8rem; color: var(--accent-gold);">UNABLE TO LOAD SECTION</h2>
                    <p style="color: var(--text-secondary); margin: 0.75rem 0 1.5rem;">
                        Failed to render the '${viewName}' section. Please try again or refresh.
                    </p>
                    <button onclick="App.renderView('${viewName}')" class="btn btn-discord">🔄 Retry</button>
                </div>
            `;
        }

        window.scrollTo({ top: 0, behavior: 'smooth' });
    },

    // RENDER HOME VIEW
    async renderHomeView() {
        const container = document.getElementById('app-content');
        if (!container) return;

        let stats = { total_tournaments: 0, approved_registrations: 0, completed_matches: 0, registered_players: 0 };
        let tournaments = [];

        try {
            const rawStats = await Api.getStats();
            if (rawStats && typeof rawStats === 'object') {
                stats = { ...stats, ...rawStats };
            }
        } catch (e) {
            console.warn('Stats fetch notice in Home:', e);
        }

        try {
            const rawTournaments = await Api.getTournaments();
            if (Array.isArray(rawTournaments)) {
                tournaments = rawTournaments;
            }
        } catch (e) {
            console.warn('Tournaments fetch notice in Home:', e);
        }

        const featuredTournaments = tournaments.slice(0, 3);

        container.innerHTML = `
            <section class="hero-section">
                <div class="hero-container">
                    <div class="hero-content">
                        <div class="hero-badge">
                            <span>🔥 OFFICIAL GEN ESPORTS PLATFORM</span>
                        </div>
                        <h1 class="hero-title">
                            COMPETE IN THE <span class="gradient-text">NEXT GENERATION</span> OF ESPORTS
                        </h1>
                        <p class="hero-subtitle">
                            Register your competitive roster, track live tournament brackets, match scores, and automated leaderboards in real-time.
                        </p>
                        <div class="hero-cta-group">
                            <button onclick="App.openDiscordInvite()" class="btn btn-discord btn-lg">
                                💬 Join Discord & Register
                            </button>
                            <a href="#tournaments" onclick="App.renderView('tournaments')" class="btn btn-secondary btn-lg">
                                🏆 Browse Tournaments
                            </a>
                        </div>
                    </div>
                </div>
            </section>

            <section class="stats-banner glass-panel">
                <div class="stat-box">
                    <div class="stat-val">${stats.total_tournaments ?? 0}</div>
                    <div class="stat-lbl">Active Tournaments</div>
                </div>
                <div class="stat-box">
                    <div class="stat-val">${stats.approved_registrations ?? 0}</div>
                    <div class="stat-lbl">Approved Teams</div>
                </div>
                <div class="stat-box">
                    <div class="stat-val">${stats.completed_matches ?? 0}</div>
                    <div class="stat-lbl">Completed Matches</div>
                </div>
                <div class="stat-box">
                    <div class="stat-val">${stats.registered_players ?? 0}</div>
                    <div class="stat-lbl">Registered Players</div>
                </div>
            </section>

            <section style="margin-top: 4rem;">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 2rem;">
                    <h2 style="font-family: var(--font-heading); font-size: 2rem;">Featured <span style="color: var(--accent-cyan);">Tournaments</span></h2>
                    <a href="#tournaments" onclick="App.renderView('tournaments')" style="color: var(--accent-cyan); font-weight: 600; text-decoration: none;">View All &rarr;</a>
                </div>
                <div class="tournaments-grid">
                    ${featuredTournaments.length === 0 ? `
                        <div class="glass-panel" style="padding: 3rem; text-align: center; grid-column: 1 / -1;">
                            <div style="font-size: 2.5rem; margin-bottom: 0.75rem;">🏆</div>
                            <h3>No Active Tournaments</h3>
                            <p style="color: var(--text-secondary); margin-top: 0.25rem;">Check back soon for upcoming GEN Esports events.</p>
                        </div>
                    ` : featuredTournaments.map(t => this.buildTournamentCardHtml(t)).join('')}
                </div>
            </section>
        `;
    },

    // RENDER TOURNAMENTS VIEW
    async renderTournamentsView() {
        const container = document.getElementById('app-content');
        const tournaments = await Api.getTournaments();

        container.innerHTML = `
            <div style="margin-bottom: 3rem;">
                <div class="hero-badge">🏆 COMPETITIVE TOURNAMENTS</div>
                <h1 style="font-family: var(--font-heading); font-size: 2.8rem; margin-top: 0.5rem;">
                    ACTIVE & UPCOMING <span class="gradient-text">EVENTS</span>
                </h1>
                <p style="color: var(--text-secondary); max-width: 650px; margin-top: 0.5rem;">
                    Browse active esports championships. All team registrations are submitted directly via Discord and instantly reflected here upon admin approval.
                </p>
            </div>

            <div class="tournaments-grid">
                ${tournaments.length === 0 ? `
                    <div class="glass-panel" style="padding: 4rem; text-align: center; grid-column: 1 / -1;">
                        <div style="font-size: 3rem; margin-bottom: 1rem;">🏆</div>
                        <h3>No Active Tournaments</h3>
                        <p style="color: var(--text-secondary);">Check back soon for upcoming GEN Esports events.</p>
                    </div>
                ` : tournaments.map(t => this.buildTournamentCardHtml(t)).join('')}
            </div>
        `;
    },

    handleImgError(img, type = 'team') {
        if (img) {
            img.onerror = null;
            img.src = type === 'team' ? TEAM_PLACEHOLDER_LOGO : PLAYER_PLACEHOLDER_AVATAR;
        }
    },

    escapeHtml(str) {
        if (!str) return '';
        return String(str)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#039;');
    },

    buildTournamentCardHtml(t) {
        const approved = t.current_approved_team_count || 0;
        const maxTeams = t.max_teams || 16;
        const isFull = approved >= maxTeams || t.registration_status === 'FULL';
        const progressPct = Math.min(100, Math.round((approved / maxTeams) * 100));

        let prizePool = t.prize_info || '৳500 BDT';
        if (prizePool.includes('$500 USD')) {
            prizePool = prizePool.replace('$500 USD', '৳500 BDT');
        }

        let statusBadge = `<span class="badge badge-open">🟢 REGISTRATION OPEN</span>`;
        if (isFull) {
            statusBadge = `<span class="badge badge-closed">🛑 REGISTRATION FULL</span>`;
        } else if (t.registration_status === 'CLOSED' || t.status === 'REGISTRATION_CLOSED') {
            statusBadge = `<span class="badge badge-closed">🔴 REGISTRATION CLOSED</span>`;
        } else if (t.status === 'ONGOING') {
            statusBadge = `<span class="badge badge-ongoing">🔵 ONGOING</span>`;
        } else if (t.status === 'COMPLETED') {
            statusBadge = `<span class="badge badge-draft">🏆 COMPLETED</span>`;
        }

        return `
            <div class="tournament-card glass-panel">
                <div class="tournament-card-header">
                    <div>
                        <div style="font-size: 0.8rem; color: var(--accent-cyan); font-weight: 700; text-transform: uppercase;">${this.escapeHtml(t.game_type || 'ESPORTS')}</div>
                        <h3 style="font-family: var(--font-heading); font-size: 1.4rem; margin-top: 0.2rem;">${this.escapeHtml(t.title)}</h3>
                    </div>
                    ${statusBadge}
                </div>
                <p style="color: var(--text-secondary); font-size: 0.9rem; margin-bottom: 1.5rem; line-height: 1.5;">
                    ${this.escapeHtml(t.description || 'GEN Esports Official Championship Tournament Series.')}
                </p>

                <div style="background: rgba(255,255,255,0.03); border-radius: var(--radius-sm); padding: 1rem; margin-bottom: 1.5rem; display: grid; grid-template-columns: 1fr 1fr; gap: 0.75rem; font-size: 0.85rem;">
                    <div>💰 <strong>Prize Pool:</strong><br><span style="color: var(--accent-gold); font-weight: 700;">${this.escapeHtml(prizePool)}</span></div>
                    <div>⚔️ <strong>Format:</strong><br><span style="color: var(--text-primary); font-weight: 600;">${this.escapeHtml(t.format || 'Single Elimination')}</span></div>
                </div>

                <div style="margin-bottom: 1.5rem;">
                    <div style="display: flex; justify-content: space-between; font-size: 0.85rem; font-weight: 600; margin-bottom: 0.4rem;">
                        <span>Approved Teams</span>
                        <span style="color: ${isFull ? 'var(--accent-red)' : 'var(--accent-cyan)'};">${approved} / ${maxTeams} Teams ${isFull ? '(FULL)' : ''}</span>
                    </div>
                    <div style="width: 100%; height: 8px; background: rgba(255,255,255,0.1); border-radius: 4px; overflow: hidden;">
                        <div style="width: ${progressPct}%; height: 100%; background: ${isFull ? 'var(--accent-red)' : 'linear-gradient(90deg, var(--accent-cyan), var(--accent-green))'}; border-radius: 4px;"></div>
                    </div>
                </div>

                <div style="display: flex; gap: 0.75rem;">
                    <button onclick="App.showTournamentDetailsModal('${this.escapeHtml(t.slug)}')" class="btn btn-secondary" style="flex: 1; font-size: 0.85rem;">
                        ℹ️ Details & Teams
                    </button>
                    ${isFull ? `
                        <button disabled class="btn btn-secondary" style="flex: 1; font-size: 0.85rem; opacity: 0.6; cursor: not-allowed;">
                            🛑 Registration Full
                        </button>
                    ` : `
                        <button onclick="App.openDiscordInvite()" class="btn btn-discord" style="flex: 1; font-size: 0.85rem;">
                            💬 Register in Discord
                        </button>
                    `}
                </div>
            </div>
        `;
    },

    async showTournamentDetailsModal(slug) {
        const t = await Api.getTournamentDetails(slug);
        const approvedTeams = await Api.getApprovedTeams(slug);
        if (!t) return;

        const approved = t.current_approved_team_count || approvedTeams.length || 0;
        const maxTeams = t.max_teams || 16;
        const isFull = approved >= maxTeams || t.registration_status === 'FULL';

        let prizePool = t.prize_info || '৳500 BDT';
        if (prizePool.includes('$500 USD')) {
            prizePool = prizePool.replace('$500 USD', '৳500 BDT');
        }

        const teamsListHtml = approvedTeams.length === 0 ? `
            <div style="text-align: center; color: var(--text-muted); padding: 2rem; background: rgba(0,0,0,0.2); border-radius: var(--radius-md); border: 1px dashed var(--border-card);">
                🛡️ No approved teams registered yet for this tournament.
            </div>
        ` : `
            <div style="display: flex; flex-direction: column; gap: 0.75rem; max-height: 280px; overflow-y: auto; padding-right: 0.25rem;">
                ${approvedTeams.map(tm => {
                    const logoUrl = tm.team_logo_url ? (tm.team_logo_url.startsWith('http') ? tm.team_logo_url : '/' + tm.team_logo_url) : TEAM_PLACEHOLDER_LOGO;
                    const publicId = tm.public_id || tm.registration_id || 'GEN-TEAM-XXXX';
                    return `
                        <div style="background: rgba(255,255,255,0.03); border: 1px solid var(--border-card); border-radius: var(--radius-md); padding: 0.85rem 1.1rem; display: flex; align-items: center; justify-content: space-between; gap: 1rem;">
                            <div style="display: flex; align-items: center; gap: 1rem;">
                                <img src="${logoUrl}"
                                     style="width: 44px; height: 44px; border-radius: 10px; object-fit: cover; background: rgba(0,0,0,0.3); border: 1px solid rgba(255,255,255,0.1);"
                                     onerror="App.handleImgError(this, 'team')">
                                <div>
                                    <div style="font-weight: 800; font-size: 1.02rem; color: #fff; display: flex; align-items: center; gap: 0.4rem;">
                                        ${this.escapeHtml(tm.team_name)}
                                        <span style="color: var(--accent-green); font-size: 0.85rem;" title="Verified Team">✓</span>
                                    </div>
                                    <div style="font-size: 0.8rem; color: var(--accent-cyan); font-weight: 600; margin-top: 0.15rem;">
                                        Team ID: <code>${this.escapeHtml(publicId)}</code>
                                    </div>
                                    <div style="font-size: 0.78rem; color: var(--text-muted); margin-top: 0.15rem;">
                                        👑 Captain: <strong>${this.escapeHtml(tm.captain_name || 'Team Captain')}</strong>
                                    </div>
                                </div>
                            </div>
                            <div style="text-align: right;">
                                <span class="badge badge-open" style="font-size: 0.75rem; padding: 0.25rem 0.6rem;">VERIFIED ✓</span>
                            </div>
                        </div>
                    `;
                }).join('')}
            </div>
        `;

        this.showModal(`
            <div style="max-width: 650px; margin: 0 auto;">
                <div style="font-size: 0.8rem; color: var(--accent-cyan); font-weight: 800; text-transform: uppercase; letter-spacing: 1px;">${this.escapeHtml(t.game_type || 'ESPORTS')}</div>
                <h2 style="font-family: var(--font-heading); font-size: 2.2rem; margin-top: 0.25rem; color: #fff;">${this.escapeHtml(t.title)}</h2>
                <p style="color: var(--text-secondary); margin-top: 0.5rem; line-height: 1.6; font-size: 0.95rem;">${this.escapeHtml(t.description || '')}</p>

                <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(130px, 1fr)); gap: 1rem; margin: 1.5rem 0; background: rgba(0,0,0,0.4); border: 1px solid var(--border-card); padding: 1.25rem; border-radius: var(--radius-md);">
                    <div><span style="color: var(--text-muted); font-size: 0.78rem; font-weight: 700;">PRIZE POOL</span><br><strong style="color: var(--accent-gold); font-size: 1.1rem;">${this.escapeHtml(prizePool)}</strong></div>
                    <div><span style="color: var(--text-muted); font-size: 0.78rem; font-weight: 700;">FORMAT</span><br><strong style="font-size: 1rem;">${this.escapeHtml(t.format || 'Single Elimination')}</strong></div>
                    <div><span style="color: var(--text-muted); font-size: 0.78rem; font-weight: 700;">MAX TEAMS</span><br><strong style="font-size: 1rem;">${maxTeams} Teams</strong></div>
                    <div><span style="color: var(--text-muted); font-size: 0.78rem; font-weight: 700;">APPROVED TEAMS</span><br><strong style="color: ${isFull ? 'var(--accent-red)' : 'var(--accent-cyan)'}; font-size: 1rem;">${approved} / ${maxTeams} ${isFull ? '(FULL)' : ''}</strong></div>
                </div>

                <h4 style="font-family: var(--font-heading); font-size: 1.15rem; margin-bottom: 0.75rem; color: #fff;">📜 Tournament Rules</h4>
                <div style="background: rgba(0,0,0,0.3); border: 1px solid var(--border-card); padding: 1rem; border-radius: var(--radius-sm); font-size: 0.9rem; max-height: 130px; overflow-y: auto; color: var(--text-secondary); margin-bottom: 1.5rem; line-height: 1.6;">
                    ${this.escapeHtml(t.rules_text || 'Official GEN Esports Rules apply.')}
                </div>

                <h4 style="font-family: var(--font-heading); font-size: 1.15rem; margin-bottom: 0.85rem; color: #fff; display: flex; align-items: center; justify-content: space-between;">
                    <span>🛡️ Registered Teams (${approvedTeams.length})</span>
                    <span style="font-size: 0.8rem; color: var(--text-muted); font-weight: 500;">Approved Roster Profiles</span>
                </h4>
                ${teamsListHtml}

                <div style="margin-top: 2rem; display: flex; justify-content: flex-end; gap: 1rem;">
                    ${isFull ? `
                        <button disabled class="btn btn-secondary" style="width: 100%; opacity: 0.6; cursor: not-allowed; padding: 0.85rem;">
                            🛑 Registration Full
                        </button>
                    ` : `
                        <button onclick="App.openDiscordInvite()" class="btn btn-discord" style="width: 100%; padding: 0.85rem; font-size: 1rem;">
                            💬 Register Team on Discord
                        </button>
                    `}
                </div>
            </div>
        `);
    },

    // RENDER TEAMS VIEW
    async renderTeamsView() {
        const container = document.getElementById('app-content');
        const teams = await Api.getTeams();

        container.innerHTML = `
            <div style="margin-bottom: 3rem;">
                <div class="hero-badge">🛡️ ESPORTS TEAMS</div>
                <h1 style="font-family: var(--font-heading); font-size: 2.8rem; margin-top: 0.5rem;">
                    REGISTERED <span class="gradient-text">TEAMS & DIRECTORY</span>
                </h1>
                <p style="color: var(--text-secondary); max-width: 650px; margin-top: 0.5rem;">
                    Explore official esports team profiles and verified rosters.
                </p>
            </div>

            <div class="teams-grid">
                ${teams.length === 0 ? `
                    <div class="glass-panel" style="padding: 4rem; text-align: center; grid-column: 1 / -1;">
                        <div style="font-size: 3rem; margin-bottom: 1rem;">🛡️</div>
                        <h3>No Teams Listed</h3>
                        <p style="color: var(--text-secondary); margin-top: 0.5rem;">Team profiles will automatically post here upon registration.</p>
                    </div>
                ` : teams.map(tm => {
                    const isVerified = tm.verification_status === 'VERIFIED';
                    const logoSrc = tm.logo_url ? (tm.logo_url.startsWith('http') ? tm.logo_url : `/${tm.logo_url}`) : TEAM_PLACEHOLDER_LOGO;
                    return `
                        <div class="team-card glass-panel" onclick="App.showTeamProfileModal('${tm.slug}')">
                            <div class="team-card-header">
                                <img src="${logoSrc}" alt="${tm.name}" class="team-logo-lg" onerror="this.src=TEAM_PLACEHOLDER_LOGO">
                                <div>
                                    <div class="team-info-name">${tm.name} ${isVerified ? '<span style="color: var(--accent-green);">✅</span>' : ''}</div>
                                    <div class="team-info-captain">🏷️ ID: ${tm.public_id}</div>
                                </div>
                            </div>
                            <div style="font-size: 0.85rem; color: var(--text-muted); margin-bottom: 0.5rem;">
                                🎮 Game: <strong>${tm.game || 'VALORANT'}</strong> | Region: <strong>${tm.region || 'South Asia'}</strong>
                            </div>
                            <button class="btn btn-secondary" style="width: 100%; margin-top: 0.75rem; font-size: 0.85rem;">
                                👁️ View Team Roster & History
                            </button>
                        </div>
                    `;
                }).join('')}
            </div>
        `;
    },

    async showTeamProfileModal(slug) {
        const team = await Api.getTeamProfile(slug);
        if (!team) return;

        const isVerified = team.verification_status === 'VERIFIED';
        const logoSrc = team.logo_url ? (team.logo_url.startsWith('http') ? team.logo_url : `/${team.logo_url}`) : TEAM_PLACEHOLDER_LOGO;

        this.showModal(`
            <div style="text-align: center; margin-bottom: 1.5rem;">
                <img src="${logoSrc}" style="width: 80px; height: 80px; border-radius: 12px; object-fit: cover; margin-bottom: 0.75rem;" onerror="this.src=TEAM_PLACEHOLDER_LOGO">
                <h2 style="font-family: var(--font-heading); font-size: 1.8rem;">${team.name} ${isVerified ? '<span style="color: var(--accent-green);">✅</span>' : ''}</h2>
                <div style="font-size: 0.9rem; color: var(--accent-cyan); font-weight: 600;">🏷️ Public ID: ${team.public_id}</div>
                <div style="font-size: 0.85rem; color: var(--text-muted); margin-top: 0.25rem;">🎮 ${team.game || 'VALORANT'} • 🌍 ${team.region || 'South Asia'}</div>
            </div>

            <h4 style="font-family: var(--font-heading); font-size: 1.1rem; margin-bottom: 0.75rem;">👥 Active Roster (${(team.roster || []).length})</h4>
            <div style="display: flex; flex-direction: column; gap: 0.5rem; background: rgba(0,0,0,0.3); padding: 1rem; border-radius: var(--radius-md); border: 1px solid var(--border-card); margin-bottom: 1.5rem;">
                ${(team.roster || []).length === 0 ? '<div style="color: var(--text-muted); text-align: center;">No roster members found.</div>' : (team.roster || []).map(p => `
                    <div style="display: flex; justify-content: space-between; align-items: center; padding: 0.5rem; border-bottom: 1px solid rgba(255,255,255,0.05);">
                        <span style="font-weight: 700; color: var(--accent-cyan); font-size: 0.85rem;">${p.role}</span>
                        <span style="font-weight: 600;">${p.display_name || p.username} (${p.public_id})</span>
                    </div>
                `).join('')}
            </div>

            <h4 style="font-family: var(--font-heading); font-size: 1.1rem; margin-bottom: 0.75rem;">📜 Tournament History</h4>
            <div style="background: rgba(0,0,0,0.3); padding: 1rem; border-radius: var(--radius-md); border: 1px solid var(--border-card); font-size: 0.9rem;">
                ${(team.tournament_history || []).length === 0 ? '<div style="color: var(--text-muted); text-align: center;">No tournament history recorded yet.</div>' : (team.tournament_history || []).map(h => `
                    <div style="display: flex; justify-content: space-between; padding: 0.4rem 0;">
                        <span>🏆 <strong>${h.tournament_name}</strong></span>
                        <span class="badge badge-open">${h.status}</span>
                    </div>
                `).join('')}
            </div>
        `);
    },

    // RENDER PLAYERS VIEW
    async renderPlayersView() {
        const container = document.getElementById('app-content');
        const players = await Api.getPlayers();

        container.innerHTML = `
            <div style="margin-bottom: 3rem;">
                <div class="hero-badge">👤 PLAYER DIRECTORY</div>
                <h1 style="font-family: var(--font-heading); font-size: 2.8rem; margin-top: 0.5rem;">
                    VERIFIED <span class="gradient-text">PLAYERS</span>
                </h1>
                <p style="color: var(--text-secondary); max-width: 650px; margin-top: 0.5rem;">
                    Browse active competitor profiles, public IDs, and game statistics.
                </p>
            </div>

            <div style="display: grid; grid-template-columns: repeat(auto-fill, minmax(260px, 1fr)); gap: 1.5rem;">
                ${players.length === 0 ? `
                    <div class="glass-panel" style="padding: 4rem; text-align: center; grid-column: 1 / -1;">
                        <div style="font-size: 3rem; margin-bottom: 1rem;">👤</div>
                        <h3>No Players Registered</h3>
                        <p style="color: var(--text-secondary); margin-top: 0.5rem;">Player profiles will automatically post here upon registration.</p>
                    </div>
                ` : players.map(p => {
                    const isVerified = p.verification_status === 'VERIFIED';
                    const avatarSrc = p.avatar_url || PLAYER_PLACEHOLDER_AVATAR;
                    return `
                        <div class="glass-panel" style="padding: 1.25rem; text-align: center; cursor: pointer;" onclick="App.showPlayerProfileModal('${p.public_id}')">
                            <img src="${avatarSrc}" style="width: 64px; height: 64px; border-radius: 50%; object-fit: cover; margin-bottom: 0.75rem;" onerror="this.src=PLAYER_PLACEHOLDER_AVATAR">
                            <h3 style="font-family: var(--font-heading); font-size: 1.2rem;">${p.display_name} ${isVerified ? '<span style="color: var(--accent-green);">✅</span>' : ''}</h3>
                            <div style="font-size: 0.8rem; color: var(--accent-cyan); font-weight: 700; margin-top: 0.2rem;">🏷️ ${p.public_id}</div>
                            <div style="font-size: 0.85rem; color: var(--text-muted); margin-top: 0.5rem;">🎮 ${p.primary_game || 'VALORANT'}</div>
                        </div>
                    `;
                }).join('')}
            </div>
        `;
    },

    async showPlayerProfileModal(slug) {
        const player = await Api.getPlayerProfile(slug);
        if (!player) return;

        const isVerified = player.verification_status === 'VERIFIED';
        const avatarSrc = player.avatar_url || PLAYER_PLACEHOLDER_AVATAR;
        const stats = player.stats || {};

        this.showModal(`
            <div style="text-align: center; margin-bottom: 1.5rem;">
                <img src="${avatarSrc}" style="width: 80px; height: 80px; border-radius: 50%; object-fit: cover; margin-bottom: 0.75rem;" onerror="this.src=PLAYER_PLACEHOLDER_AVATAR">
                <h2 style="font-family: var(--font-heading); font-size: 1.8rem;">${player.display_name} ${isVerified ? '<span style="color: var(--accent-green);">✅</span>' : ''}</h2>
                <div style="font-size: 0.9rem; color: var(--accent-cyan); font-weight: 600;">🏷️ Public ID: ${player.public_id}</div>
                <div style="font-size: 0.85rem; color: var(--text-muted); margin-top: 0.25rem;">🎮 Primary Game: ${player.primary_game || 'VALORANT'}</div>
            </div>

            <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 1rem; margin-bottom: 1.5rem; background: rgba(255,255,255,0.03); padding: 1rem; border-radius: var(--radius-md); text-align: center;">
                <div><span style="color: var(--text-muted); font-size: 0.8rem;">MATCHES</span><br><strong style="font-size: 1.2rem;">${stats.matches_played ?? 0}</strong></div>
                <div><span style="color: var(--text-muted); font-size: 0.8rem;">WINS</span><br><strong style="font-size: 1.2rem; color: var(--accent-green);">${stats.wins ?? 0}</strong></div>
                <div><span style="color: var(--text-muted); font-size: 0.8rem;">WIN RATE</span><br><strong style="font-size: 1.2rem; color: var(--accent-gold);">${stats.win_rate ?? 0}%</strong></div>
            </div>

            <h4 style="font-family: var(--font-heading); font-size: 1.1rem; margin-bottom: 0.75rem;">🛡️ Active Teams</h4>
            <div style="background: rgba(0,0,0,0.3); padding: 0.75rem; border-radius: var(--radius-md); border: 1px solid var(--border-card); margin-bottom: 1.5rem;">
                ${(player.teams || []).length === 0 ? '<div style="color: var(--text-muted); text-align: center;">No active team membership.</div>' : (player.teams || []).map(t => `
                    <div style="display: flex; justify-content: space-between; padding: 0.4rem 0;">
                        <span>🛡️ <strong>${t.team_name}</strong></span>
                        <span style="color: var(--accent-cyan); font-weight: 700; font-size: 0.85rem;">${t.role}</span>
                    </div>
                `).join('')}
            </div>

            <h4 style="font-family: var(--font-heading); font-size: 1.1rem; margin-bottom: 0.75rem;">🏅 Achievements</h4>
            <div style="background: rgba(0,0,0,0.3); padding: 0.75rem; border-radius: var(--radius-md); border: 1px solid var(--border-card);">
                ${(player.achievements || []).length === 0 ? '<div style="color: var(--text-muted); text-align: center;">No achievements recorded yet.</div>' : (player.achievements || []).map(a => `
                    <div style="display: flex; align-items: center; gap: 0.75rem; padding: 0.4rem 0;">
                        <span style="font-size: 1.5rem;">${a.badge_icon || '🏆'}</span>
                        <div><strong>${a.title}</strong><br><span style="font-size: 0.8rem; color: var(--text-muted);">${a.description || ''}</span></div>
                    </div>
                `).join('')}
            </div>
        `);
    },

    // RENDER MATCHES VIEW
    async renderMatchesView() {
        const container = document.getElementById('app-content');
        const matches = await Api.getMatches();

        container.innerHTML = `
            <div style="margin-bottom: 3rem;">
                <div class="hero-badge">⚔️ TOURNAMENT SCHEDULE</div>
                <h1 style="font-family: var(--font-heading); font-size: 2.8rem; margin-top: 0.5rem;">
                    MATCH <span class="gradient-text">CENTER</span>
                </h1>
                <p style="color: var(--text-secondary); max-width: 650px; margin-top: 0.5rem;">
                    Live, upcoming, and completed match results recorded directly by tournament administrators.
                </p>
            </div>

            <div style="display: grid; grid-template-columns: repeat(auto-fill, minmax(320px, 1fr)); gap: 1.5rem;">
                ${matches.length === 0 ? `
                    <div class="glass-panel" style="padding: 4rem; text-align: center; grid-column: 1 / -1;">
                        <div style="font-size: 3rem; margin-bottom: 1rem;">⚔️</div>
                        <h3>No Matches Scheduled</h3>
                        <p style="color: var(--text-secondary);">Matches will appear here once brackets are generated by administrators.</p>
                    </div>
                ` : matches.map(m => `
                    <div class="glass-panel" style="padding: 1.25rem;">
                        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 1rem; font-size: 0.8rem; color: var(--text-muted);">
                            <span>🏆 ${m.tournament_name || 'GEN Tournament'}</span>
                            <span class="badge ${m.status === 'COMPLETED' ? 'badge-closed' : (m.status === 'LIVE' ? 'badge-open' : 'badge-draft')}">${m.status}</span>
                        </div>
                        <div style="font-size: 0.85rem; font-weight: 700; color: var(--accent-cyan); margin-bottom: 0.75rem;">${m.stage_name || 'Stage Match'}</div>

                        <div style="display: flex; flex-direction: column; gap: 0.5rem; background: rgba(0,0,0,0.3); padding: 0.75rem; border-radius: var(--radius-sm);">
                            <div style="display: flex; justify-content: space-between; align-items: center; font-weight: 600;">
                                <span>🛡️ ${m.team1_name || 'TBD'}</span>
                                <span style="font-family: var(--font-heading); font-size: 1.2rem; color: var(--accent-gold);">${m.team1_score ?? 0}</span>
                            </div>
                            <div style="display: flex; justify-content: space-between; align-items: center; font-weight: 600;">
                                <span>🛡️ ${m.team2_name || 'TBD'}</span>
                                <span style="font-family: var(--font-heading); font-size: 1.2rem; color: var(--accent-gold);">${m.team2_score ?? 0}</span>
                            </div>
                        </div>
                    </div>
                `).join('')}
            </div>
        `;
    },

    // RENDER BRACKETS VIEW
    async renderBracketsView() {
        const container = document.getElementById('app-content');
        const tournaments = await Api.getTournaments();

        if (tournaments.length > 0 && !this.activeTournamentSlug) {
            this.activeTournamentSlug = tournaments[0].slug;
        }

        const data = this.activeTournamentSlug ? await Api.getTournamentBracket(this.activeTournamentSlug) : { tournament: null, has_bracket: false, rounds: [], champion: null };
        const t_info = data.tournament || {};
        const rounds = data.rounds || [];
        const champion = data.champion;

        container.innerHTML = `
            <div style="margin-bottom: 2rem;">
                <div class="hero-badge">🏆 DYNAMIC BRACKET VIEWER</div>
                <h1 style="font-family: var(--font-heading); font-size: 2.8rem; margin-top: 0.5rem;">
                    TOURNAMENT <span class="gradient-text">BRACKET</span>
                </h1>
                <p style="color: var(--text-secondary); max-width: 650px; margin-top: 0.5rem;">
                    Inspect live tournament brackets, match progression, and grand champions in real-time.
                </p>
            </div>

            <div style="margin-bottom: 2rem; display: flex; gap: 1.5rem; align-items: center; justify-content: space-between; flex-wrap: wrap;" class="glass-panel">
                <div style="display: flex; gap: 1rem; align-items: center; flex-wrap: wrap; padding: 1rem 1.5rem;">
                    <label style="font-weight: 700; color: var(--accent-cyan);">Select Tournament:</label>
                    <select onchange="App.changeBracketTournament(this.value)" class="form-select" style="max-width: 340px;">
                        ${tournaments.map(t => `<option value="${t.slug}" ${t.slug === this.activeTournamentSlug ? 'selected' : ''}>${t.title}</option>`).join('')}
                    </select>
                </div>
                ${t_info.title ? `
                    <div style="display: flex; gap: 1rem; font-size: 0.85rem; font-weight: 600; padding: 1rem 1.5rem;">
                        <span class="badge badge-open">Status: ${t_info.status || 'ACTIVE'}</span>
                        <span class="badge badge-draft">Format: ${t_info.format || 'Single Elimination'}</span>
                        <span class="badge badge-closed">Registered Teams: ${t_info.registered_teams_count ?? 0}</span>
                    </div>
                ` : ''}
            </div>

            ${champion ? `
                <div class="champion-banner">
                    <div style="font-size: 2.5rem;">🏆</div>
                    <div class="champion-title">GRAND CHAMPION</div>
                    <div style="font-size: 1.8rem; font-weight: 800; color: #fff; margin-top: 0.5rem;">${champion.name}</div>
                    <div style="color: var(--accent-gold); font-weight: 700; letter-spacing: 1px; margin-top: 0.25rem;">TOURNAMENT WINNER</div>
                </div>
            ` : ''}

            <div class="bracket-wrapper glass-panel">
                ${!data.has_bracket ? `
                    <div style="padding: 4rem 2rem; text-align: center; width: 100%;">
                        <div style="font-size: 3.5rem; margin-bottom: 1rem;">🏆</div>
                        <h2 style="font-family: var(--font-heading); font-size: 1.8rem; color: var(--accent-cyan);">BRACKET NOT GENERATED YET</h2>
                        <p style="color: var(--text-secondary); max-width: 550px; margin: 0.75rem auto 1.5rem;">
                            Tournament registration is currently underway. The bracket will appear here automatically once tournament seeding is completed by administrators.
                        </p>
                        <div style="display: inline-flex; gap: 1rem; background: rgba(0,0,0,0.3); padding: 0.75rem 1.5rem; border-radius: var(--radius-md); font-weight: 600; font-size: 0.9rem;">
                            <span>Approved Teams: <strong style="color: var(--accent-gold);">${t_info.registered_teams_count ?? 0}</strong></span>
                            <span>•</span>
                            <span>Seeding Status: <strong style="color: var(--accent-cyan);">PENDING</strong></span>
                        </div>
                    </div>
                ` : `
                    <div class="bracket-container">
                        ${rounds.map((r, rIdx) => `
                            <div class="bracket-round">
                                <div class="bracket-round-title">${r.round_name || 'Round ' + r.round_number}</div>
                                <div style="display: flex; flex-direction: column; gap: 2rem; height: 100%; justify-content: space-around;">
                                    ${r.matches.map(m => `
                                        <div class="bracket-match-card">
                                            <div class="bracket-match-header">
                                                <span>#${m.public_match_id || m.match_id}</span>
                                                <span class="badge ${m.status === 'COMPLETED' ? 'badge-final' : (m.status === 'IN_PROGRESS' || m.status === 'READY' ? 'badge-live' : 'badge-upcoming')}">
                                                    ${m.status === 'COMPLETED' ? 'FINAL' : (m.status === 'IN_PROGRESS' || m.status === 'READY' ? '🔴 LIVE' : 'UPCOMING')}
                                                </span>
                                            </div>
                                            <div class="bracket-team-row ${m.winner_id && m.winner_id === m.team1_id ? 'winner' : ''}">
                                                <div class="bracket-team-info">
                                                    <span>🛡️</span>
                                                    <span>${m.team1_name || 'TBD'}</span>
                                                </div>
                                                <span class="bracket-score">${m.team1_score ?? '-'}</span>
                                            </div>
                                            <div class="bracket-team-row ${m.winner_id && m.winner_id === m.team2_id ? 'winner' : ''}">
                                                <div class="bracket-team-info">
                                                    <span>🛡️</span>
                                                    <span>${m.team2_name || 'TBD'}</span>
                                                </div>
                                                <span class="bracket-score">${m.team2_score ?? '-'}</span>
                                            </div>
                                            ${rIdx < rounds.length - 1 ? '<div class="bracket-connector-line"></div>' : ''}
                                        </div>
                                    `).join('')}
                                </div>
                            </div>
                        `).join('')}
                    </div>
                `}
            </div>
        `;
    },

    async changeBracketTournament(slug) {
        this.activeTournamentSlug = slug;
        await this.renderBracketsView();
    },

    // RENDER LEADERBOARDS VIEW
    async renderLeaderboardsView() {
        const container = document.getElementById('app-content');
        const tournaments = await Api.getTournaments();

        if (tournaments.length > 0 && !this.activeTournamentSlug) {
            this.activeTournamentSlug = tournaments[0].slug;
        }

        const standings = this.activeTournamentSlug ? await Api.getTournamentStandings(this.activeTournamentSlug) : [];

        container.innerHTML = `
            <div style="margin-bottom: 2rem;">
                <div class="hero-badge">📊 RANKINGS</div>
                <h1 style="font-family: var(--font-heading); font-size: 2.8rem; margin-top: 0.5rem;">
                    TOURNAMENT <span class="gradient-text">LEADERBOARD</span>
                </h1>
            </div>

            <div style="margin-bottom: 2rem; display: flex; gap: 1rem; align-items: center; flex-wrap: wrap;">
                <label style="font-weight: 700; color: var(--accent-cyan);">Select Tournament:</label>
                <select onchange="App.changeLeaderboardTournament(this.value)" class="form-select" style="max-width: 320px;">
                    ${tournaments.map(t => `<option value="${t.slug}" ${t.slug === this.activeTournamentSlug ? 'selected' : ''}>${t.title}</option>`).join('')}
                </select>
            </div>

            <div class="data-table-wrapper glass-panel">
                <table class="data-table">
                    <thead>
                        <tr>
                            <th>Rank</th>
                            <th>Team Name</th>
                            <th>Played</th>
                            <th>Wins</th>
                            <th>Losses</th>
                            <th>Points</th>
                        </tr>
                    </thead>
                    <tbody>
                        ${standings.length === 0 ? `
                            <tr><td colspan="6" style="text-align: center; color: var(--text-muted); padding: 3rem;">No completed match data available for standings calculation yet.</td></tr>
                        ` : standings.map((s, idx) => `
                            <tr>
                                <td><strong style="color: ${idx === 0 ? 'var(--accent-gold)' : 'var(--text-primary)'};">#${idx + 1}</strong></td>
                                <td><strong>🛡️ ${s.team_name}</strong></td>
                                <td>${s.played}</td>
                                <td style="color: var(--accent-green); font-weight: 700;">${s.wins}</td>
                                <td style="color: var(--accent-red);">${s.losses}</td>
                                <td><strong style="color: var(--accent-cyan); font-size: 1.1rem;">${s.points} PTS</strong></td>
                            </tr>
                        `).join('')}
                    </tbody>
                </table>
            </div>
        `;
    },

    async changeLeaderboardTournament(slug) {
        this.activeTournamentSlug = slug;
        await this.renderLeaderboardsView();
    },

    // RENDER DASHBOARD VIEW
    async renderDashboardView() {
        const container = document.getElementById('app-content');

        if (!this.userDiscordId) {
            container.innerHTML = `
                <div style="max-width: 450px; margin: 4rem auto;" class="glass-panel">
                    <div style="text-align: center; margin-bottom: 1.5rem;">
                        <div style="font-size: 3rem; margin-bottom: 0.5rem;">👤</div>
                        <h2 style="font-family: var(--font-heading); font-size: 1.8rem;">Player Dashboard</h2>
                        <p style="color: var(--text-secondary); font-size: 0.9rem; margin-top: 0.25rem;">Enter your Discord User ID or Code to view your profile & teams.</p>
                    </div>

                    <form onsubmit="App.loginUserDashboard(event)">
                        <div class="form-group" style="margin-bottom: 1.5rem;">
                            <label>Discord User ID / Player ID</label>
                            <input type="text" id="user-id-input" class="form-input" placeholder="e.g. 123456789012345678" required>
                        </div>
                        <button type="submit" class="btn btn-primary" style="width: 100%;">
                            🔓 Access Dashboard
                        </button>
                    </form>
                </div>
            `;
            return;
        }

        const data = await Api.getUserDashboard(this.userDiscordId);
        const profile = data ? data.profile : null;
        const regs = data ? (data.registrations || []) : [];
        const cases = data ? (data.cases || []) : [];

        container.innerHTML = `
            <div style="margin-bottom: 2.5rem; display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 1rem;">
                <div>
                    <div class="hero-badge">👤 PLAYER DASHBOARD</div>
                    <h1 style="font-family: var(--font-heading); font-size: 2.4rem; margin-top: 0.25rem;">
                        WELCOME BACK, <span class="gradient-text">${profile ? profile.display_name : 'COMPETITOR'}</span>
                    </h1>
                </div>
                <button onclick="App.logoutUserDashboard()" class="btn btn-secondary" style="font-size: 0.85rem;">
                    🔒 Switch Account
                </button>
            </div>

            <div class="stats-banner glass-panel" style="margin-bottom: 2.5rem;">
                <div class="stat-box"><div class="stat-val" style="color: var(--accent-cyan);">${profile ? profile.public_id : 'GEN-P-000000'}</div><div class="stat-lbl">Public ID</div></div>
                <div class="stat-box"><div class="stat-val" style="color: var(--accent-gold);">${regs.length}</div><div class="stat-lbl">Registrations</div></div>
                <div class="stat-box"><div class="stat-val" style="color: var(--accent-green);">${profile && profile.teams ? profile.teams.length : 0}</div><div class="stat-lbl">Active Teams</div></div>
                <div class="stat-box"><div class="stat-val">${cases.length}</div><div class="stat-lbl">Support Cases</div></div>
            </div>

            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 2rem;">
                <div class="glass-panel" style="padding: 1.5rem;">
                    <h3 style="font-family: var(--font-heading); font-size: 1.3rem; margin-bottom: 1rem;">📋 My Registrations (${regs.length})</h3>
                    <div style="display: flex; flex-direction: column; gap: 0.75rem;">
                        ${regs.length === 0 ? '<div style="color: var(--text-muted);">No registrations found. Register via Discord!</div>' : regs.map(r => `
                            <div style="background: rgba(0,0,0,0.3); padding: 0.75rem; border-radius: var(--radius-sm); border: 1px solid var(--border-card);">
                                <div style="display: flex; justify-content: space-between; font-weight: 700; margin-bottom: 0.25rem;">
                                    <span>🛡️ ${r.team_name}</span>
                                    <span class="badge ${r.status === 'APPROVED' ? 'badge-open' : 'badge-closed'}">${r.status}</span>
                                </div>
                                <div style="font-size: 0.8rem; color: var(--text-secondary);">🏆 ${r.tournament_name} • Code: <code>${r.registration_code || r.ticket_id}</code></div>
                            </div>
                        `).join('')}
                    </div>
                </div>

                <div class="glass-panel" style="padding: 1.5rem;">
                    <h3 style="font-family: var(--font-heading); font-size: 1.3rem; margin-bottom: 1rem;">🎧 My Support Cases (${cases.length})</h3>
                    <div style="display: flex; flex-direction: column; gap: 0.75rem;">
                        ${cases.length === 0 ? '<div style="color: var(--text-muted);">No support cases on record.</div>' : cases.map(c => `
                            <div style="background: rgba(0,0,0,0.3); padding: 0.75rem; border-radius: var(--radius-sm); border: 1px solid var(--border-card);">
                                <div style="display: flex; justify-content: space-between; font-weight: 700; margin-bottom: 0.25rem;">
                                    <span>🎧 Case #${c.case_id}</span>
                                    <span class="badge ${c.status === 'CLOSED' ? 'badge-closed' : 'badge-open'}">${c.status}</span>
                                </div>
                                <div style="font-size: 0.8rem; color: var(--text-secondary);">📂 Category: <code>${c.ticket_type}</code> • Priority: <code>${c.priority}</code></div>
                            </div>
                        `).join('')}
                    </div>
                </div>
            </div>
        `;
    },

    loginUserDashboard(e) {
        e.preventDefault();
        const input = document.getElementById('user-id-input');
        const id = input ? input.value.trim() : '';
        if (id) {
            this.userDiscordId = id;
            localStorage.setItem('gen_user_discord_id', id);
            this.renderDashboardView();
        }
    },

    logoutUserDashboard() {
        this.userDiscordId = '';
        localStorage.removeItem('gen_user_discord_id');
        this.renderDashboardView();
    },

    // RENDER ADMIN VIEW
    async renderAdminView() {
        const container = document.getElementById('app-content');

        if (!this.adminApiKey) {
            container.innerHTML = `
                <div style="max-width: 450px; margin: 4rem auto;" class="glass-panel">
                    <div style="text-align: center; margin-bottom: 1.5rem;">
                        <div style="font-size: 3rem; margin-bottom: 0.5rem;">🔑</div>
                        <h2 style="font-family: var(--font-heading); font-size: 1.8rem;">Admin Portal</h2>
                        <p style="color: var(--text-secondary); font-size: 0.9rem; margin-top: 0.25rem;">Enter your API Key to manage tournaments & approvals.</p>
                    </div>

                    <form onsubmit="App.loginAdmin(event)">
                        <div class="form-group" style="margin-bottom: 1.5rem;">
                            <label>API Key</label>
                            <input type="password" id="admin-key-input" class="form-input" placeholder="Enter X-API-Key..." required>
                        </div>
                        <button type="submit" class="btn btn-primary" style="width: 100%;">
                            🔓 Login to Admin Panel
                        </button>
                    </form>
                </div>
            `;
            return;
        }

        try {
            const stats = await Api.getAdminStats(this.adminApiKey);
            const tournaments = await Api.getAdminTournaments(this.adminApiKey);

            container.innerHTML = `
                <div class="admin-container">
                    <div class="admin-header">
                        <div>
                            <div class="hero-badge">⚙️ ADMIN CONTROL DASHBOARD</div>
                            <h1 style="font-family: var(--font-heading); font-size: 2.4rem; margin-top: 0.25rem;">
                                PLATFORM <span class="gradient-text">MANAGEMENT</span>
                            </h1>
                        </div>
                        <button onclick="App.logoutAdmin()" class="btn btn-secondary" style="font-size: 0.85rem;">
                            🔒 Logout
                        </button>
                    </div>

                    <div class="admin-nav-tabs">
                        <button onclick="App.switchAdminTab('overview')" class="admin-tab-btn ${this.adminTab === 'overview' ? 'active' : ''}">📊 Overview & Registrations</button>
                        <button onclick="App.switchAdminTab('tournaments')" class="admin-tab-btn ${this.adminTab === 'tournaments' ? 'active' : ''}">🏆 Tournament Manager</button>
                        <button onclick="App.switchAdminTab('matches')" class="admin-tab-btn ${this.adminTab === 'matches' ? 'active' : ''}">⚔️ Match & Score Input</button>
                        <button onclick="App.switchAdminTab('audit')" class="admin-tab-btn ${this.adminTab === 'audit' ? 'active' : ''}">📜 Audit Logs</button>
                    </div>

                    <div id="admin-tab-content">
                        <!-- Rendered dynamically based on adminTab -->
                    </div>
                </div>
            `;

            await this.renderAdminTabContent(stats, tournaments);
        } catch (err) {
            console.error('Admin login error:', err);
            this.adminApiKey = '';
            sessionStorage.removeItem('gen_admin_api_key');
            alert('Invalid API Key or authorization error.');
            await this.renderAdminView();
        }
    },

    loginAdmin(e) {
        e.preventDefault();
        const input = document.getElementById('admin-key-input');
        const key = input ? (input.value.strip ? input.value.strip() : input.value.trim()) : '';
        if (key) {
            this.adminApiKey = key;
            sessionStorage.setItem('gen_admin_api_key', key);
            this.renderAdminView();
        }
    },

    logoutAdmin() {
        this.adminApiKey = '';
        sessionStorage.removeItem('gen_admin_api_key');
        this.renderAdminView();
    },

    async switchAdminTab(tabName) {
        this.adminTab = tabName;
        await this.renderAdminView();
    },

    async renderAdminTabContent(stats, tournaments) {
        const container = document.getElementById('admin-tab-content');
        if (!container) return;

        if (this.adminTab === 'overview') {
            const pendingRegs = await Api.getAdminRegistrations(this.adminApiKey, 'PENDING');

            container.innerHTML = `
                <div class="stats-banner glass-panel" style="margin-bottom: 2rem;">
                    <div class="stat-box"><div class="stat-val">${stats.total_tournaments ?? 0}</div><div class="stat-lbl">Total Tournaments</div></div>
                    <div class="stat-box"><div class="stat-val" style="color: var(--accent-gold);">${stats.pending_registrations ?? 0}</div><div class="stat-lbl">Pending Approvals</div></div>
                    <div class="stat-box"><div class="stat-val" style="color: var(--accent-green);">${stats.approved_registrations ?? 0}</div><div class="stat-lbl">Approved Teams</div></div>
                    <div class="stat-box"><div class="stat-val">${stats.completed_matches ?? 0}</div><div class="stat-lbl">Completed Matches</div></div>
                </div>

                <h3 style="font-family: var(--font-heading); font-size: 1.4rem; margin-bottom: 1rem;">📋 Pending Team Registrations (${pendingRegs.length})</h3>
                <div style="display: grid; grid-template-columns: repeat(auto-fill, minmax(340px, 1fr)); gap: 1.5rem;">
                    ${pendingRegs.length === 0 ? `
                        <div class="glass-panel" style="padding: 3rem; text-align: center; grid-column: 1 / -1;">
                            <div style="font-size: 2.5rem; margin-bottom: 0.5rem;">✅</div>
                            <h4>No Pending Registrations</h4>
                            <p style="color: var(--text-muted);">All team registration tickets have been reviewed.</p>
                        </div>
                    ` : pendingRegs.map(r => `
                        <div class="glass-panel" style="padding: 1.5rem;">
                            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.75rem;">
                                <strong style="font-size: 1.1rem; color: var(--accent-cyan);">${r.team_name || 'Team'}</strong>
                                <span class="badge badge-draft">PENDING</span>
                            </div>
                            <div style="font-size: 0.85rem; color: var(--text-secondary); margin-bottom: 1rem;">
                                🏆 <strong>Tournament:</strong> ${r.tournament_name || 'N/A'}<br>
                                👑 <strong>Captain:</strong> ${r.captain_name || 'N/A'} (<span style="color: var(--accent-gold);">${r.captain_phone || ''}</span>)<br>
                                🆔 <strong>Code:</strong> ${r.registration_code || r.ticket_id}
                            </div>
                            <div style="display: flex; gap: 0.75rem;">
                                <button onclick="App.approveTeamAdmin(${r.ticket_id})" class="btn btn-primary" style="flex: 1; padding: 0.5rem;">✅ Approve</button>
                                <button onclick="App.rejectTeamAdmin(${r.ticket_id})" class="btn btn-danger" style="flex: 1; padding: 0.5rem; background: var(--accent-red); color: #fff;">❌ Reject</button>
                            </div>
                        </div>
                    `).join('')}
                </div>
            `;
        } else if (this.adminTab === 'tournaments') {
            container.innerHTML = `
                <div class="glass-panel" style="padding: 2rem; margin-bottom: 2.5rem;">
                    <h3 style="font-family: var(--font-heading); font-size: 1.4rem; margin-bottom: 1.25rem;">➕ Create New Tournament</h3>
                    <form onsubmit="App.handleCreateTournament(event)">
                        <div class="form-grid">
                            <div class="form-group"><label>Tournament Name</label><input type="text" id="t-title" class="form-input" placeholder="e.g. GEN Valorant Masters" required></div>
                            <div class="form-group"><label>Game</label><input type="text" id="t-game" class="form-input" placeholder="VALORANT / PUBG MOBILE / CS2 / League of Legends" required></div>
                            <div class="form-group"><label>Prize Pool</label><input type="text" id="t-prize" class="form-input" placeholder="$500 USD / 50,000 BDT"></div>
                            <div class="form-group"><label>Maximum Teams</label><input type="number" id="t-max" class="form-input" value="16" min="2" max="128" required></div>
                            <div class="form-group"><label>Format</label><select id="t-format" class="form-select"><option value="Single Elimination">Single Elimination</option><option value="Double Elimination">Double Elimination</option><option value="Round Robin">Round Robin</option></select></div>
                            <div class="form-group"><label>Initial Status</label><select id="t-status" class="form-select"><option value="REGISTRATION_OPEN">🟢 REGISTRATION OPEN</option><option value="DRAFT">⏸️ DRAFT</option><option value="REGISTRATION_CLOSED">🔴 REGISTRATION CLOSED</option><option value="ONGOING">🔵 ONGOING</option><option value="COMPLETED">🏆 COMPLETED</option></select></div>
                            <div class="form-group"><label>Registration Start</label><input type="datetime-local" id="t-reg-start" class="form-input"></div>
                            <div class="form-group"><label>Registration Deadline</label><input type="datetime-local" id="t-reg-deadline" class="form-input"></div>
                            <div class="form-group"><label>Tournament Start</label><input type="datetime-local" id="t-start" class="form-input"></div>
                            <div class="form-group"><label>Tournament End</label><input type="datetime-local" id="t-end" class="form-input"></div>
                        </div>
                        <div class="form-group" style="margin-top: 1rem;"><label>Description</label><textarea id="t-desc" class="form-textarea" rows="2" placeholder="Brief tournament summary..."></textarea></div>
                        <div class="form-group" style="margin-top: 1rem;"><label>Rules & Guidelines</label><textarea id="t-rules" class="form-textarea" rows="3" placeholder="Full tournament rules text..."></textarea></div>
                        <button type="submit" class="btn btn-primary" style="margin-top: 1.25rem;">✨ Create Tournament</button>
                    </form>
                </div>

                <h3 style="font-family: var(--font-heading); font-size: 1.4rem; margin-bottom: 1rem;">🏆 Active Database Tournaments</h3>
                <div class="data-table-wrapper glass-panel">
                    <table class="data-table">
                        <thead>
                            <tr><th>ID</th><th>Name</th><th>Game</th><th>Reg Status</th><th>Main Status</th><th>Teams</th><th>Quick Actions</th></tr>
                        </thead>
                        <tbody>
                            ${tournaments.map(t => {
                                const approved = t.current_approved_team_count || 0;
                                const maxT = t.max_teams || 16;
                                const isFull = approved >= maxT || t.registration_status === 'FULL';
                                return `
                                    <tr>
                                        <td>#${t.tournament_id}</td>
                                        <td><strong>${t.title}</strong></td>
                                        <td><span style="color: var(--accent-cyan); font-weight: 700;">${t.game_type}</span></td>
                                        <td><span class="badge ${isFull ? 'badge-closed' : (t.registration_status === 'OPEN' ? 'badge-open' : 'badge-closed')}">${isFull ? 'FULL' : t.registration_status}</span></td>
                                        <td><span class="badge badge-ongoing">${t.status}</span></td>
                                        <td><strong>${approved} / ${maxT}</strong></td>
                                        <td style="display: flex; gap: 0.4rem; flex-wrap: wrap;">
                                            <button onclick="App.handleOpenRegistration(${t.tournament_id})" class="btn btn-secondary" style="padding: 0.25rem 0.5rem; font-size: 0.75rem;" title="Open Registration">🟢 Open</button>
                                            <button onclick="App.handleCloseRegistration(${t.tournament_id})" class="btn btn-secondary" style="padding: 0.25rem 0.5rem; font-size: 0.75rem;" title="Close Registration">🔴 Close</button>
                                            <select onchange="App.handleSetStatus(${t.tournament_id}, this.value)" class="form-select" style="padding: 0.25rem; font-size: 0.75rem; width: auto;">
                                                <option value="" disabled selected>Status...</option>
                                                <option value="DRAFT">DRAFT</option>
                                                <option value="REGISTRATION_OPEN">REG OPEN</option>
                                                <option value="REGISTRATION_CLOSED">REG CLOSED</option>
                                                <option value="ONGOING">ONGOING</option>
                                                <option value="COMPLETED">COMPLETED</option>
                                                <option value="CANCELLED">CANCELLED</option>
                                            </select>
                                            <button onclick="App.handleGenerateBracket('${t.tournament_id}')" class="btn btn-secondary" style="padding: 0.25rem 0.5rem; font-size: 0.75rem;">🌳 Bracket</button>
                                            <button onclick="App.handleCancelTournament(${t.tournament_id})" class="btn btn-danger" style="padding: 0.25rem 0.5rem; font-size: 0.75rem; background: var(--accent-red); color:#fff;">❌ Cancel</button>
                                        </td>
                                    </tr>
                                `;
                            }).join('')}
                        </tbody>
                    </table>
                </div>
            `;
        } else if (this.adminTab === 'matches') {
            const matches = await Api.getMatches();

            container.innerHTML = `
                <h3 style="font-family: var(--font-heading); font-size: 1.4rem; margin-bottom: 1rem;">⚔️ Update Match Scores</h3>
                <div class="data-table-wrapper glass-panel">
                    <table class="data-table">
                        <thead>
                            <tr><th>Match ID</th><th>Tournament</th><th>Stage</th><th>Team 1</th><th>Team 2</th><th>Score</th><th>Action</th></tr>
                        </thead>
                        <tbody>
                            ${matches.length === 0 ? `
                                <tr><td colspan="7" style="text-align: center; color: var(--text-muted); padding: 2rem;">No matches scheduled. Generate a bracket first.</td></tr>
                            ` : matches.map(m => `
                                <tr>
                                    <td>#${m.match_id}</td>
                                    <td>${m.tournament_name || 'N/A'}</td>
                                    <td>${m.stage_name}</td>
                                    <td>🛡️ ${m.team1_name || 'TBD'}</td>
                                    <td>🛡️ ${m.team2_name || 'TBD'}</td>
                                    <td><strong>${m.team1_score ?? 0} - ${m.team2_score ?? 0}</strong></td>
                                    <td>
                                        <button onclick="App.showScoreInputModal(${m.match_id}, '${m.team1_name || 'Team 1'}', '${m.team2_name || 'Team 2'}')" class="btn btn-primary" style="padding: 0.3rem 0.6rem; font-size: 0.75rem;">✏️ Update Score</button>
                                    </td>
                                </tr>
                            `).join('')}
                        </tbody>
                    </table>
                </div>
            `;
        } else if (this.adminTab === 'audit') {
            const logs = await Api.getAuditLogs(this.adminApiKey);

            container.innerHTML = `
                <h3 style="font-family: var(--font-heading); font-size: 1.4rem; margin-bottom: 1rem;">📜 Admin Action Audit Logs (${logs.length})</h3>
                <div class="data-table-wrapper glass-panel">
                    <table class="data-table">
                        <thead>
                            <tr><th>Log ID</th><th>Timestamp</th><th>Admin</th><th>Action</th><th>Tournament</th><th>Details</th></tr>
                        </thead>
                        <tbody>
                            ${logs.length === 0 ? `
                                <tr><td colspan="6" style="text-align: center; color: var(--text-muted); padding: 2rem;">No audit logs recorded yet.</td></tr>
                            ` : logs.map(l => `
                                <tr>
                                    <td>#${l.log_id}</td>
                                    <td style="font-size: 0.8rem; color: var(--text-muted);">${l.timestamp}</td>
                                    <td><strong style="color: var(--accent-gold);">${l.admin_id}</strong></td>
                                    <td><span class="badge badge-ongoing">${l.action}</span></td>
                                    <td>${l.tournament_name || (l.tournament_id ? `#${l.tournament_id}` : '-')}</td>
                                    <td style="font-size: 0.85rem; color: var(--text-secondary);">${l.details || '-'}</td>
                                </tr>
                            `).join('')}
                        </tbody>
                    </table>
                </div>
            `;
        }
    },

    async approveTeamAdmin(ticketId) {
        try {
            await Api.approveRegistration(this.adminApiKey, ticketId);
            alert('Registration approved successfully!');
            await this.renderAdminView();
        } catch (err) {
            alert('Error approving registration: ' + err.message);
        }
    },

    async rejectTeamAdmin(ticketId) {
        const reason = prompt('Enter rejection reason:');
        if (!reason) return;
        try {
            await Api.rejectRegistration(this.adminApiKey, ticketId, reason);
            alert('Registration rejected successfully!');
            await this.renderAdminView();
        } catch (err) {
            alert('Error rejecting registration: ' + err.message);
        }
    },

    async handleCreateTournament(e) {
        e.preventDefault();
        const title = document.getElementById('t-title').value;
        const game_type = document.getElementById('t-game').value;
        const prize_info = document.getElementById('t-prize').value;
        const max_teams = parseInt(document.getElementById('t-max').value || '16', 10);
        const format = document.getElementById('t-format').value;
        const status = document.getElementById('t-status').value;
        const registration_start = document.getElementById('t-reg-start').value;
        const registration_deadline = document.getElementById('t-reg-deadline').value;
        const tournament_start = document.getElementById('t-start').value;
        const tournament_end = document.getElementById('t-end').value;
        const description = document.getElementById('t-desc').value;
        const rules_text = document.getElementById('t-rules').value;

        const registration_status = status === 'REGISTRATION_OPEN' ? 'OPEN' : 'CLOSED';

        try {
            await Api.createTournament(this.adminApiKey, {
                title, game_type, prize_info, max_teams, format, status,
                registration_status, registration_start, registration_deadline,
                tournament_start, tournament_end, description, rules_text
            });
            alert('Tournament created! If status is OPEN, it is now live in Discord registration.');
            await this.renderAdminView();
        } catch (err) {
            alert('Failed to create tournament: ' + err.message);
        }
    },

    async handleOpenRegistration(id) {
        try {
            await Api.openRegistration(this.adminApiKey, id);
            alert('Registration opened! Tournament is now active in Discord dropdown.');
            await this.renderAdminView();
        } catch (err) {
            alert('Error opening registration: ' + err.message);
        }
    },

    async handleCloseRegistration(id) {
        try {
            await Api.closeRegistration(this.adminApiKey, id);
            alert('Registration closed.');
            await this.renderAdminView();
        } catch (err) {
            alert('Error closing registration: ' + err.message);
        }
    },

    async handleSetStatus(id, newStatus) {
        if (!newStatus) return;
        try {
            await Api.setTournamentStatus(this.adminApiKey, id, newStatus);
            alert(`Tournament status updated to ${newStatus}.`);
            await this.renderAdminView();
        } catch (err) {
            alert('Error changing status: ' + err.message);
        }
    },

    async handleCancelTournament(id) {
        if (!confirm('Are you sure you want to cancel this tournament?')) return;
        try {
            await Api.cancelTournament(this.adminApiKey, id);
            alert('Tournament cancelled.');
            await this.renderAdminView();
        } catch (err) {
            alert('Error cancelling tournament: ' + err.message);
        }
    },

    async handleGenerateBracket(id) {
        try {
            await Api.generateBracket(this.adminApiKey, id);
            alert('Tournament bracket generated successfully!');
            await this.renderAdminView();
        } catch (err) {
            alert('Error generating bracket: ' + err.message);
        }
    },

    showScoreInputModal(matchId, t1Name, t2Name) {
        this.showModal(`
            <h3 style="font-family: var(--font-heading); font-size: 1.5rem; margin-bottom: 1rem;">✏️ Enter Match Score</h3>
            <form onsubmit="App.handleSaveMatchScore(event, ${matchId})">
                <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 1rem; margin-bottom: 1.5rem;">
                    <div class="form-group">
                        <label>${t1Name} Score</label>
                        <input type="number" id="m-score1" class="form-input" value="0" min="0" required>
                    </div>
                    <div class="form-group">
                        <label>${t2Name} Score</label>
                        <input type="number" id="m-score2" class="form-input" value="0" min="0" required>
                    </div>
                </div>
                <button type="submit" class="btn btn-primary" style="width: 100%;">💾 Save Match Result</button>
            </form>
        `);
    },

    async handleSaveMatchScore(e, matchId) {
        e.preventDefault();
        const score1 = parseInt(document.getElementById('m-score1').value || '0', 10);
        const score2 = parseInt(document.getElementById('m-score2').value || '0', 10);

        try {
            await Api.submitMatchResult(this.adminApiKey, matchId, {
                team1_score: score1,
                team2_score: score2,
                status: 'COMPLETED'
            });
            this.hideModal();
            alert('Match score recorded and winner advanced!');
            await this.renderAdminView();
        } catch (err) {
            alert('Error recording score: ' + err.message);
        }
    }
};

window.App = App;
