/**
 * GEN ESPORTS WEB PLATFORM APPLICATION CONTROLLER
 * Independent Competitive Tournament Platform Logic.
 */

document.addEventListener('DOMContentLoaded', () => {
    App.init();
});

const TEAM_PLACEHOLDER_LOGO = 'data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSI2NCIgaGVpZ2h0PSI2NCIgdmlld0JveD0iMCAwIDY0IDY0Ij48cmVjdCB3aWR0aD0iNjQiIGhlaWdodD0iNjQiIHJ4PSIxMiIgZmlsbD0iIzFhMjAzNSIvPjx0ZXh0IHg9IjUwJSIgeT0iNTUlIiBkb21pbmFudC1iYXNlbGluZT0ibWlkZGxlIiB0ZXh0LWFuY2hvcj0ibWlkZGxlIiBmb250LXNpemU9IjI4Ij7wn4ef77iJPC90ZXh0Pjwvc3ZnPg==';
const PLAYER_PLACEHOLDER_AVATAR = 'data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSI2NCIgaGVpZ2h0PSI2NCIgdmlld0JveD0iMCAwIDY0IDY0Ij48Y2lyY2xlIGN4PSIzMiIgY3k9IzMyIiByPSIzMiIgZmlsbD0iIzFhMjAzNSIvPjx0ZXh0IHg9IjUwJSIgeT0iNTUlIiBkb21pbmFudC1iYXNlbGluZT0ibWlkZGxlIiB0ZXh0LWFuY2hvcj0ibWlkZGxlIiBmb250LXNpemU9IjI4Ij7wn5CwPC90ZXh0Pjwvc3ZnPg==';

function toDateTimeLocalValue(value) {
    if (!value) return '';

    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return '';

    const pad = n => String(n).padStart(2, '0');

    return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`;
}

const App = {
    toDateTimeLocalValue,
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
        if (!container) return;

        let tournaments = [];
        try {
            tournaments = await Api.getTournaments();
        } catch (e) {
            console.warn('Error fetching tournaments:', e);
        }

        container.innerHTML = `
            <div style="margin-bottom: 2.5rem;">
                <div class="hero-badge">🏆 COMPETITIVE EVENTS</div>
                <h1 style="font-family: var(--font-heading); font-size: 2.4rem; margin-top: 0.25rem;">
                    ACTIVE & UPCOMING <span class="gradient-text">TOURNAMENTS</span>
                </h1>
                <p style="color: var(--text-secondary); font-size: 0.95rem; margin-top: 0.5rem;">
                    Explore active tournaments, team limits, prize pools, and rules. Join via Discord commands.
                </p>
            </div>

            <div class="tournaments-grid">
                ${tournaments.length === 0 ? `
                    <div class="glass-panel" style="padding: 4rem 2rem; text-align: center; grid-column: 1 / -1;">
                        <div style="font-size: 3rem; margin-bottom: 1rem;">🏆</div>
                        <h3 style="font-family: var(--font-heading); font-size: 1.5rem;">No Active Tournaments</h3>
                        <p style="color: var(--text-secondary); margin-top: 0.5rem;">Check back soon or join our Discord server for announcement alerts!</p>
                    </div>
                ` : tournaments.map(t => this.buildTournamentCardHtml(t)).join('')}
            </div>
        `;
    },

    handleImgError(img, fallbackUrl) {
        if (img && img.src !== fallbackUrl) {
            img.onerror = null;
            img.src = fallbackUrl;
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
        const approvedCount = t.current_approved_team_count || 0;
        const maxTeams = t.max_teams || 16;
        const percent = Math.min(100, Math.round((approvedCount / maxTeams) * 100));
        const isFull = approvedCount >= maxTeams || t.registration_status === 'FULL';
        const regBadgeClass = isFull ? 'badge-closed' : (t.registration_status === 'OPEN' ? 'badge-open' : 'badge-closed');
        const regText = isFull ? '🔴 REGISTRATION FULL' : (t.registration_status === 'OPEN' ? '🟢 REGISTRATION OPEN' : '🔴 REGISTRATION CLOSED');

        return `
            <div class="esports-card" onclick="App.showTournamentDetailsModal('${this.escapeHtml(t.slug || t.tournament_id)}')">
                <div class="esports-card-banner">
                    <span class="badge ${regBadgeClass}" style="z-index: 2;">${regText}</span>
                    <span class="badge badge-draft" style="z-index: 2;">${this.escapeHtml(t.game_type || 'ESPORTS')}</span>
                </div>
                <div class="esports-card-body">
                    <h3 style="font-family: var(--font-heading); font-size: 1.35rem; font-weight: 800; color: #fff; margin-bottom: 0.5rem; line-height: 1.3;">
                        ${this.escapeHtml(t.title)}
                    </h3>
                    <p style="color: var(--text-secondary); font-size: 0.88rem; line-height: 1.5; margin-bottom: 1.25rem; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden;">
                        ${this.escapeHtml(t.description || 'Official GEN Esports competitive tournament. Register your roster and compete.')}
                    </p>

                    <div style="margin-top: auto; padding-top: 1rem; border-top: 1px solid rgba(255,255,255,0.06);">
                        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.5rem;">
                            <div>
                                <div style="font-size: 0.72rem; color: var(--text-muted); font-weight: 700; text-transform: uppercase;">PRIZE POOL</div>
                                <div style="color: var(--accent-gold); font-weight: 800; font-size: 1.1rem;">${this.escapeHtml(t.prize_info || '৳500 BDT')}</div>
                            </div>
                            <div style="text-align: right;">
                                <div style="font-size: 0.72rem; color: var(--text-muted); font-weight: 700; text-transform: uppercase;">ROSTERS</div>
                                <div style="color: #fff; font-weight: 800; font-size: 0.95rem;">${approvedCount} / ${maxTeams} Teams</div>
                            </div>
                        </div>

                        <div class="progress-track">
                            <div class="progress-fill" style="width: ${percent}%;"></div>
                        </div>

                        <button class="btn btn-primary" style="width: 100%; margin-top: 1.25rem; padding: 0.65rem; font-size: 0.9rem;">
                            ✨ VIEW TOURNAMENT
                        </button>
                    </div>
                </div>
            </div>
        `;
    },

    async showTournamentDetailsModal(slug) {
        this.showModal(`
            <div style="text-align: center; padding: 3rem;">
                <div class="spinner" style="margin: 0 auto 1rem;"></div>
                <p style="color: var(--text-secondary); font-weight: 600;">Loading tournament details...</p>
            </div>
        `);

        try {
            const data = await Api.getTournamentDetails(slug);
            const t = (data && data.tournament) ? data.tournament : (data && data.title ? data : null);
            const teams = (data && data.approved_teams) ? data.approved_teams : [];

            if (!t) {
                this.showModal(`
                    <div style="text-align: center; padding: 3rem;">
                        <h3 style="font-family: var(--font-heading); color: var(--accent-red); font-size: 1.8rem;">Tournament Not Found</h3>
                        <p style="color: var(--text-secondary); margin-top: 0.5rem;">Could not load details for this tournament.</p>
                        <button onclick="App.hideModal()" class="btn btn-secondary" style="margin-top: 1.5rem;">Close</button>
                    </div>
                `);
                return;
            }

            const approvedCount = teams.length;
            const maxTeams = t.max_teams || 16;
            const isFull = approvedCount >= maxTeams || t.registration_status === 'FULL';
            const percent = Math.min(100, Math.round((approvedCount / maxTeams) * 100));

            this.showModal(`
                <div style="max-width: 760px; margin: 0 auto;">
                    <div style="background: linear-gradient(135deg, rgba(15, 23, 42, 0.9), rgba(30, 41, 59, 0.8)); padding: 1.5rem; border-radius: var(--radius-md); border: 1px solid var(--border-card); margin-bottom: 1.5rem;">
                        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.75rem; flex-wrap: wrap; gap: 0.5rem;">
                            <div style="display: flex; gap: 0.5rem;">
                                <span class="badge ${isFull ? 'badge-closed' : 'badge-open'}">${isFull ? '🔴 REGISTRATION FULL' : (t.registration_status === 'OPEN' ? '🟢 REGISTRATION OPEN' : '🔴 CLOSED')}</span>
                                <span class="badge badge-draft">${this.escapeHtml(t.game_type || 'VALORANT')}</span>
                            </div>
                            <span style="color: var(--accent-gold); font-weight: 800; font-size: 1.25rem;">🏆 Prize: ${this.escapeHtml(t.prize_info || '৳500 BDT')}</span>
                        </div>

                        <h2 style="font-family: var(--font-heading); font-size: 2rem; font-weight: 900; color: #fff; margin-bottom: 0.5rem;">${this.escapeHtml(t.title)}</h2>
                        <p style="color: var(--text-secondary); line-height: 1.6; font-size: 0.95rem; margin-bottom: 1rem;">${this.escapeHtml(t.description || 'Official GEN Esports competitive tournament.')}</p>

                        <div style="margin-top: 1rem;">
                            <div style="display: flex; justify-content: space-between; font-size: 0.85rem; font-weight: 700; color: var(--text-secondary); margin-bottom: 0.35rem;">
                                <span>APPROVED TEAMS CAPACITY</span>
                                <span>${approvedCount} / ${maxTeams} Teams (${percent}%)</span>
                            </div>
                            <div class="progress-track" style="height: 8px;">
                                <div class="progress-fill" style="width: ${percent}%;"></div>
                            </div>
                        </div>
                    </div>

                    <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap: 1rem; margin-bottom: 1.5rem;">
                        <div style="background: rgba(0,0,0,0.3); padding: 0.85rem; border-radius: var(--radius-sm); border: 1px solid var(--border-card);">
                            <div style="font-size: 0.72rem; color: var(--text-muted); font-weight: 700;">REGISTRATION START</div>
                            <div style="font-weight: 700; font-size: 0.9rem; color: #fff; margin-top: 0.25rem;">📅 ${this.escapeHtml(t.registration_start || 'Immediate')}</div>
                        </div>
                        <div style="background: rgba(0,0,0,0.3); padding: 0.85rem; border-radius: var(--radius-sm); border: 1px solid var(--border-card);">
                            <div style="font-size: 0.72rem; color: var(--text-muted); font-weight: 700;">REGISTRATION DEADLINE</div>
                            <div style="font-weight: 700; font-size: 0.9rem; color: #fff; margin-top: 0.25rem;">📅 ${this.escapeHtml(t.registration_deadline || 'TBD')}</div>
                        </div>
                        <div style="background: rgba(0,0,0,0.3); padding: 0.85rem; border-radius: var(--radius-sm); border: 1px solid var(--border-card);">
                            <div style="font-size: 0.72rem; color: var(--text-muted); font-weight: 700;">TOURNAMENT START</div>
                            <div style="font-weight: 700; font-size: 0.9rem; color: #fff; margin-top: 0.25rem;">📅 ${this.escapeHtml(t.tournament_start || 'TBD')}</div>
                        </div>
                        <div style="background: rgba(0,0,0,0.3); padding: 0.85rem; border-radius: var(--radius-sm); border: 1px solid var(--border-card);">
                            <div style="font-size: 0.72rem; color: var(--text-muted); font-weight: 700;">FORMAT</div>
                            <div style="font-weight: 700; font-size: 0.9rem; color: var(--accent-cyan); margin-top: 0.25rem;">⚔️ ${this.escapeHtml(t.format || 'Single Elimination')}</div>
                        </div>
                    </div>

                    <div style="background: rgba(0,0,0,0.3); padding: 1.25rem; border-radius: var(--radius-md); border: 1px solid var(--border-card); margin-bottom: 1.5rem;">
                        <h4 style="font-family: var(--font-heading); font-size: 1.1rem; margin-bottom: 0.75rem; color: var(--accent-cyan);">📜 Tournament Rules & Guidelines</h4>
                        <p style="color: var(--text-secondary); font-size: 0.88rem; line-height: 1.6; white-space: pre-line;">${this.escapeHtml(t.rules_text || 'Standard GEN Esports Tournament Rules apply.')}</p>
                    </div>

                    <h4 style="font-family: var(--font-heading); font-size: 1.2rem; margin-bottom: 1rem; color: #fff;">🛡️ Approved Registered Teams (${approvedCount} / ${maxTeams})</h4>
                    <div style="display: grid; grid-template-columns: repeat(auto-fill, minmax(210px, 1fr)); gap: 0.75rem; max-height: 250px; overflow-y: auto; padding-right: 0.5rem; margin-bottom: 1.5rem;">
                        ${teams.length === 0 ? `
                            <div style="color: var(--text-muted); font-size: 0.9rem; grid-column: 1 / -1; background: rgba(0,0,0,0.2); padding: 1.5rem; text-align: center; border-radius: var(--radius-sm);">No approved teams yet. Register your team on Discord!</div>
                        ` : teams.map(tm => `
                            <div style="display: flex; align-items: center; gap: 0.75rem; background: rgba(255,255,255,0.04); padding: 0.65rem 0.85rem; border-radius: var(--radius-sm); border: 1px solid var(--border-card); cursor: pointer;" onclick="App.showTeamProfileModal('${this.escapeHtml(tm.slug || tm.public_id || tm.team_name || '')}')">
                                <img src="${this.escapeHtml(tm.logo_url || TEAM_PLACEHOLDER_LOGO)}" onerror="App.handleImgError(this, '${TEAM_PLACEHOLDER_LOGO}')" style="width: 32px; height: 32px; border-radius: 6px; object-fit: cover;">
                                <div style="overflow: hidden;">
                                    <div style="font-weight: 700; font-size: 0.9rem; color: #fff; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">${this.escapeHtml(tm.name || tm.team_name)}</div>
                                    <div style="font-size: 0.75rem; color: var(--accent-gold);">👑 ${this.escapeHtml(tm.captain_name || 'Captain')}</div>
                                </div>
                            </div>
                        `).join('')}
                    </div>

                    <div style="display: flex; justify-content: space-between; align-items: center; border-top: 1px solid var(--border-card); padding-top: 1.25rem;">
                        <button onclick="App.openDiscordInvite()" class="btn btn-discord">
                            💬 Register Team in Discord
                        </button>
                        <button onclick="App.hideModal()" class="btn btn-secondary">Close</button>
                    </div>
                </div>
            `);
        } catch (err) {
            console.error('Error opening tournament details modal:', err);
        }
    },

    // RENDER TEAMS VIEW
    async renderTeamsView() {
        const container = document.getElementById('app-content');
        if (!container) return;

        let teams = [];
        try {
            teams = await Api.getTeams();
        } catch (e) {
            console.warn('Error fetching teams:', e);
        }

        container.innerHTML = `
            <div style="margin-bottom: 2.5rem;">
                <div class="hero-badge">🛡️ COMPETITIVE ROSTERS</div>
                <h1 style="font-family: var(--font-heading); font-size: 2.4rem; margin-top: 0.25rem;">
                    REGISTERED <span class="gradient-text">TEAMS & CLANS</span>
                </h1>
                <p style="color: var(--text-secondary); font-size: 0.95rem; margin-top: 0.5rem;">
                    All officially verified teams competing across GEN Esports tournaments.
                </p>
            </div>

            <div style="display: grid; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); gap: 1.5rem;">
                ${teams.length === 0 ? `
                    <div class="glass-panel" style="padding: 4rem 2rem; text-align: center; grid-column: 1 / -1;">
                        <div style="font-size: 3.5rem; margin-bottom: 1rem;">🛡️</div>
                        <h3 style="font-family: var(--font-heading); font-size: 1.6rem;">No Teams Registered</h3>
                        <p style="color: var(--text-secondary); margin-top: 0.5rem;">Be the first to register your roster on our Discord server!</p>
                    </div>
                ` : teams.map(tm => `
                    <div class="glass-panel team-card-hover" style="padding: 1.5rem; display: flex; flex-direction: column; gap: 1rem; cursor: pointer;" onclick="App.showTeamProfileModal('${this.escapeHtml(tm.slug || tm.public_id || tm.team_id)}')">
                        <div style="display: flex; align-items: center; gap: 1rem;">
                            <img src="${this.escapeHtml(tm.logo_url || TEAM_PLACEHOLDER_LOGO)}" onerror="App.handleImgError(this, '${TEAM_PLACEHOLDER_LOGO}')" style="width: 56px; height: 56px; border-radius: var(--radius-sm); object-fit: cover; border: 2px solid var(--border-card);">
                            <div>
                                <h3 style="font-family: var(--font-heading); font-size: 1.25rem; font-weight: 800; color: #fff;">${this.escapeHtml(tm.name)}</h3>
                                <div style="display: flex; gap: 0.4rem; margin-top: 0.25rem;">
                                    <span class="badge badge-draft" style="font-size: 0.7rem;">${this.escapeHtml(tm.game || 'VALORANT')}</span>
                                    <span class="badge badge-open" style="font-size: 0.7rem;">APPROVED</span>
                                </div>
                            </div>
                        </div>

                        <div style="background: rgba(0,0,0,0.3); padding: 0.75rem 1rem; border-radius: var(--radius-sm); border: 1px solid var(--border-card); font-size: 0.85rem; display: flex; justify-content: space-between; align-items: center;">
                            <div>👑 <strong>Captain:</strong> <span style="color: var(--accent-gold);">${this.escapeHtml(tm.captain_name || 'Captain')}</span></div>
                            <div style="color: var(--text-secondary);">👥 Roster: ${tm.player_count || 5}</div>
                        </div>

                        <div style="font-size: 0.85rem; color: var(--accent-cyan); font-weight: 700; text-align: right;">
                            View Roster & Stats &rarr;
                        </div>
                    </div>
                `).join('')}
            </div>
        `;
    },

    async showTeamProfileModal(teamId) {
        this.showModal(`
            <div style="text-align: center; padding: 2rem;">
                <div class="spinner" style="margin: 0 auto 1rem;"></div>
                <p style="color: var(--text-secondary);">Loading team profile...</p>
            </div>
        `);

        try {
            const data = await Api.getTeamProfile(teamId);
            if (!data || (!data.team && !data.name)) {
                this.showModal(`
                    <div style="text-align: center; padding: 2rem;">
                        <h3 style="font-family: var(--font-heading); color: var(--accent-red);">Team Not Found</h3>
                    </div>
                `);
                return;
            }

            const tm = data.team || data;
            const members = data.roster || data.members || [];
            const stats = data.stats || { matches_played: 0, wins: 0, losses: 0 };

            this.showModal(`
                <div style="max-width: 650px; margin: 0 auto;">
                    <div style="display: flex; align-items: center; gap: 1.25rem; margin-bottom: 1.5rem;">
                        <img src="${this.escapeHtml(tm.logo_url || TEAM_PLACEHOLDER_LOGO)}" onerror="App.handleImgError(this, '${TEAM_PLACEHOLDER_LOGO}')" style="width: 72px; height: 72px; border-radius: var(--radius-md); object-fit: cover; border: 2px solid var(--accent-cyan);">
                        <div>
                            <h2 style="font-family: var(--font-heading); font-size: 2rem; color: #fff;">${this.escapeHtml(tm.name)}</h2>
                            <div style="color: var(--accent-gold); font-weight: 600; font-size: 0.95rem; margin-top: 0.25rem;">
                                👑 Captain: ${this.escapeHtml(tm.captain_name || 'Captain')}
                            </div>
                        </div>
                    </div>

                    <div class="stats-banner glass-panel" style="margin-bottom: 1.5rem;">
                        <div class="stat-box"><div class="stat-val">${stats.matches_played}</div><div class="stat-lbl">Matches</div></div>
                        <div class="stat-box"><div class="stat-val" style="color: var(--accent-green);">${stats.wins}</div><div class="stat-lbl">Wins</div></div>
                        <div class="stat-box"><div class="stat-val" style="color: var(--accent-red);">${stats.losses}</div><div class="stat-lbl">Losses</div></div>
                    </div>

                    <h4 style="font-family: var(--font-heading); font-size: 1.2rem; margin-bottom: 1rem;">👥 Roster Members (${members.length})</h4>
                    <div style="display: flex; flex-direction: column; gap: 0.5rem; max-height: 220px; overflow-y: auto; margin-bottom: 1.5rem;">
                        ${members.length === 0 ? `
                            <div style="color: var(--text-muted); padding: 1rem; text-align: center;">No roster members listed yet.</div>
                        ` : members.map(m => `
                            <div style="display: flex; justify-content: space-between; align-items: center; background: rgba(0,0,0,0.3); padding: 0.75rem 1rem; border-radius: var(--radius-sm); border: 1px solid var(--border-card);">
                                <div style="display: flex; align-items: center; gap: 0.75rem;">
                                    <span style="font-size: 1.2rem;">👤</span>
                                    <div>
                                        <div style="font-weight: 700; color: #fff;">${this.escapeHtml(m.display_name || m.ign || 'Player')}</div>
                                        <div style="font-size: 0.78rem; color: var(--text-muted);">In-Game ID: ${this.escapeHtml(m.in_game_id || m.ign || 'N/A')}</div>
                                    </div>
                                </div>
                                <span class="badge ${m.role === 'CAPTAIN' ? 'badge-ongoing' : 'badge-draft'}">${this.escapeHtml(m.role || 'MEMBER')}</span>
                            </div>
                        `).join('')}
                    </div>

                    <button onclick="App.hideModal()" class="btn btn-secondary">Close</button>
                </div>
            `);
        } catch (err) {
            console.error('Error fetching team profile:', err);
        }
    },

    // RENDER PLAYERS VIEW
    async renderPlayersView() {
        const container = document.getElementById('app-content');
        if (!container) return;

        let players = [];
        try {
            players = await Api.getPlayers();
            this._cachedPlayers = players;
        } catch (e) {
            console.warn('Error fetching players:', e);
        }

        container.innerHTML = `
            <div style="margin-bottom: 2rem; display: flex; justify-content: space-between; align-items: flex-end; flex-wrap: wrap; gap: 1rem;">
                <div>
                    <div class="hero-badge">👤 PLAYER DIRECTORY</div>
                    <h1 style="font-family: var(--font-heading); font-size: 2.4rem; margin-top: 0.25rem;">
                        REGISTERED <span class="gradient-text">COMPETITORS</span>
                    </h1>
                    <p style="color: var(--text-secondary); font-size: 0.95rem; margin-top: 0.5rem;">
                        Browse verified competitive players, in-game handles, and team affiliations.
                    </p>
                </div>

                <div style="width: 100%; max-width: 320px;">
                    <input type="text" id="player-search-input" class="form-input" placeholder="🔍 Search player by IGN or team..." oninput="App.filterPlayersDisplay(this.value)">
                </div>
            </div>

            <div id="players-grid" style="display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 1.25rem;">
                ${this.renderPlayersCardsHtml(players)}
            </div>
        `;
    },

    renderPlayersCardsHtml(players) {
        if (!players || players.length === 0) {
            return `
                <div class="glass-panel" style="padding: 4rem 2rem; text-align: center; grid-column: 1 / -1;">
                    <div style="font-size: 3.5rem; margin-bottom: 1rem;">👤</div>
                    <h3 style="font-family: var(--font-heading); font-size: 1.6rem;">No Players Found</h3>
                    <p style="color: var(--text-secondary); margin-top: 0.5rem;">Registered competitors will appear here when teams are approved.</p>
                </div>
            `;
        }

        return players.map(p => `
            <div class="glass-panel player-card-hover" style="padding: 1.25rem; display: flex; align-items: center; gap: 1.25rem; cursor: pointer;" onclick="App.showPlayerProfileModal('${this.escapeHtml(p.public_id || p.discord_id || p.ign || '')}')">
                <img src="${PLAYER_PLACEHOLDER_AVATAR}" style="width: 52px; height: 52px; border-radius: 50%; border: 2px solid var(--accent-cyan); object-fit: cover;">
                <div style="overflow: hidden;">
                    <div style="font-weight: 800; color: #fff; font-size: 1.1rem; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">${this.escapeHtml(p.display_name || p.ign)}</div>
                    <div style="font-size: 0.78rem; color: var(--accent-gold); font-weight: 600; margin-top: 0.15rem;">ID: ${this.escapeHtml(p.public_id || 'GEN-P')}</div>
                    <div style="font-size: 0.8rem; color: var(--text-secondary); margin-top: 0.25rem; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">
                        🛡️ <strong style="color: #fff;">${this.escapeHtml(p.primary_team || 'Free Agent')}</strong>
                    </div>
                </div>
            </div>
        `).join('');
    },

    filterPlayersDisplay(query) {
        const q = (query || '').toLowerCase().trim();
        const grid = document.getElementById('players-grid');
        if (!grid) return;

        if (!this._cachedPlayers) {
            Api.getPlayers().then(players => {
                this._cachedPlayers = players;
                this.applyPlayerFilter(grid, q);
            });
        } else {
            this.applyPlayerFilter(grid, q);
        }
    },

    applyPlayerFilter(grid, query) {
        if (!this._cachedPlayers) return;
        const filtered = !query ? this._cachedPlayers : this._cachedPlayers.filter(p => 
            (p.display_name || '').toLowerCase().includes(query) ||
            (p.ign || '').toLowerCase().includes(query) ||
            (p.primary_team || '').toLowerCase().includes(query)
        );
        grid.innerHTML = this.renderPlayersCardsHtml(filtered);
    },

    async showPlayerProfileModal(playerId) {
        this.showModal(`
            <div style="text-align: center; padding: 2rem;">
                <div class="spinner" style="margin: 0 auto 1rem;"></div>
                <p style="color: var(--text-secondary);">Loading player profile...</p>
            </div>
        `);

        try {
            const p = await Api.getPlayerProfile(playerId);
            if (!p) {
                this.showModal(`
                    <div style="text-align: center; padding: 2rem;">
                        <h3 style="font-family: var(--font-heading); color: var(--accent-red);">Player Not Found</h3>
                    </div>
                `);
                return;
            }

            this.showModal(`
                <div style="max-width: 500px; margin: 0 auto; text-align: center;">
                    <img src="${PLAYER_PLACEHOLDER_AVATAR}" style="width: 80px; height: 80px; border-radius: 50%; border: 3px solid var(--accent-cyan); margin-bottom: 1rem;">
                    <h2 style="font-family: var(--font-heading); font-size: 1.8rem; color: #fff;">${this.escapeHtml(p.display_name || p.ign)}</h2>
                    <div style="color: var(--accent-cyan); font-weight: 700; font-size: 0.95rem; margin-bottom: 1.5rem;">Public ID: ${this.escapeHtml(p.public_id || 'GEN-P')}</div>

                    <div style="background: rgba(0,0,0,0.3); padding: 1.25rem; border-radius: var(--radius-md); border: 1px solid var(--border-card); text-align: left; margin-bottom: 1.5rem;">
                        <div style="margin-bottom: 0.75rem;">🎮 <strong>In-Game Name/ID:</strong> ${this.escapeHtml(p.in_game_id || p.ign || 'N/A')}</div>
                        <div style="margin-bottom: 0.75rem;">🛡️ <strong>Current Team:</strong> ${this.escapeHtml(p.primary_team || 'Free Agent')}</div>
                        <div style="margin-bottom: 0.75rem;">🏆 <strong>Primary Game:</strong> ${this.escapeHtml(p.primary_game || 'VALORANT')}</div>
                        <div>✅ <strong>Verification:</strong> <span style="color: var(--accent-green); font-weight: 700;">${this.escapeHtml(p.verification_status || 'VERIFIED')}</span></div>
                    </div>

                    <button onclick="App.hideModal()" class="btn btn-secondary">Close</button>
                </div>
            `);
        } catch (err) {
            console.error('Error fetching player profile:', err);
        }
    },

    // RENDER MATCHES VIEW
    async renderMatchesView() {
        const container = document.getElementById('app-content');
        if (!container) return;

        let matches = [];
        try {
            matches = await Api.getMatches();
        } catch (e) {
            console.warn('Error fetching matches:', e);
        }

        container.innerHTML = `
            <div style="margin-bottom: 2.5rem;">
                <div class="hero-badge">⚔️ COMPETITIVE MATCHES</div>
                <h1 style="font-family: var(--font-heading); font-size: 2.4rem; margin-top: 0.25rem;">
                    LIVE MATCHES & <span class="gradient-text">RESULTS</span>
                </h1>
                <p style="color: var(--text-secondary); font-size: 0.95rem; margin-top: 0.5rem;">
                    Real-time match schedules, live scores, map picks, and bracket advancement.
                </p>
            </div>

            <div style="display: flex; flex-direction: column; gap: 1rem;">
                ${matches.length === 0 ? `
                    <div class="glass-panel" style="padding: 4rem 2rem; text-align: center;">
                        <div style="font-size: 3.5rem; margin-bottom: 1rem;">⚔️</div>
                        <h3 style="font-family: var(--font-heading); font-size: 1.6rem;">No Active Matches Scheduled</h3>
                        <p style="color: var(--text-secondary); margin-top: 0.5rem;">Matches will appear here once brackets are generated by organizers.</p>
                    </div>
                ` : matches.map(m => {
                    const t1Name = m.team1_name || m.team_a_name || 'TBD';
                    const t2Name = m.team2_name || m.team_b_name || 'TBD';
                    const score1 = m.team1_score ?? m.score_a ?? 0;
                    const score2 = m.team2_score ?? m.score_b ?? 0;
                    const isCompleted = m.status === 'COMPLETED';
                    const isLive = m.status === 'LIVE' || m.status === 'IN_PROGRESS';

                    return `
                        <div class="glass-panel match-card-hover" style="padding: 1.25rem 1.5rem; display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 1rem;">
                            <div style="display: flex; align-items: center; gap: 1.5rem; flex: 1; min-width: 280px;">
                                <div style="text-align: right; flex: 1;">
                                    <div style="font-weight: 800; font-size: 1.15rem; color: #fff;">${this.escapeHtml(t1Name)}</div>
                                    <div style="font-size: 1.6rem; font-weight: 900; color: var(--accent-cyan); margin-top: 0.15rem;">${score1}</div>
                                </div>
                                <div style="font-weight: 900; font-size: 1.2rem; color: var(--text-muted); padding: 0 0.5rem; text-align: center;">
                                    VS
                                </div>
                                <div style="text-align: left; flex: 1;">
                                    <div style="font-weight: 800; font-size: 1.15rem; color: #fff;">${this.escapeHtml(t2Name)}</div>
                                    <div style="font-size: 1.6rem; font-weight: 900; color: var(--accent-gold); margin-top: 0.15rem;">${score2}</div>
                                </div>
                            </div>

                            <div style="text-align: right; border-left: 1px solid var(--border-card); padding-left: 1.5rem; min-width: 180px;">
                                <span class="badge ${isLive ? 'badge-live' : (isCompleted ? 'badge-final' : 'badge-upcoming')}">
                                    ${isLive ? '🔴 LIVE' : (isCompleted ? '🏆 COMPLETED' : m.status || 'SCHEDULED')}
                                </span>
                                <div style="font-size: 0.85rem; font-weight: 700; color: #fff; margin-top: 0.4rem;">
                                    🏆 ${this.escapeHtml(m.tournament_name || 'GEN Esports')}
                                </div>
                                <div style="font-size: 0.78rem; color: var(--accent-cyan); margin-top: 0.15rem; font-weight: 600;">
                                    ${this.escapeHtml(m.stage_name || 'Round 1')}
                                </div>
                                ${m.scheduled_time ? `<div style="font-size: 0.75rem; color: var(--text-muted); margin-top: 0.25rem;">📅 ${this.escapeHtml(m.scheduled_time)}</div>` : ''}
                            </div>
                        </div>
                    `;
                }).join('')}
            </div>
        `;
    },

    // RENDER BRACKETS VIEW
    async renderBracketsView() {
        const container = document.getElementById('app-content');
        if (!container) return;

        let tournaments = [];
        try {
            tournaments = await Api.getTournaments();
        } catch (e) {
            console.warn('Error fetching tournaments for bracket:', e);
        }

        const activeSlug = this.activeTournamentSlug || (tournaments[0] ? (tournaments[0].slug || tournaments[0].tournament_id) : '');
        let bracketData = null;
        if (activeSlug) {
            try {
                bracketData = await Api.getTournamentBracket(activeSlug);
            } catch (e) {
                console.warn('Error fetching bracket:', e);
            }
        }

        const hasBracket = bracketData && (
            (bracketData.has_bracket && bracketData.rounds && bracketData.rounds.length > 0) ||
            (Array.isArray(bracketData) && bracketData.length > 0) ||
            (bracketData.rounds && bracketData.rounds.length > 0)
        );

        container.innerHTML = `
            <div style="margin-bottom: 2rem; display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 1rem;">
                <div>
                    <div class="hero-badge">🌳 TOURNAMENT BRACKET</div>
                    <h1 style="font-family: var(--font-heading); font-size: 2.4rem; margin-top: 0.25rem;">
                        LIVE BRACKET <span class="gradient-text">TREE</span>
                    </h1>
                </div>

                ${tournaments.length > 0 ? `
                    <select onchange="App.changeBracketTournament(this.value)" class="form-select" style="max-width: 300px; background: rgba(0,0,0,0.4);">
                        ${tournaments.map(t => `<option value="${t.slug || t.tournament_id}" ${t.slug === activeSlug || String(t.tournament_id) === String(activeSlug) ? 'selected' : ''}>🏆 ${this.escapeHtml(t.title)}</option>`).join('')}
                    </select>
                ` : ''}
            </div>

            ${!hasBracket ? `
                <div class="glass-panel" style="padding: 4rem 2rem; text-align: center;">
                    <div style="font-size: 3.5rem; margin-bottom: 1rem;">🌳</div>
                    <h3 style="font-family: var(--font-heading); font-size: 1.6rem;">Bracket Tree Not Generated Yet</h3>
                    <p style="color: var(--text-secondary); margin-top: 0.5rem;">
                        The tournament organizer will generate the single/double elimination bracket once registration closes.
                    </p>
                </div>
            ` : `
                <div class="glass-panel" style="padding: 2rem; overflow-x: auto;">
                    <div style="display: flex; gap: 3rem; min-width: 800px; justify-content: space-around;">
                        ${this.buildBracketTreeHtml(bracketData)}
                    </div>
                </div>
            `}
        `;
    },

    buildBracketTreeHtml(bracketData) {
        if (!bracketData) return '';
        
        let roundsList = [];
        if (bracketData.rounds && Array.isArray(bracketData.rounds)) {
            roundsList = bracketData.rounds;
        } else if (Array.isArray(bracketData)) {
            const grouped = {};
            bracketData.forEach(m => {
                const rName = m.stage_name || `Round ${m.round_number || 1}`;
                if (!grouped[rName]) grouped[rName] = [];
                grouped[rName].push(m);
            });
            roundsList = Object.keys(grouped).map(rName => ({ round_name: rName, matches: grouped[rName] }));
        }

        return roundsList.map(r => `
            <div style="flex: 1; display: flex; flex-direction: column; justify-content: space-around;">
                <h4 style="font-family: var(--font-heading); font-size: 1.1rem; text-align: center; margin-bottom: 1.5rem; color: var(--accent-cyan); border-bottom: 1px solid var(--border-card); padding-bottom: 0.5rem;">${this.escapeHtml(r.round_name || `Round ${r.round_number}`)}</h4>
                <div style="display: flex; flex-direction: column; gap: 1.5rem;">
                    ${(r.matches || []).map(m => `
                        <div style="background: rgba(0,0,0,0.5); border: 1px solid var(--border-card); border-radius: var(--radius-sm); padding: 0.75rem;">
                            <div style="display: flex; justify-content: space-between; font-size: 0.85rem; font-weight: 700; margin-bottom: 0.35rem; color: ${m.winner_id && m.winner_id === m.team1_id ? 'var(--accent-cyan)' : '#fff'};">
                                <span>🛡️ ${this.escapeHtml(m.team1_name || m.team_a_name || 'TBD')}</span>
                                <span>${m.team1_score ?? m.score_a ?? 0}</span>
                            </div>
                            <div style="display: flex; justify-content: space-between; font-size: 0.85rem; font-weight: 700; color: ${m.winner_id && m.winner_id === m.team2_id ? 'var(--accent-cyan)' : '#fff'};">
                                <span>🛡️ ${this.escapeHtml(m.team2_name || m.team_b_name || 'TBD')}</span>
                                <span>${m.team2_score ?? m.score_b ?? 0}</span>
                            </div>
                        </div>
                    `).join('')}
                </div>
            </div>
        `).join('');
    },

    changeBracketTournament(slug) {
        this.activeTournamentSlug = slug;
        this.renderBracketsView();
    },

    // RENDER LEADERBOARDS VIEW
    async renderLeaderboardsView() {
        const container = document.getElementById('app-content');
        if (!container) return;

        let leaderboard = [];
        try {
            leaderboard = await Api.getLeaderboard();
        } catch (e) {
            console.warn('Error fetching leaderboard:', e);
        }

        container.innerHTML = `
            <div style="margin-bottom: 2.5rem;">
                <div class="hero-badge">🥇 STANDINGS & RANKINGS</div>
                <h1 style="font-family: var(--font-heading); font-size: 2.4rem; margin-top: 0.25rem;">
                    GLOBAL ESPORTS <span class="gradient-text">LEADERBOARD</span>
                </h1>
                <p style="color: var(--text-secondary); font-size: 0.95rem; margin-top: 0.5rem;">
                    Top performing teams ranked by tournament wins, series points, and match record.
                </p>
            </div>

            <div class="data-table-wrapper glass-panel">
                <table class="data-table">
                    <thead>
                        <tr>
                            <th>Rank</th>
                            <th>Team</th>
                            <th>Matches Played</th>
                            <th>Wins</th>
                            <th>Losses</th>
                            <th>Win Rate</th>
                            <th>Total Points</th>
                        </tr>
                    </thead>
                    <tbody>
                        ${leaderboard.length === 0 ? `
                            <tr>
                                <td colspan="7" style="text-align: center; color: var(--text-muted); padding: 3rem;">
                                    No leaderboard standings calculated yet. Complete tournament matches to earn points!
                                </td>
                            </tr>
                        ` : leaderboard.map((row, idx) => `
                            <tr>
                                <td>
                                    <span style="font-weight: 900; font-size: 1.1rem; color: ${idx === 0 ? 'var(--accent-gold)' : (idx === 1 ? '#c0c0c0' : (idx === 2 ? '#cd7f32' : 'var(--text-muted)'))}">
                                        #${idx + 1}
                                    </span>
                                </td>
                                <td>
                                    <div style="display: flex; align-items: center; gap: 0.75rem;">
                                        <img src="${this.escapeHtml(row.logo_url || TEAM_PLACEHOLDER_LOGO)}" onerror="App.handleImgError(this, '${TEAM_PLACEHOLDER_LOGO}')" style="width: 32px; height: 32px; border-radius: 6px; object-fit: cover;">
                                        <strong style="color: #fff; font-size: 1rem;">${this.escapeHtml(row.team_name)}</strong>
                                    </div>
                                </td>
                                <td>${row.matches_played}</td>
                                <td><span style="color: var(--accent-green); font-weight: 700;">${row.wins}</span></td>
                                <td><span style="color: var(--accent-red); font-weight: 700;">${row.losses}</span></td>
                                <td><strong>${row.win_rate || '0%'}</strong></td>
                                <td><strong style="color: var(--accent-gold); font-size: 1.1rem;">${row.points} PTS</strong></td>
                            </tr>
                        `).join('')}
                    </tbody>
                </table>
            </div>
        `;
    },

    changeLeaderboardTournament(slug) {
        this.renderLeaderboardsView();
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
                        WELCOME BACK, <span class="gradient-text">${profile ? this.escapeHtml(profile.display_name) : 'COMPETITOR'}</span>
                    </h1>
                </div>
                <button onclick="App.logoutUserDashboard()" class="btn btn-secondary" style="font-size: 0.85rem;">
                    🔒 Switch Account
                </button>
            </div>

            <div class="stats-banner glass-panel" style="margin-bottom: 2.5rem;">
                <div class="stat-box"><div class="stat-val" style="color: var(--accent-cyan);">${profile ? this.escapeHtml(profile.public_id) : 'GEN-P-000000'}</div><div class="stat-lbl">Public ID</div></div>
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
                                    <span>🛡️ ${this.escapeHtml(r.team_name)}</span>
                                    <span class="badge ${r.status === 'APPROVED' ? 'badge-open' : 'badge-closed'}">${r.status}</span>
                                </div>
                                <div style="font-size: 0.8rem; color: var(--text-secondary);">🏆 ${this.escapeHtml(r.tournament_name)} • Code: <code>${this.escapeHtml(r.registration_code || r.ticket_id)}</code></div>
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
                                <div style="font-size: 0.8rem; color: var(--text-secondary);">📂 Category: <code>${this.escapeHtml(c.ticket_type)}</code> • Priority: <code>${this.escapeHtml(c.priority)}</code></div>
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
        const key = input ? input.value.trim() : '';
        if (key) {
            this.adminApiKey = key;
            sessionStorage.setItem('gen_admin_api_key', key);
            this.renderAdminView();
        }
    },

    showToast(message, type = 'info') {
        let container = document.getElementById('toast-container');
        if (!container) {
            container = document.createElement('div');
            container.id = 'toast-container';
            container.style.cssText = 'position: fixed; bottom: 2rem; right: 2rem; z-index: 10000; display: flex; flex-direction: column; gap: 0.5rem; pointer-events: none;';
            document.body.appendChild(container);
        }
        const toast = document.createElement('div');
        toast.className = `toast toast-${type} glass-panel`;
        const bgColor = type === 'success' ? 'rgba(0, 240, 255, 0.18)' : (type === 'error' ? 'rgba(255, 0, 85, 0.22)' : 'rgba(255, 255, 255, 0.12)');
        const borderColor = type === 'success' ? 'var(--accent-cyan)' : (type === 'error' ? 'var(--accent-red)' : 'var(--border-card)');
        const textColor = type === 'error' ? '#ff4d6d' : (type === 'success' ? '#00f0ff' : '#fff');
        toast.style.cssText = `padding: 0.9rem 1.35rem; border-radius: var(--radius-sm); background: ${bgColor}; border: 1px solid ${borderColor}; color: ${textColor}; font-weight: 700; font-size: 0.92rem; box-shadow: 0 8px 30px rgba(0,0,0,0.6); backdrop-filter: blur(12px); transition: all 0.3s ease; pointer-events: auto;`;
        toast.innerHTML = message;
        container.appendChild(toast);
        setTimeout(() => {
            toast.style.opacity = '0';
            toast.style.transform = 'translateY(10px)';
            setTimeout(() => toast.remove(), 300);
        }, 3500);
    },

    async refreshAdminData(toastMsg = '') {
        if (toastMsg) {
            this.showToast(toastMsg, 'success');
        }
        await this.renderAdminView();
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

                <h3 style="font-family: var(--font-heading); font-size: 1.4rem; margin-bottom: 1rem; color: #fff;">📋 Pending Team Registrations (${pendingRegs.length})</h3>
                <div style="display: grid; grid-template-columns: repeat(auto-fill, minmax(340px, 1fr)); gap: 1.5rem;">
                    ${pendingRegs.length === 0 ? `
                        <div class="glass-panel" style="padding: 3rem; text-align: center; grid-column: 1 / -1;">
                            <div style="font-size: 2.5rem; margin-bottom: 0.5rem;">✅</div>
                            <h4>No Pending Registrations</h4>
                            <p style="color: var(--text-muted); margin-top: 0.25rem;">All team registration tickets have been reviewed.</p>
                        </div>
                    ` : pendingRegs.map(r => `
                        <div class="glass-panel" style="padding: 1.5rem;" id="reg-card-${r.ticket_id}">
                            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.75rem;">
                                <strong style="font-size: 1.15rem; color: var(--accent-cyan);">${this.escapeHtml(r.team_name || 'Team')}</strong>
                                <span class="badge badge-draft">PENDING</span>
                            </div>
                            <div style="font-size: 0.88rem; color: var(--text-secondary); margin-bottom: 1.25rem; line-height: 1.6;">
                                🏆 <strong>Tournament:</strong> ${this.escapeHtml(r.tournament_name || 'N/A')}<br>
                                👑 <strong>Captain:</strong> ${this.escapeHtml(r.captain_name || 'N/A')} (<span style="color: var(--accent-gold);">${this.escapeHtml(r.captain_phone || '')}</span>)<br>
                                🆔 <strong>Registration Code:</strong> <code>${this.escapeHtml(r.registration_code || r.ticket_id)}</code>
                            </div>
                            <div style="display: flex; gap: 0.75rem;">
                                <button onclick="App.approveTeamAdmin(${r.ticket_id})" class="btn btn-primary" style="flex: 1; padding: 0.6rem; font-weight: 700;">
                                    ✓ Approve
                                </button>
                                <button onclick="App.showRejectModal(${r.ticket_id})" class="btn btn-danger" style="flex: 1; padding: 0.6rem; background: var(--accent-red); color: #fff; font-weight: 700;">
                                    ✕ Reject
                                </button>
                            </div>
                        </div>
                    `).join('')}
                </div>
            `;
        } else if (this.adminTab === 'tournaments') {
            container.innerHTML = `
                <div class="glass-panel" style="padding: 2rem; margin-bottom: 2.5rem;">
                    <h3 style="font-family: var(--font-heading); font-size: 1.4rem; margin-bottom: 1.25rem;">➕ Create New Tournament</h3>
                    <div id="t-form-error" class="form-error-msg" style="display: none; color: #ff6b6b; background: rgba(255,107,107,0.1); border: 1px solid rgba(255,107,107,0.3); padding: 0.75rem 1rem; border-radius: var(--radius-sm); margin-bottom: 1rem; font-size: 0.9rem; font-weight: 600;"></div>
                    <form onsubmit="App.handleCreateTournament(event)" novalidate>
                        <div class="form-grid">
                            <div class="form-group"><label>Tournament Name</label><input type="text" id="t-title" class="form-input" placeholder="e.g. GEN Valorant Masters" required></div>
                            <div class="form-group"><label>Game</label><input type="text" id="t-game" class="form-input" placeholder="VALORANT / PUBG MOBILE / CS2" required></div>
                            <div class="form-group"><label>Prize Pool</label><input type="text" id="t-prize" class="form-input" placeholder="৳500 BDT / $500 USD"></div>
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

                <h3 style="font-family: var(--font-heading); font-size: 1.4rem; margin-bottom: 1rem; color: #fff;">🏆 Active Database Tournaments</h3>
                <div class="data-table-wrapper glass-panel">
                    <table class="data-table">
                        <thead>
                            <tr><th>ID</th><th>Name</th><th>Game</th><th>Reg Status</th><th>Main Status</th><th>Approved Teams</th><th>Quick Actions</th></tr>
                        </thead>
                        <tbody>
                            ${tournaments.map(t => {
                                const approved = t.current_approved_team_count || 0;
                                const maxT = t.max_teams || 16;
                                const isFull = approved >= maxT || t.registration_status === 'FULL';
                                return `
                                    <tr>
                                        <td>#${t.tournament_id}</td>
                                        <td><strong>${this.escapeHtml(t.title)}</strong></td>
                                        <td><span style="color: var(--accent-cyan); font-weight: 700;">${this.escapeHtml(t.game_type)}</span></td>
                                        <td><span class="badge ${isFull ? 'badge-closed' : (t.registration_status === 'OPEN' ? 'badge-open' : 'badge-closed')}">${isFull ? 'FULL' : t.registration_status}</span></td>
                                        <td><span class="badge badge-ongoing">${t.status}</span></td>
                                        <td><strong style="color: ${approved >= 2 ? 'var(--accent-green)' : 'var(--text-primary)'};">${approved} / ${maxT} Teams</strong></td>
                                        <td style="display: flex; gap: 0.4rem; flex-wrap: wrap; align-items: center;">
                                            <button onclick="App.handleOpenRegistration(${t.tournament_id})" class="btn btn-secondary" style="padding: 0.3rem 0.5rem; font-size: 0.75rem;" title="Open Registration">🟢 Open</button>
                                            <button onclick="App.handleCloseRegistration(${t.tournament_id})" class="btn btn-secondary" style="padding: 0.3rem 0.5rem; font-size: 0.75rem;" title="Close Registration">🔴 Close</button>
                                            <select onchange="App.handleSetStatus(${t.tournament_id}, this.value)" class="form-select" style="padding: 0.25rem; font-size: 0.75rem; width: auto;">
                                                <option value="" disabled selected>Status...</option>
                                                <option value="DRAFT">DRAFT</option>
                                                <option value="REGISTRATION_OPEN">REG OPEN</option>
                                                <option value="REGISTRATION_CLOSED">REG CLOSED</option>
                                                <option value="ONGOING">ONGOING</option>
                                                <option value="COMPLETED">COMPLETED</option>
                                                <option value="CANCELLED">CANCELLED</option>
                                            </select>
                                            <button onclick="App.handleGenerateBracket('${t.tournament_id}')" class="btn btn-primary" style="padding: 0.3rem 0.6rem; font-size: 0.75rem;" title="Generate or Regenerate Bracket">🏆 Bracket</button>
                                            <button onclick="App.showCancelModal(${t.tournament_id})" class="btn btn-danger" style="padding: 0.3rem 0.5rem; font-size: 0.75rem; background: var(--accent-red); color:#fff;" title="Cancel Tournament">❌ Cancel</button>
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
                <div style="margin-bottom: 1.5rem; display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 1rem;">
                    <div>
                        <h3 style="font-family: var(--font-heading); font-size: 1.6rem; color: #fff;">⚔️ Admin Match Manager</h3>
                        <p style="color: var(--text-secondary); font-size: 0.9rem;">Schedule matches, manage lobbies, enter match scores & advance winners automatically.</p>
                    </div>
                </div>

                <div class="data-table-wrapper glass-panel">
                    <table class="data-table">
                        <thead>
                            <tr><th>Match ID</th><th>Tournament</th><th>Stage</th><th>Teams & Scores</th><th>Schedule & Lobby</th><th>Status</th><th>Actions</th></tr>
                        </thead>
                        <tbody>
                            ${matches.length === 0 ? `
                                <tr><td colspan="7" style="text-align: center; color: var(--text-muted); padding: 3rem;">No matches scheduled yet. Go to Tournament Manager and click 🏆 Bracket to generate matches.</td></tr>
                            ` : matches.map(m => `
                                <tr>
                                    <td><strong>#M-${m.match_id}</strong></td>
                                    <td>${this.escapeHtml(m.tournament_name || 'N/A')}</td>
                                    <td><span style="color: var(--accent-cyan); font-weight: 700;">${this.escapeHtml(m.stage_name || 'Round')}</span></td>
                                    <td>
                                        <div style="display: flex; align-items: center; gap: 0.5rem;">
                                            <span>🛡️ <strong>${this.escapeHtml(m.team1_name || 'TBD')}</strong> (${m.team1_score ?? 0})</span>
                                            <span style="color: var(--text-muted);">vs</span>
                                            <span>🛡️ <strong>${this.escapeHtml(m.team2_name || 'TBD')}</strong> (${m.team2_score ?? 0})</span>
                                        </div>
                                    </td>
                                    <td style="font-size: 0.8rem; color: var(--text-secondary);">
                                        📅 ${m.scheduled_time || 'Not Scheduled'}<br>
                                        🎮 ${this.escapeHtml(m.lobby_info || 'Lobby TBD')}
                                    </td>
                                    <td>
                                        <span class="badge ${m.status === 'COMPLETED' ? 'badge-draft' : 'badge-open'}">${m.status || 'SCHEDULED'}</span>
                                    </td>
                                    <td>
                                        <div style="display: flex; gap: 0.4rem; flex-wrap: wrap;">
                                            <button onclick="App.showScheduleModal(${m.match_id}, '${this.escapeHtml(m.scheduled_time || '')}', '${this.escapeHtml(m.lobby_info || '')}')" class="btn btn-secondary" style="padding: 0.3rem 0.55rem; font-size: 0.75rem;">📅 Schedule</button>
                                            <button onclick="App.showScoreInputModal(${m.match_id}, '${this.escapeHtml(m.team1_name || 'Team 1')}', '${this.escapeHtml(m.team2_name || 'Team 2')}', ${m.team1_score ?? 0}, ${m.team2_score ?? 0})" class="btn btn-primary" style="padding: 0.3rem 0.55rem; font-size: 0.75rem;">✏️ Enter Score</button>
                                        </div>
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
                <h3 style="font-family: var(--font-heading); font-size: 1.4rem; margin-bottom: 1rem; color: #fff;">📜 Admin Action Audit Logs (${logs.length})</h3>
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
                                    <td><strong style="color: var(--accent-gold);">${this.escapeHtml(l.admin_id)}</strong></td>
                                    <td><span class="badge badge-ongoing">${this.escapeHtml(l.action)}</span></td>
                                    <td>${l.tournament_name || (l.tournament_id ? `#${l.tournament_id}` : '-')}</td>
                                    <td style="font-size: 0.85rem; color: var(--text-secondary);">${this.escapeHtml(l.details || '-')}</td>
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
            this.showToast('✅ Registration approved successfully!', 'success');
            await this.refreshAdminData();
        } catch (err) {
            this.showToast('✕ Error approving registration: ' + err.message, 'error');
        }
    },

    showRejectModal(ticketId) {
        this.showModal(`
            <h3 style="font-family: var(--font-heading); font-size: 1.5rem; margin-bottom: 1rem; color: var(--accent-red);">❌ Reject Team Registration</h3>
            <p style="color: var(--text-secondary); margin-bottom: 1rem; font-size: 0.9rem;">Provide a reason for rejecting ticket #${ticketId}:</p>
            <form onsubmit="App.handleRejectSubmit(event, ${ticketId})">
                <div class="form-group" style="margin-bottom: 1.5rem;">
                    <label>Rejection Reason</label>
                    <input type="text" id="reject-reason-input" class="form-input" placeholder="e.g. Invalid payment transaction ID or incorrect team tag" required>
                </div>
                <div style="display: flex; gap: 1rem; justify-content: flex-end;">
                    <button type="button" onclick="App.hideModal()" class="btn btn-secondary">Cancel</button>
                    <button type="submit" class="btn btn-danger" style="background: var(--accent-red); color: #fff;">Confirm Rejection</button>
                </div>
            </form>
        `);
    },

    async handleRejectSubmit(e, ticketId) {
        e.preventDefault();
        const reason = document.getElementById('reject-reason-input').value;
        try {
            await Api.rejectRegistration(this.adminApiKey, ticketId, reason);
            this.hideModal();
            this.showToast('Registration rejected.', 'info');
            await this.refreshAdminData();
        } catch (err) {
            this.showToast('✕ Error rejecting registration: ' + err.message, 'error');
        }
    },

    showFormError(msg) {
        const errEl = document.getElementById('t-form-error');
        if (errEl) {
            errEl.textContent = '⚠️ ' + msg;
            errEl.style.display = 'block';
            errEl.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
        } else {
            this.showToast('⚠️ ' + msg, 'error');
        }
    },

    async handleCreateTournament(e) {
        e.preventDefault();
        const errEl = document.getElementById('t-form-error');
        if (errEl) {
            errEl.style.display = 'none';
            errEl.textContent = '';
        }

        const title = (document.getElementById('t-title').value || '').trim();
        const game_type = (document.getElementById('t-game').value || '').trim();
        const prize_info = (document.getElementById('t-prize').value || '').trim();
        const max_teams = parseInt(document.getElementById('t-max').value || '16', 10);
        const format = document.getElementById('t-format').value;
        const status = document.getElementById('t-status').value;

        if (!title || !game_type) {
            this.showFormError('Tournament Name and Game are required.');
            return;
        }

        const regStartInput = document.getElementById('t-reg-start');
        const regDeadlineInput = document.getElementById('t-reg-deadline');
        const tournStartInput = document.getElementById('t-start');
        const tournEndInput = document.getElementById('t-end');

        const regStartRaw = regStartInput ? regStartInput.value : '';
        const regDeadlineRaw = regDeadlineInput ? regDeadlineInput.value : '';
        const tournStartRaw = tournStartInput ? tournStartInput.value : '';
        const tournEndRaw = tournEndInput ? tournEndInput.value : '';

        const registration_start = toDateTimeLocalValue(regStartRaw);
        const registration_deadline = toDateTimeLocalValue(regDeadlineRaw);
        const tournament_start = toDateTimeLocalValue(tournStartRaw);
        const tournament_end = toDateTimeLocalValue(tournEndRaw);

        if (regStartRaw && !registration_start) {
            this.showFormError('Please enter a valid Registration Start date and time.');
            return;
        }
        if (regDeadlineRaw && !registration_deadline) {
            this.showFormError('Please enter a valid Registration Deadline date and time.');
            return;
        }
        if (tournStartRaw && !tournament_start) {
            this.showFormError('Please enter a valid Tournament Start date and time.');
            return;
        }
        if (tournEndRaw && !tournament_end) {
            this.showFormError('Please enter a valid Tournament End date and time.');
            return;
        }

        const dRegStart = registration_start ? new Date(registration_start) : null;
        const dRegDead = registration_deadline ? new Date(registration_deadline) : null;
        const dTournStart = tournament_start ? new Date(tournament_start) : null;
        const dTournEnd = tournament_end ? new Date(tournament_end) : null;

        if (dRegStart && dRegDead && dRegStart.getTime() >= dRegDead.getTime()) {
            this.showFormError('Registration Start must be earlier than Registration Deadline.');
            return;
        }
        if (dRegDead && dTournStart && dRegDead.getTime() > dTournStart.getTime()) {
            this.showFormError('Registration Deadline must be on or before Tournament Start.');
            return;
        }
        if (dTournStart && dTournEnd && dTournStart.getTime() >= dTournEnd.getTime()) {
            this.showFormError('Tournament Start must be earlier than Tournament End.');
            return;
        }

        const description = document.getElementById('t-desc').value;
        const rules_text = document.getElementById('t-rules').value;
        const registration_status = status === 'REGISTRATION_OPEN' ? 'OPEN' : 'CLOSED';

        try {
            await Api.createTournament(this.adminApiKey, {
                title, game_type, prize_info, max_teams, format, status,
                registration_status, registration_start, registration_deadline,
                tournament_start, tournament_end, description, rules_text
            });
            this.showToast('🏆 Tournament created successfully!', 'success');
            await this.refreshAdminData();
        } catch (err) {
            this.showFormError('Failed to create tournament: ' + err.message);
        }
    },

    async handleOpenRegistration(id) {
        try {
            await Api.openRegistration(this.adminApiKey, id);
            this.showToast('🟢 Registration opened!', 'success');
            await this.refreshAdminData();
        } catch (err) {
            this.showToast('✕ Error opening registration: ' + err.message, 'error');
        }
    },

    async handleCloseRegistration(id) {
        try {
            await Api.closeRegistration(this.adminApiKey, id);
            this.showToast('🔴 Registration closed.', 'info');
            await this.refreshAdminData();
        } catch (err) {
            this.showToast('✕ Error closing registration: ' + err.message, 'error');
        }
    },

    async handleSetStatus(id, newStatus) {
        if (!newStatus) return;
        try {
            await Api.setTournamentStatus(this.adminApiKey, id, newStatus);
            this.showToast(`Tournament status updated to ${newStatus}.`, 'success');
            await this.refreshAdminData();
        } catch (err) {
            this.showToast('✕ Error changing status: ' + err.message, 'error');
        }
    },

    showCancelModal(id) {
        this.showModal(`
            <h3 style="font-family: var(--font-heading); font-size: 1.5rem; margin-bottom: 1rem; color: var(--accent-red);">⚠️ Cancel Tournament</h3>
            <p style="color: var(--text-secondary); margin-bottom: 1.5rem;">Are you sure you want to cancel this tournament? Status will update to CANCELLED.</p>
            <div style="display: flex; gap: 1rem; justify-content: flex-end;">
                <button type="button" onclick="App.hideModal()" class="btn btn-secondary">Keep Active</button>
                <button type="button" onclick="App.executeCancelTournament(${id})" class="btn btn-danger" style="background: var(--accent-red); color: #fff;">Yes, Cancel Tournament</button>
            </div>
        `);
    },

    async executeCancelTournament(id) {
        try {
            await Api.cancelTournament(this.adminApiKey, id);
            this.hideModal();
            this.showToast('Tournament cancelled.', 'info');
            await this.refreshAdminData();
        } catch (err) {
            this.showToast('✕ Error cancelling tournament: ' + err.message, 'error');
        }
    },

    async handleGenerateBracket(id) {
        try {
            await Api.generateBracket(this.adminApiKey, id);
            this.showToast('🏆 Tournament bracket generated successfully!', 'success');
            this.adminTab = 'matches';
            await this.refreshAdminData();
        } catch (err) {
            this.showToast('✕ Error generating bracket: ' + err.message, 'error');
        }
    },

    showScheduleModal(matchId, currentScheduled = '', currentLobby = '') {
        this.showModal(`
            <h3 style="font-family: var(--font-heading); font-size: 1.5rem; margin-bottom: 1rem;">📅 Schedule Match & Lobby Info</h3>
            <form onsubmit="App.handleSaveSchedule(event, ${matchId})">
                <div class="form-grid" style="margin-bottom: 1rem;">
                    <div class="form-group">
                        <label>Scheduled Time (Asia/Dhaka)</label>
                        <input type="text" id="m-schedule-time" class="form-input" placeholder="e.g. 15 Aug 2026, 8:00 PM (Asia/Dhaka)" value="${currentScheduled}">
                    </div>
                    <div class="form-group">
                        <label>Map / Mode</label>
                        <input type="text" id="m-map" class="form-input" placeholder="e.g. Haven / Ascent / Erangel">
                    </div>
                    <div class="form-group">
                        <label>Lobby Name / ID</label>
                        <input type="text" id="m-lobby-name" class="form-input" placeholder="e.g. GEN-MATCH-${matchId}" value="${currentLobby}">
                    </div>
                    <div class="form-group">
                        <label>Lobby Password / Passcode</label>
                        <input type="text" id="m-lobby-pass" class="form-input" placeholder="e.g. 1234">
                    </div>
                </div>
                <button type="submit" class="btn btn-primary" style="width: 100%; padding: 0.75rem;">💾 Save Schedule & Lobby Info</button>
            </form>
        `);
    },

    async handleSaveSchedule(e, matchId) {
        e.preventDefault();
        const scheduled_at = document.getElementById('m-schedule-time').value;
        const map_name = document.getElementById('m-map').value;
        const lobby_name = document.getElementById('m-lobby-name').value;
        const lobby_password = document.getElementById('m-lobby-pass').value;

        try {
            await Api.scheduleMatch(this.adminApiKey, matchId, {
                scheduled_at,
                map: map_name,
                lobby_name,
                lobby_password
            });
            this.hideModal();
            this.showToast('📅 Match schedule & lobby details updated!', 'success');
            await this.refreshAdminData();
        } catch (err) {
            this.showToast('✕ Failed to schedule match: ' + err.message, 'error');
        }
    },

    showScoreInputModal(matchId, t1Name, t2Name, currentScore1 = 0, currentScore2 = 0) {
        this.showModal(`
            <div style="max-width: 500px; margin: 0 auto;">
                <h3 style="font-family: var(--font-heading); font-size: 1.6rem; margin-bottom: 0.5rem; text-align: center; color: #fff;">⚔️ ENTER MATCH RESULT</h3>
                <p style="color: var(--text-secondary); font-size: 0.9rem; text-align: center; margin-bottom: 1.5rem;">
                    Match #${matchId} • Submit scores to determine winner & auto-advance bracket.
                </p>
                <form onsubmit="App.handleSaveMatchScore(event, ${matchId})">
                    <div style="display: grid; grid-template-columns: 1fr auto 1fr; gap: 1rem; align-items: center; background: rgba(0,0,0,0.3); border: 1px solid var(--border-card); padding: 1.5rem; border-radius: var(--radius-md); margin-bottom: 1.5rem;">
                        <div style="text-align: center;">
                            <div style="font-weight: 800; font-size: 1.1rem; color: var(--accent-cyan); margin-bottom: 0.5rem;">${this.escapeHtml(t1Name)}</div>
                            <input type="number" id="m-score1" class="form-input" value="${currentScore1}" min="0" style="text-align: center; font-weight: 800; font-size: 1.4rem;" required>
                        </div>
                        <div style="font-size: 1.5rem; font-weight: 800; color: var(--text-muted);">VS</div>
                        <div style="text-align: center;">
                            <div style="font-weight: 800; font-size: 1.1rem; color: var(--accent-gold); margin-bottom: 0.5rem;">${this.escapeHtml(t2Name)}</div>
                            <input type="number" id="m-score2" class="form-input" value="${currentScore2}" min="0" style="text-align: center; font-weight: 800; font-size: 1.4rem;" required>
                        </div>
                    </div>
                    <button type="submit" class="btn btn-primary" style="width: 100%; padding: 0.85rem; font-size: 1rem; font-weight: 700;">
                        🏆 SUBMIT RESULT & ADVANCE WINNER
                    </button>
                </form>
            </div>
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
            this.showToast('🏆 Match score recorded & winner advanced in bracket!', 'success');
            await this.refreshAdminData();
        } catch (err) {
            this.showToast('✕ Error recording match score: ' + err.message, 'error');
        }
    }
};

window.App = App;
