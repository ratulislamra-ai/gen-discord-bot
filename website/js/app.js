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
    if (!Number.isNaN(date.getTime())) {
        const pad = n => String(n).padStart(2, '0');
        return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`;
    }

    try {
        const match = String(value).match(/(\d{1,2})\s+([A-Za-z]{3})\s+(\d{4}),?\s+(\d{1,2}):(\d{2})\s*(AM|PM)/i);
        if (match) {
            const day = parseInt(match[1], 10);
            const monthStr = match[2];
            const year = parseInt(match[3], 10);
            let hours = parseInt(match[4], 10);
            const minutes = parseInt(match[5], 10);
            const ampm = match[6].toUpperCase();
            if (ampm === 'PM' && hours < 12) hours += 12;
            if (ampm === 'AM' && hours === 12) hours = 0;

            const monthNames = ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"];
            const monthIdx = monthNames.indexOf(monthStr.toLowerCase());
            if (monthIdx !== -1) {
                const pad = n => String(n).padStart(2, '0');
                return `${year}-${pad(monthIdx + 1)}-${pad(day)}T${pad(hours)}:${pad(minutes)}`;
            }
        }
    } catch (e) {
        console.warn('Date parse notice:', e);
    }
    return '';
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

    formatStageName(stage, roundNum) {
        if (!stage) {
            if (roundNum === 1) return 'Quarter Finals';
            if (roundNum === 2) return 'Semi Finals';
            if (roundNum === 3) return 'Grand Final';
            return `Round ${roundNum || 1}`;
        }
        const s = String(stage).trim();
        const lower = s.toLowerCase();
        if (lower === 'round 1' || lower === 'quarterfinals' || lower === 'quarter finals') return 'Quarter Finals';
        if (lower === 'round 2' || lower === 'semifinals' || lower === 'semi finals') return 'Semi Finals';
        if (lower === 'round 3' || lower === 'finals' || lower === 'final' || lower === 'grand final' || lower === 'grand finals') return 'Grand Final';
        return s;
    },

    async init() {
        this.bindEvents();
        window.addEventListener('hashchange', () => this.handleHashRoute());
        try {
            await this.loadConfig();
        } catch (e) {
            console.warn('Config load notice:', e);
        }
        if (window.location.hash) {
            await this.handleHashRoute();
        } else {
            try {
                await this.renderView('home');
            } catch (e) {
                console.error('Failed initial view render:', e);
            }
        }
        this.startAutoRefresh();
    },

    handleHashRoute() {
        const hash = window.location.hash || '';
        if (!hash.startsWith('#')) return;

        const [viewPart, queryPart] = hash.substring(1).split('?');
        const viewName = viewPart.replace(/^\//, '');

        if (['home', 'tournaments', 'teams', 'players', 'matches', 'brackets', 'leaderboards', 'dashboard', 'admin'].includes(viewName)) {
            if (queryPart) {
                const params = new URLSearchParams(queryPart);
                const tourneyParam = params.get('tournament') || params.get('slug');
                if (tourneyParam) {
                    this.activeTournamentSlug = tourneyParam;
                }
            }
            return this.renderView(viewName);
        }
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
            } else if (this.currentView === 'brackets') {
                await this.renderBracketsView();
            }
        } catch (err) {
            console.warn('Silent background refresh notice:', err);
        }
    },

    async loadConfig() {
        try {
            const config = await Api.getConfig();
            let url = (config && config.discord_invite_url) || '';
            if (!url || url.includes('G568r5MFqB') || url.includes('genesports')) {
                url = 'https://discord.gg/c4YuB5GmbS';
            }
            this.discordInviteUrl = url;
        } catch (e) {
            console.warn('Failed to fetch config:', e);
            this.discordInviteUrl = 'https://discord.gg/c4YuB5GmbS';
        }
    },

    openDiscordInvite() {
        const officialUrl = 'https://discord.gg/c4YuB5GmbS';
        let url = (this.discordInviteUrl && this.discordInviteUrl.startsWith('http')) 
            ? this.discordInviteUrl 
            : officialUrl;
        if (url.includes('G568r5MFqB') || url.includes('genesports')) {
            url = officialUrl;
        }
        window.open(url, '_blank', 'noopener,noreferrer');
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
                                    ${this.escapeHtml(this.formatStageName(m.stage_name, m.round_number))}
                                </div>
                                ${m.scheduled_time ? `<div style="font-size: 0.75rem; color: var(--text-muted); margin-top: 0.25rem;">📅 ${this.escapeHtml(m.scheduled_time)}</div>` : ''}
                            </div>
                        </div>
                    `;
                }).join('')}
            </div>
        `;
    },

    // ═══════════════════════════════════════════════════════════
    // RENDER BRACKETS VIEW — Premium World Cup Style
    // ═══════════════════════════════════════════════════════════
    async renderBracketsView() {
        const container = document.getElementById('app-content');
        if (!container) return;

        // Clear match data cache for fresh render
        this._bracketMatchCache = {};

        // Fetch tournament list for selector
        let tournaments = [];
        try {
            tournaments = await Api.getTournaments();
        } catch (e) {
            console.warn('Error fetching tournaments for bracket:', e);
        }

        // Determine active tournament
        const activeSlug = this.activeTournamentSlug || (tournaments[0] ? (tournaments[0].slug || String(tournaments[0].tournament_id)) : '');

        // Fetch bracket data for active tournament
        let bracketData = null;
        if (activeSlug) {
            try {
                bracketData = await Api.getTournamentBracket(activeSlug);
            } catch (e) {
                console.warn('Error fetching bracket:', e);
            }
        }

        // Parse bracket data
        const hasBracket = bracketData && (
            (bracketData.has_bracket && bracketData.rounds && bracketData.rounds.length > 0)
        );
        const tournament = bracketData && bracketData.tournament;
        const rounds = (bracketData && bracketData.rounds) || [];
        const champion = (bracketData && bracketData.champion) || null;

        // ─── Build tournament metadata ───────────────────────────
        const tName = tournament ? (tournament.title || tournament.name || 'Tournament') : 'Tournament';
        const tGame = tournament ? (tournament.game || 'Esports') : 'Esports';
        const tStatus = tournament ? (tournament.status || 'ACTIVE') : 'ACTIVE';
        const tTeams = tournament ? (tournament.registered_teams_count || tournament.max_teams || 0) : 0;
        const numRounds = rounds.length;

        // Status pill color class
        const statusClass = tStatus === 'ONGOING' || tStatus === 'ACTIVE' ? 'green' : (tStatus === 'COMPLETED' ? '' : 'gold');

        // Build round tabs for mobile
        const roundTabsHtml = rounds.map((r, i) => {
            const shortName = (r.round_name || `Round ${r.round_number}`)
                .replace('ROUND OF ', 'RO')
                .replace('QUARTER FINALS', 'QF')
                .replace('SEMI FINALS', 'SF')
                .replace('GRAND FINAL', 'FINAL');
            return `<button class="bracket-tab-btn ${i === 0 ? 'active' : ''}" onclick="App.bracketShowRound(${i})" data-round-idx="${i}" aria-label="Show ${this.escapeHtml(r.round_name || `Round ${r.round_number}`)}">${this.escapeHtml(shortName)}</button>`;
        }).join('');

        // Build main bracket HTML
        const bracketBodyHtml = !hasBracket ? `
            <div style="padding: 4rem 2rem; text-align: center; background: var(--bg-surface); border: 1px solid var(--border-card); border-radius: var(--radius-lg); box-shadow: inset 0 0 40px rgba(0,0,0,0.5);">
                <div style="font-size: 3.5rem; margin-bottom: 1.25rem; opacity: 0.4;">🌳</div>
                <h3 style="font-family: var(--font-heading); font-size: 1.6rem; font-weight: 800; color: var(--text-primary); margin-bottom: 0.75rem;">No Bracket Generated Yet</h3>
                <p style="color: var(--text-secondary); font-size: 0.95rem; max-width: 480px; margin: 0 auto 1rem;">
                    The tournament organizer will generate the bracket once team registration closes.
                </p>
                <div style="display: inline-flex; align-items: center; gap: 0.5rem; background: rgba(0,240,255,0.08); border: 1px solid rgba(0,240,255,0.25); color: var(--accent-cyan); padding: 0.4rem 1rem; border-radius: 20px; font-size: 0.82rem; font-weight: 700;">
                    ⏳ AWAITING BRACKET GENERATION
                </div>
            </div>
        ` : `
            ${rounds.length > 0 ? `
                <div class="bracket-mobile-tabs" id="bracket-mobile-tabs">
                    ${roundTabsHtml}
                </div>
            ` : ''}
            <div class="esports-bracket-viewport">
                <div class="esports-bracket-tree" id="esports-bracket-tree" style="position: relative;">
                    ${this.buildPremiumBracketHtml(rounds)}
                </div>
            </div>
            ${champion ? `
                <div class="champion-banner" style="margin-top: 2rem;">
                    <div style="font-size: 0.8rem; font-weight: 900; letter-spacing: 3px; color: var(--accent-gold); text-transform: uppercase; margin-bottom: 0.5rem;">🏆 Tournament Champion</div>
                    ${champion.logo_url ? `<img src="${this.escapeHtml(champion.logo_url)}" onerror="App.handleImgError(this, '${TEAM_PLACEHOLDER_LOGO}')" class="champion-logo" alt="${this.escapeHtml(champion.name)}">` : `<div class="champion-logo" style="display:flex;align-items:center;justify-content:center;font-size:2rem;">🏆</div>`}
                    <div class="champion-title">${this.escapeHtml(champion.name || 'Champions')}</div>
                </div>
            ` : ''}
        `;

        container.innerHTML = `
            <div class="bracket-page-wrapper">
                <!-- ══ TOURNAMENT HEADER CARD ══════════════════════════ -->
                <div class="bracket-header-card">
                    <div class="bracket-header-top">
                        <div>
                            <div class="bracket-header-title">
                                🏆 TOURNAMENT BRACKET
                            </div>
                            <div class="bracket-meta-pills" style="margin-top: 0.6rem;">
                                <span class="bracket-meta-pill">${this.escapeHtml(tGame)}</span>
                                ${tTeams > 0 ? `<span class="bracket-meta-pill">${tTeams} TEAMS</span>` : ''}
                                ${numRounds > 0 ? `<span class="bracket-meta-pill">${numRounds} ROUND${numRounds !== 1 ? 'S' : ''}</span>` : ''}
                                ${hasBracket ? `<span class="bracket-meta-pill ${statusClass}">● ${this.escapeHtml(tStatus)}</span>` : ''}
                                ${champion ? `<span class="bracket-meta-pill gold">🏆 CHAMPION CROWNED</span>` : ''}
                            </div>
                            <div style="font-family: var(--font-heading); font-size: 1.4rem; font-weight: 800; color: #fff; margin-top: 0.5rem; letter-spacing: -0.3px;">${this.escapeHtml(tName)}</div>
                        </div>

                        ${tournaments.length > 0 ? `
                            <div>
                                <div style="font-size: 0.75rem; font-weight: 700; color: var(--text-muted); text-transform: uppercase; letter-spacing: 1px; margin-bottom: 0.35rem;">Tournament</div>
                                <select onchange="App.changeBracketTournament(this.value)" class="form-select" style="min-width: 240px; background: rgba(0,0,0,0.5);" aria-label="Select Tournament">
                                    ${tournaments.map(t => `<option value="${this.escapeHtml(t.slug || String(t.tournament_id))}" ${(t.slug === activeSlug || String(t.tournament_id) === String(activeSlug)) ? 'selected' : ''}>🏆 ${this.escapeHtml(t.title || t.name)}</option>`).join('')}
                                </select>
                            </div>
                        ` : ''}
                    </div>

                    <!-- Legend bar -->
                    <div class="bracket-controls-bar">
                        <div class="bracket-legend" role="list" aria-label="Match status legend">
                            <div class="legend-item" role="listitem"><span class="legend-dot live"></span> Live</div>
                            <div class="legend-item" role="listitem"><span class="legend-dot completed"></span> Completed</div>
                            <div class="legend-item" role="listitem"><span class="legend-dot upcoming"></span> Upcoming</div>
                            <div class="legend-item" role="listitem"><span class="legend-dot tbd"></span> TBD</div>
                        </div>
                        <div style="font-size: 0.8rem; color: var(--text-muted); font-weight: 600;">
                            Scroll horizontally to view full bracket →
                        </div>
                    </div>
                </div>

                <!-- ══ BRACKET BODY ════════════════════════════════════ -->
                ${bracketBodyHtml}
            </div>
        `;

        // Draw connector lines after DOM is updated & bind window resize listener
        if (hasBracket) {
            requestAnimationFrame(() => this.drawBracketConnectors());
            if (!this._bracketResizeBound) {
                this._bracketResizeBound = true;
                window.addEventListener('resize', () => {
                    if (this.currentView === 'brackets') {
                        this.drawBracketConnectors();
                    }
                });
            }
        }
    },

    // ═══════════════════════════════════════════════════════════
    // BUILD PREMIUM BRACKET HTML — Round Columns with Match Cards
    // ═══════════════════════════════════════════════════════════
    buildPremiumBracketHtml(rounds) {
        if (!rounds || rounds.length === 0) return '';
        const totalRounds = rounds.length;

        return rounds.map((round, roundIdx) => {
            const isFinal = roundIdx === totalRounds - 1;
            const roundName = round.round_name || `ROUND ${round.round_number}`;
            const matches = round.matches || [];

            // Use justified spacing for each round
            const matchesHtml = matches.map((m, matchIdx) => {
                const matchId = m.public_match_id || m.match_id || '';
                const t1Name = m.team1_name || m.team_a_name || null;
                const t2Name = m.team2_name || m.team_b_name || null;
                const t1Score = m.team1_score ?? m.score_a ?? null;
                const t2Score = m.team2_score ?? m.score_b ?? null;
                const t1Logo = m.team1_logo || '';
                const t2Logo = m.team2_logo || '';
                const winnerId = m.winner_id || null;
                const t1Id = m.team1_id || null;
                const t2Id = m.team2_id || null;

                const status = (m.status || '').toUpperCase();
                const isCompleted = status === 'COMPLETED';
                const isLive = status === 'LIVE' || status === 'IN_PROGRESS';
                const isTBD = !t1Name && !t2Name;

                // Determine winner/loser states
                const t1IsWinner = isCompleted && winnerId && t1Id && winnerId === t1Id;
                const t2IsWinner = isCompleted && winnerId && t2Id && winnerId === t2Id;

                // Status badge
                let statusBadgeClass = 'tbd';
                let statusBadgeText = '◼ TBD';
                if (isLive) { statusBadgeClass = 'live'; statusBadgeText = '● LIVE'; }
                else if (isCompleted) { statusBadgeClass = 'completed'; statusBadgeText = '✓ DONE'; }
                else if (t1Name || t2Name) { statusBadgeClass = 'upcoming'; statusBadgeText = '🕐 UPCOMING'; }

                // State class for card
                let cardStateClass = '';
                if (isLive) cardStateClass = 'state-live';
                if (isFinal && isCompleted) cardStateClass += ' is-grand-final';
                else if (isFinal) cardStateClass += ' is-grand-final';

                // Team logo HTML
                const logoFor = (logoUrl, teamName) => {
                    if (logoUrl) {
                        return `<img src="${this.escapeHtml(logoUrl)}" onerror="App.handleImgError(this, '${TEAM_PLACEHOLDER_LOGO}')" class="match-team-logo" alt="${this.escapeHtml(teamName || 'Team')}">`;
                    }
                    // Default SVG badge for no-logo
                    const initial = (teamName || '?').charAt(0).toUpperCase();
                    return `<div class="match-team-logo" style="background: rgba(0,240,255,0.12); border: 1px solid rgba(0,240,255,0.3); display:flex;align-items:center;justify-content:center; font-family:var(--font-heading); font-weight:900; font-size:0.7rem; color:var(--accent-cyan);">${initial}</div>`;
                };

                // Team 1 row
                const t1Classes = `match-team-row${t1IsWinner ? ' winner' : ''}${isCompleted && !t1IsWinner && t1Name ? ' loser' : ''}${!t1Name ? ' tbd-slot' : ''}`;
                const t1Html = `
                    <div class="${t1Classes}">
                        <div class="match-team-info">
                            ${logoFor(t1Logo, t1Name)}
                            <span class="match-team-name">${this.escapeHtml(t1Name || 'TBD')}</span>
                        </div>
                        <span class="match-team-score">${(isCompleted || isLive) && t1Score !== null ? t1Score : (t1Name ? '–' : '')}</span>
                    </div>
                `;

                // Team 2 row
                const t2Classes = `match-team-row${t2IsWinner ? ' winner' : ''}${isCompleted && !t2IsWinner && t2Name ? ' loser' : ''}${!t2Name ? ' tbd-slot' : ''}`;
                const t2Html = `
                    <div class="${t2Classes}">
                        <div class="match-team-info">
                            ${logoFor(t2Logo, t2Name)}
                            <span class="match-team-name">${this.escapeHtml(t2Name || 'TBD')}</span>
                        </div>
                        <span class="match-team-score">${(isCompleted || isLive) && t2Score !== null ? t2Score : (t2Name ? '–' : '')}</span>
                    </div>
                `;

                // Winner indicator
                const winnerName = t1IsWinner ? t1Name : (t2IsWinner ? t2Name : null);
                const winnerHtml = winnerName && isCompleted ? `
                    <div class="match-winner-indicator" aria-label="Winner: ${this.escapeHtml(winnerName)}">
                        ✓ <span>${this.escapeHtml(winnerName)}</span> advanced
                    </div>
                ` : '';

                // Footer (time or status note)
                let footerHtml = '';
                if (isLive) {
                    footerHtml = `<div class="match-card-footer live-footer">🔴 MATCH IN PROGRESS</div>`;
                } else if (m.scheduled_time && !isCompleted) {
                    const dt = new Date(m.scheduled_time);
                    const timeStr = isNaN(dt.getTime()) ? m.scheduled_time : dt.toLocaleString(undefined, { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
                    footerHtml = `<div class="match-card-footer">📅 ${this.escapeHtml(timeStr)}</div>`;
                } else if (isTBD) {
                    footerHtml = `<div class="match-card-footer">⏳ Awaiting previous round</div>`;
                }

                // Store match data in cache for modal retrieval (safe - no JSON in HTML attr)
                if (!this._bracketMatchCache) this._bracketMatchCache = {};
                const cacheKey = `r${roundIdx}m${matchIdx}`;
                this._bracketMatchCache[cacheKey] = m;

                const onClickAttr = `onclick="App.showBracketMatchModal('${cacheKey}')"`;

                return `
                    <div class="bracket-match-card ${cardStateClass}" ${onClickAttr}
                         data-round="${roundIdx}" data-match="${matchIdx}"
                         role="button" tabindex="0" aria-label="Match: ${this.escapeHtml(t1Name || 'TBD')} vs ${this.escapeHtml(t2Name || 'TBD')}">
                        <!-- Match meta header -->
                        <div class="match-card-meta">
                            <span class="match-card-id">${matchId ? `#${this.escapeHtml(String(matchId))}` : `M${matchIdx + 1}`}</span>
                            <span class="match-card-status ${statusBadgeClass}">${statusBadgeText}</span>
                        </div>
                        <!-- Teams -->
                        ${t1Html}
                        ${t2Html}
                        <!-- Winner + footer -->
                        ${winnerHtml}
                        ${footerHtml}
                    </div>
                `;
            }).join('');

            return `
                <div class="bracket-round-column ${isFinal ? 'is-final' : ''} mobile-round-${roundIdx === 0 ? 'visible' : 'hidden'}"
                     data-round-idx="${roundIdx}" id="bracket-round-col-${roundIdx}"
                     aria-label="${this.escapeHtml(roundName)}">
                    <div class="bracket-round-header">
                        <div class="round-header-pill">${this.escapeHtml(roundName)}</div>
                    </div>
                    <div class="bracket-round-matches">
                        ${matchesHtml}
                    </div>
                </div>
            `;
        }).join('');
    },

    // ═══════════════════════════════════════════════════════════
    // DRAW BRACKET CONNECTOR LINES (SVG overlay)
    // ═══════════════════════════════════════════════════════════
    drawBracketConnectors() {
        const tree = document.getElementById('esports-bracket-tree');
        if (!tree) return;

        // Remove any existing SVG layer
        const existing = tree.querySelector('.bracket-svg-layer');
        if (existing) existing.remove();

        const columns = Array.from(tree.querySelectorAll('.bracket-round-column'));
        if (columns.length < 2) return;

        const treeRect = tree.getBoundingClientRect();
        const totalRounds = columns.length;

        const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
        svg.setAttribute('class', 'bracket-svg-layer');
        svg.setAttribute('aria-hidden', 'true');

        for (let ci = 0; ci < columns.length - 1; ci++) {
            const leftCol = columns[ci];
            const rightCol = columns[ci + 1];

            const leftCards = Array.from(leftCol.querySelectorAll('.bracket-match-card'));
            const rightCards = Array.from(rightCol.querySelectorAll('.bracket-match-card'));
            if (!leftCards.length || !rightCards.length) continue;

            const isFinalConnector = ci === totalRounds - 2;

            // Each pair of left-round matches feeds one right-round match
            for (let ri = 0; ri < rightCards.length; ri++) {
                const top = leftCards[ri * 2];
                const bottom = leftCards[ri * 2 + 1];
                const target = rightCards[ri];
                if (!target) continue;

                const targetRect = target.getBoundingClientRect();
                const targetX = targetRect.left - treeRect.left;
                const targetY = targetRect.top - treeRect.top + targetRect.height / 2;

                const drawLine = (sourceCard) => {
                    if (!sourceCard) return;
                    const srcRect = sourceCard.getBoundingClientRect();
                    const srcX = srcRect.right - treeRect.left;
                    const srcY = srcRect.top - treeRect.top + srcRect.height / 2;

                    const midX = srcX + (targetX - srcX) / 2;

                    const path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
                    // Horizontal from source card right → midpoint, then vertical → horizontal to target
                    const d = `M ${srcX} ${srcY} H ${midX} V ${targetY} H ${targetX}`;
                    path.setAttribute('d', d);
                    path.setAttribute('class', `bracket-connector-path${isFinalConnector ? ' final' : ''}`);
                    svg.appendChild(path);
                };

                drawLine(top);
                drawLine(bottom);
            }
        }

        // Set SVG viewport
        const treeComputedRect = tree.getBoundingClientRect();
        svg.setAttribute('width', treeComputedRect.width);
        svg.setAttribute('height', treeComputedRect.height);
        svg.setAttribute('viewBox', `0 0 ${treeComputedRect.width} ${treeComputedRect.height}`);

        tree.insertBefore(svg, tree.firstChild);
    },

    // ═══════════════════════════════════════════════════════════
    // BRACKET MATCH DETAIL MODAL
    // ═══════════════════════════════════════════════════════════
    showBracketMatchModal(matchOrKey) {
        // Accept either a cache key string or direct match object
        let match;
        if (typeof matchOrKey === 'string') {
            match = (this._bracketMatchCache || {})[matchOrKey];
        } else {
            match = matchOrKey;
        }
        if (!match) return;
        const t1 = match.team1_name || match.team_a_name || 'TBD';
        const t2 = match.team2_name || match.team_b_name || 'TBD';
        const s1 = match.team1_score ?? match.score_a ?? '–';
        const s2 = match.team2_score ?? match.score_b ?? '–';
        const status = match.status || 'PENDING';
        const isCompleted = status === 'COMPLETED';
        const matchId = match.public_match_id || match.match_id || '';
        const stage = match.stage_name || '';

        let dt = '';
        if (match.scheduled_time) {
            const d = new Date(match.scheduled_time);
            dt = isNaN(d.getTime()) ? match.scheduled_time : d.toLocaleString(undefined, { weekday: 'short', month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
        }

        this.showModal(`
            <div style="text-align: center; max-width: 420px; margin: 0 auto;">
                <div style="font-family: var(--font-heading); font-size: 0.8rem; font-weight: 900; letter-spacing: 2px; color: var(--accent-cyan); text-transform: uppercase; margin-bottom: 1rem;">
                    ${matchId ? `Match #${this.escapeHtml(String(matchId))}` : 'Match Details'}
                </div>

                <div style="display: grid; grid-template-columns: 1fr auto 1fr; gap: 1rem; align-items: center; margin-bottom: 1.5rem; background: rgba(0,0,0,0.4); padding: 1.25rem; border-radius: var(--radius-md); border: 1px solid var(--border-card);">
                    <div style="text-align: center;">
                        <div style="font-family: var(--font-heading); font-weight: 800; font-size: 1rem; color: #fff; margin-bottom: 0.25rem; word-break: break-word;">${this.escapeHtml(t1)}</div>
                        ${isCompleted ? `<div style="font-family: var(--font-heading); font-size: 2.2rem; font-weight: 900; color: var(--accent-cyan);">${s1}</div>` : ''}
                    </div>
                    <div style="font-family: var(--font-heading); font-weight: 900; font-size: 1.1rem; color: var(--text-muted); text-align: center;">VS</div>
                    <div style="text-align: center;">
                        <div style="font-family: var(--font-heading); font-weight: 800; font-size: 1rem; color: #fff; margin-bottom: 0.25rem; word-break: break-word;">${this.escapeHtml(t2)}</div>
                        ${isCompleted ? `<div style="font-family: var(--font-heading); font-size: 2.2rem; font-weight: 900; color: var(--accent-gold);">${s2}</div>` : ''}
                    </div>
                </div>

                <div style="display: flex; flex-direction: column; gap: 0.5rem; text-align: left; font-size: 0.88rem; margin-bottom: 1.5rem;">
                    <div style="display: flex; justify-content: space-between; padding: 0.5rem 0.75rem; background: rgba(0,0,0,0.3); border-radius: var(--radius-sm);">
                        <span style="color: var(--text-muted); font-weight: 600;">Status</span>
                        <span style="font-weight: 700; color: ${status === 'COMPLETED' ? 'var(--accent-green)' : (status === 'LIVE' ? 'var(--accent-red)' : 'var(--accent-gold)')}">${this.escapeHtml(status)}</span>
                    </div>
                    ${stage ? `<div style="display: flex; justify-content: space-between; padding: 0.5rem 0.75rem; background: rgba(0,0,0,0.3); border-radius: var(--radius-sm);"><span style="color: var(--text-muted); font-weight: 600;">Stage</span><span style="font-weight: 700;">${this.escapeHtml(stage)}</span></div>` : ''}
                    ${dt ? `<div style="display: flex; justify-content: space-between; padding: 0.5rem 0.75rem; background: rgba(0,0,0,0.3); border-radius: var(--radius-sm);"><span style="color: var(--text-muted); font-weight: 600;">Scheduled</span><span style="font-weight: 700;">${this.escapeHtml(dt)}</span></div>` : ''}
                    ${isCompleted && match.winner_name ? `<div style="display: flex; justify-content: space-between; padding: 0.5rem 0.75rem; background: rgba(0,240,255,0.08); border: 1px solid rgba(0,240,255,0.25); border-radius: var(--radius-sm);"><span style="color: var(--accent-cyan); font-weight: 700;">🏆 Winner</span><span style="font-weight: 800; color: var(--accent-cyan);">${this.escapeHtml(match.winner_name)}</span></div>` : ''}
                </div>

                <button onclick="App.hideModal()" class="btn btn-secondary" style="width: 100%;">Close</button>
            </div>
        `);
    },

    // ═══════════════════════════════════════════════════════════
    // MOBILE BRACKET ROUND TAB SWITCHING
    // ═══════════════════════════════════════════════════════════
    bracketShowRound(roundIdx) {
        // Update tab buttons
        document.querySelectorAll('.bracket-tab-btn').forEach((btn, i) => {
            btn.classList.toggle('active', i === roundIdx);
        });
        // Show/hide columns (only relevant on mobile)
        document.querySelectorAll('.bracket-round-column').forEach((col, i) => {
            col.classList.toggle('mobile-round-hidden', i !== roundIdx);
            col.classList.toggle('mobile-round-visible', i === roundIdx);
        });
    },

    async changeBracketTournament(slug) {
        this.activeTournamentSlug = slug;
        const tree = document.getElementById('esports-bracket-tree');
        if (tree) {
            tree.innerHTML = `
                <div style="padding: 4rem 2rem; text-align: center; width: 100%;">
                    <div class="spinner" style="margin: 0 auto 1rem; border: 3px solid rgba(0,240,255,0.2); border-top-color: var(--accent-cyan); width: 36px; height: 36px; border-radius: 50%; animation: spin 0.8s linear infinite;"></div>
                    <div style="color: var(--text-muted); font-size: 0.9rem; font-weight: 700; letter-spacing: 0.5px;">LOADING BRACKET DATA...</div>
                </div>
            `;
        }
        await this.renderBracketsView();
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

        // Check OAuth session first if userDiscordId is not set
        if (!this.userDiscordId) {
            const authRes = await Api.getAuthMe();
            if (authRes && authRes.authenticated && authRes.user_id) {
                this.userDiscordId = authRes.user_id;
            }
        }

        if (!this.userDiscordId) {
            container.innerHTML = `
                <div style="max-width: 500px; margin: 4rem auto;" class="glass-panel">
                    <div style="text-align: center; margin-bottom: 2rem;">
                        <div style="font-size: 3.5rem; margin-bottom: 0.5rem;">🎮</div>
                        <h2 style="font-family: var(--font-heading); font-size: 2rem;">PLAYER DASHBOARD LOGIN</h2>
                        <p style="color: var(--text-secondary); font-size: 0.95rem; margin-top: 0.5rem; line-height: 1.5;">
                            Access your GEN Esports account, active team roster, registered tournaments, upcoming matches & results securely.
                        </p>
                    </div>

                    <div style="margin-bottom: 2rem;">
                        <button onclick="Api.loginWithDiscord()" class="btn btn-discord btn-lg" style="width: 100%; justify-content: center; font-size: 1.1rem; padding: 0.9rem;">
                            <svg class="icon-discord" viewBox="0 0 24 24" width="22" height="22" fill="currentColor">
                                <path d="M20.317 4.37a19.791 19.791 0 0 0-4.885-1.515.074.074 0 0 0-.079.037c-.21.375-.444.864-.608 1.25a18.27 18.27 0 0 0-5.487 0 12.64 12.64 0 0 0-.617-1.25.077.077 0 0 0-.079-.037A19.736 19.736 0 0 0 3.677 4.37a.07.07 0 0 0-.032.027C.533 9.046-.32 13.58.099 18.057a.082.082 0 0 0 .031.057 19.9 19.9 0 0 0 5.993 3.03.078.078 0 0 0 .084-.028 14.09 14.09 0 0 0 1.226-1.994.076.076 0 0 0-.041-.106 13.107 13.107 0 0 1-1.872-.892.077.077 0 0 1-.008-.128c.126-.093.252-.19.373-.287a.075.075 0 0 1 .078-.01c3.927 1.793 8.18 1.793 12.061 0a.075.075 0 0 1 .079.009c.12.098.245.195.372.288a.077.077 0 0 1-.006.128 12.299 12.299 0 0 1-1.873.892.077.077 0 0 0-.041.107c.36.698.772 1.362 1.225 1.993a.076.076 0 0 0 .084.028 19.839 19.839 0 0 0 6.002-3.03.077.077 0 0 0 .032-.054c.5-5.177-.838-9.674-3.549-13.66a.061.061 0 0 0-.031-.028zM8.02 15.33c-1.183 0-2.157-1.085-2.157-2.419 0-1.333.956-2.419 2.157-2.419 1.21 0 2.176 1.096 2.157 2.42 0 1.333-.956 2.418-2.157 2.418zm7.975 0c-1.183 0-2.157-1.085-2.157-2.419 0-1.333.955-2.419 2.157-2.419 1.21 0 2.176 1.096 2.157 2.42 0 1.333-.946 2.418-2.157 2.418z"/>
                            </svg>
                            <span>LOGIN WITH DISCORD</span>
                        </button>
                    </div>

                    <div style="position: relative; text-align: center; margin: 1.5rem 0;">
                        <span style="background: var(--bg-card); padding: 0 10px; color: var(--text-muted); font-size: 0.85rem;">OR ENTER DISCORD ID</span>
                        <div style="position: absolute; top: 50%; left: 0; right: 0; border-top: 1px solid var(--border-card); z-index: -1;"></div>
                    </div>

                    <form onsubmit="App.loginUserDashboard(event)">
                        <div class="form-group" style="margin-bottom: 1.25rem;">
                            <input type="text" id="user-id-input" class="form-input" placeholder="e.g. 123456789012345678" required>
                        </div>
                        <button type="submit" class="btn btn-secondary" style="width: 100%;">
                            🔑 Quick Access by User ID
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
        const matches = await Api.getMatches();
        const userMatches = matches ? matches.filter(m => 
            (m.team1_id && profile && profile.teams && profile.teams.some(t => t.team_id === m.team1_id)) ||
            (m.team2_id && profile && profile.teams && profile.teams.some(t => t.team_id === m.team2_id))
        ) : [];

        const getStatusBadge = (status) => {
            if (status === 'APPROVED') return '<span class="badge badge-open">🟢 APPROVED</span>';
            if (status === 'PENDING') return '<span class="badge" style="background: rgba(255, 193, 7, 0.2); color: #ffc107; border: 1px solid #ffc107;">🟡 PENDING</span>';
            if (status === 'REJECTED') return '<span class="badge badge-closed">🔴 REJECTED</span>';
            return '<span class="badge badge-closed">⚪ CANCELLED</span>';
        };

        container.innerHTML = `
            <div style="margin-bottom: 2.5rem; display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 1rem;">
                <div>
                    <div class="hero-badge">👤 PLAYER DASHBOARD</div>
                    <h1 style="font-family: var(--font-heading); font-size: 2.4rem; margin-top: 0.25rem;">
                        WELCOME BACK, <span class="gradient-text">${profile ? this.escapeHtml(profile.display_name) : 'COMPETITOR'}</span>
                    </h1>
                </div>
                <button onclick="App.logoutUserDashboard()" class="btn btn-secondary" style="font-size: 0.85rem;">
                    🔒 Logout / Switch Account
                </button>
            </div>

            <div class="stats-banner glass-panel" style="margin-bottom: 2.5rem;">
                <div class="stat-box"><div class="stat-val" style="color: var(--accent-cyan);">${profile ? this.escapeHtml(profile.public_id) : 'GEN-P-000000'}</div><div class="stat-lbl">Public ID</div></div>
                <div class="stat-box"><div class="stat-val" style="color: var(--accent-gold);">${regs.length}</div><div class="stat-lbl">Registrations</div></div>
                <div class="stat-box"><div class="stat-val" style="color: var(--accent-green);">${profile && profile.teams ? profile.teams.length : 0}</div><div class="stat-lbl">Active Teams</div></div>
                <div class="stat-box"><div class="stat-val">${userMatches.length}</div><div class="stat-lbl">Upcoming Matches</div></div>
            </div>

            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 2rem;">
                <div class="glass-panel" style="padding: 1.5rem;">
                    <h3 style="font-family: var(--font-heading); font-size: 1.3rem; margin-bottom: 1rem;">📋 Tournament Registrations (${regs.length})</h3>
                    <div style="display: flex; flex-direction: column; gap: 0.75rem;">
                        ${regs.length === 0 ? '<div style="color: var(--text-muted);">No registrations found. Join a tournament via Discord!</div>' : regs.map(r => `
                            <div style="background: rgba(0,0,0,0.3); padding: 0.9rem; border-radius: var(--radius-sm); border: 1px solid var(--border-card);">
                                <div style="display: flex; justify-content: space-between; align-items: center; font-weight: 700; margin-bottom: 0.5rem;">
                                    <span style="font-size: 1.05rem;">🛡️ ${this.escapeHtml(r.team_name)}</span>
                                    ${getStatusBadge(r.status)}
                                </div>
                                <div style="font-size: 0.85rem; color: var(--text-secondary); margin-bottom: 0.25rem;">🏆 ${this.escapeHtml(r.tournament_name)}</div>
                                <div style="font-size: 0.8rem; color: var(--text-muted); display: flex; justify-content: space-between;">
                                    <span>Code: <code>${this.escapeHtml(r.registration_code || r.ticket_id)}</code></span>
                                    <span>Date: ${new Date(r.submitted_at || Date.now()).toLocaleDateString()}</span>
                                </div>
                            </div>
                        `).join('')}
                    </div>
                </div>

                <div class="glass-panel" style="padding: 1.5rem;">
                    <h3 style="font-family: var(--font-heading); font-size: 1.3rem; margin-bottom: 1rem;">⚔️ Upcoming Matches & Schedule (${userMatches.length})</h3>
                    <div style="display: flex; flex-direction: column; gap: 0.75rem;">
                        ${userMatches.length === 0 ? '<div style="color: var(--text-muted);">No upcoming matches scheduled.</div>' : userMatches.map(m => `
                            <div style="background: rgba(0,0,0,0.3); padding: 0.9rem; border-radius: var(--radius-sm); border: 1px solid var(--border-card);">
                                <div style="display: flex; justify-content: space-between; font-weight: 700; margin-bottom: 0.3rem;">
                                    <span>⚔️ ${this.escapeHtml(m.team1_name || 'TBD')} vs ${this.escapeHtml(m.team2_name || 'TBD')}</span>
                                    <span class="badge badge-open">${m.status || 'SCHEDULED'}</span>
                                </div>
                                <div style="font-size: 0.85rem; color: var(--text-secondary);">🏆 ${this.escapeHtml(m.tournament_name || 'Tournament')} • Stage: ${this.escapeHtml(m.stage_name || 'Stage')}</div>
                                <div style="font-size: 0.8rem; color: var(--text-muted); margin-top: 0.4rem; display: flex; gap: 0.5rem;">
                                    <button onclick="App.openDiscordInvite()" class="btn btn-secondary btn-sm">🏠 OPEN MATCH ROOM</button>
                                </div>
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

    async logoutUserDashboard() {
        this.userDiscordId = '';
        localStorage.removeItem('gen_user_discord_id');
        await Api.logout();
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
                                            <button onclick="App.handleAdminBracketButtonClick('${t.tournament_id}')" class="btn btn-primary" style="padding: 0.3rem 0.6rem; font-size: 0.75rem;" title="View or Generate Bracket">🏆 Bracket</button>
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
                                    <td><span style="color: var(--accent-cyan); font-weight: 700;">${this.escapeHtml(this.formatStageName(m.stage_name, m.round_number))}</span></td>
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

    async handleAdminBracketButtonClick(tournamentId) {
        console.log('Admin Bracket clicked for tournament ID:', tournamentId);
        if (!tournamentId) {
            this.showToast('✕ Invalid tournament ID', 'error');
            return;
        }

        try {
            // Fetch bracket status for this tournament
            const bracketData = await Api.getTournamentBracket(tournamentId);
            const hasBracket = bracketData && bracketData.has_bracket && bracketData.rounds && bracketData.rounds.length > 0;

            if (hasBracket) {
                // Bracket already exists -> Open bracket view directly for this tournament
                const targetSlug = (bracketData.tournament && bracketData.tournament.slug) ? bracketData.tournament.slug : String(tournamentId);
                this.activeTournamentSlug = targetSlug;
                this.showToast(`🏆 Opening bracket for tournament #${tournamentId}`, 'info');
                await this.renderView('brackets');
                window.location.hash = `#brackets?tournament=${encodeURIComponent(targetSlug)}`;
                return;
            }

            // Bracket does NOT exist -> Fetch tournament details and show confirmation modal
            let tInfo = bracketData ? bracketData.tournament : null;
            if (!tInfo) {
                const tournaments = await Api.getTournaments().catch(() => []);
                tInfo = tournaments.find(t => String(t.tournament_id) === String(tournamentId) || t.slug === String(tournamentId));
            }

            const title = tInfo ? (tInfo.title || tInfo.name || `Tournament #${tournamentId}`) : `Tournament #${tournamentId}`;
            const approvedTeams = tInfo ? (tInfo.registered_teams_count || tInfo.current_approved_team_count || 0) : 0;
            const maxTeams = tInfo ? (tInfo.max_teams || 8) : 8;
            const format = tInfo ? (tInfo.format || 'Single Elimination') : 'Single Elimination';

            this.showModal(`
                <div style="text-align: center; padding: 0.5rem;">
                    <div style="font-size: 2.5rem; margin-bottom: 0.5rem;">🏆</div>
                    <h3 style="font-family: var(--font-heading); font-size: 1.5rem; color: #fff; margin-bottom: 1rem;">GENERATE TOURNAMENT BRACKET</h3>
                    <div class="glass-panel" style="padding: 1.25rem; margin-bottom: 1.5rem; text-align: left; background: rgba(0,0,0,0.4); border-radius: var(--radius-md);">
                        <p style="margin-bottom: 0.5rem;"><strong>Tournament:</strong> <span style="color: var(--accent-cyan); font-weight: 700;">${this.escapeHtml(title)}</span></p>
                        <p style="margin-bottom: 0.5rem;"><strong>Teams:</strong> <span style="color: var(--accent-green); font-weight: 700;">${approvedTeams} / ${maxTeams} Approved</span></p>
                        <p style="margin-bottom: 0;"><strong>Format:</strong> <span style="color: var(--accent-gold); font-weight: 700;">${this.escapeHtml(format)}</span></p>
                    </div>
                    <div style="display: flex; gap: 0.75rem; justify-content: center;">
                        <button type="button" onclick="App.hideModal()" class="btn btn-secondary" style="padding: 0.5rem 1.2rem;">Cancel</button>
                        <button type="button" onclick="App.confirmGenerateBracket('${this.escapeHtml(String(tournamentId))}')" class="btn btn-primary" style="padding: 0.5rem 1.2rem; font-weight: 700;">🏆 GENERATE BRACKET</button>
                    </div>
                </div>
            `);
        } catch (err) {
            console.error('Error in handleAdminBracketButtonClick:', err);
            this.showModal(`
                <div style="text-align: center; padding: 1rem;">
                    <div style="font-size: 3rem; margin-bottom: 0.5rem;">❌</div>
                    <h3 style="font-family: var(--font-heading); font-size: 1.4rem; color: var(--accent-red); margin-bottom: 0.75rem;">Unable to load bracket</h3>
                    <p style="color: var(--text-secondary); margin-bottom: 1.5rem;"><strong>Reason:</strong> ${this.escapeHtml(err.message || 'Unknown technical error')}</p>
                    <button type="button" onclick="App.hideModal()" class="btn btn-secondary">Close</button>
                </div>
            `);
        }
    },

    async confirmGenerateBracket(tournamentId) {
        console.log('Confirming bracket generation for tournament ID:', tournamentId);
        try {
            this.hideModal();
            this.showToast('⏳ Generating tournament bracket...', 'info');
            await Api.generateBracket(this.adminApiKey, tournamentId);
            this.showToast('🏆 Tournament bracket generated successfully!', 'success');
            
            // Set active tournament and switch to bracket view
            this.activeTournamentSlug = String(tournamentId);
            await this.renderView('brackets');
            window.location.hash = `#brackets?tournament=${encodeURIComponent(tournamentId)}`;
        } catch (err) {
            console.error('Error generating bracket:', err);
            this.showModal(`
                <div style="text-align: center; padding: 1rem;">
                    <div style="font-size: 3rem; margin-bottom: 0.5rem;">❌</div>
                    <h3 style="font-family: var(--font-heading); font-size: 1.4rem; color: var(--accent-red); margin-bottom: 0.75rem;">Unable to generate bracket</h3>
                    <p style="color: var(--text-secondary); margin-bottom: 1.5rem;"><strong>Reason:</strong> ${this.escapeHtml(err.message || 'Unknown technical error')}</p>
                    <button type="button" onclick="App.hideModal()" class="btn btn-secondary">Close</button>
                </div>
            `);
        }
    },

    async handleGenerateBracket(id) {
        return this.handleAdminBracketButtonClick(id);
    },

    showScheduleModal(matchId, currentScheduled = '', currentLobby = '') {
        const dtVal = toDateTimeLocalValue(currentScheduled);
        this.showModal(`
            <h3 style="font-family: var(--font-heading); font-size: 1.5rem; margin-bottom: 1rem; color: #fff;">📅 Schedule Match & Lobby Info</h3>
            <form onsubmit="App.handleSaveSchedule(event, ${matchId})">
                <div style="margin-bottom: 1.25rem;">
                    <label style="display: block; font-weight: 700; font-size: 0.85rem; color: var(--text-secondary); margin-bottom: 0.4rem; text-transform: uppercase;">SCHEDULED TIME (ASIA/DHAKA)</label>
                    <input type="datetime-local" id="m-schedule-time" name="scheduled_at" step="60" class="form-input" value="${dtVal}" style="width: 100%; color-scheme: dark;" required>
                </div>
                <div style="margin-bottom: 1.25rem;">
                    <label style="display: block; font-weight: 700; font-size: 0.85rem; color: var(--text-secondary); margin-bottom: 0.4rem; text-transform: uppercase;">MAP / MODE</label>
                    <input type="text" id="m-map" class="form-input" placeholder="e.g. Haven / Ascent / Erangel">
                </div>
                <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 1rem; margin-bottom: 1.5rem;">
                    <div>
                        <label style="display: block; font-weight: 700; font-size: 0.85rem; color: var(--text-secondary); margin-bottom: 0.4rem; text-transform: uppercase;">LOBBY NAME / ID</label>
                        <input type="text" id="m-lobby-name" class="form-input" placeholder="e.g. GEN-MATCH-${matchId}" value="${this.escapeHtml(currentLobby)}">
                    </div>
                    <div>
                        <label style="display: block; font-weight: 700; font-size: 0.85rem; color: var(--text-secondary); margin-bottom: 0.4rem; text-transform: uppercase;">LOBBY PASSWORD</label>
                        <input type="text" id="m-lobby-pass" class="form-input" placeholder="e.g. 1234">
                    </div>
                </div>
                <button type="submit" class="btn btn-primary" style="width: 100%; padding: 0.75rem; font-weight: 700;">💾 Save Schedule & Lobby Info</button>
            </form>
        `);
    },

    async handleSaveSchedule(e, matchId) {
        e.preventDefault();
        const rawTime = document.getElementById('m-schedule-time').value;
        const map_name = document.getElementById('m-map').value;
        const lobby_name = document.getElementById('m-lobby-name').value;
        const lobby_password = document.getElementById('m-lobby-pass').value;

        if (!rawTime) {
            this.showToast('✕ Please select a valid date and time', 'error');
            return;
        }

        let formattedSchedule = rawTime;
        try {
            const dateObj = new Date(rawTime);
            if (!Number.isNaN(dateObj.getTime())) {
                const day = String(dateObj.getDate()).padStart(2, '0');
                const months = ['Aug', 'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
                const month = months[dateObj.getMonth() + 1];
                const year = dateObj.getFullYear();
                let hours = dateObj.getHours();
                const minutes = String(dateObj.getMinutes()).padStart(2, '0');
                const ampm = hours >= 12 ? 'PM' : 'AM';
                hours = hours % 12;
                hours = hours ? hours : 12;
                formattedSchedule = `${day} ${month} ${year}, ${hours}:${minutes} ${ampm} (Asia/Dhaka)`;
            }
        } catch (e) {
            console.warn('Format schedule date notice:', e);
        }

        try {
            await Api.scheduleMatch(this.adminApiKey, matchId, {
                scheduled_at: formattedSchedule,
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

    selectedEvidenceFile: null,

    showScoreInputModal(matchId, t1Name, t2Name, currentScore1 = 0, currentScore2 = 0) {
        this.selectedEvidenceFile = null;
        this.showModal(`
            <div style="max-width: 520px; margin: 0 auto;">
                <h3 style="font-family: var(--font-heading); font-size: 1.6rem; margin-bottom: 0.5rem; text-align: center; color: #fff;">⚔️ ENTER MATCH RESULT</h3>
                <p style="color: var(--text-secondary); font-size: 0.9rem; text-align: center; margin-bottom: 1.5rem;">
                    Match #${matchId} • Submit scores & screenshot evidence to advance bracket.
                </p>
                <form onsubmit="App.handleSaveMatchScore(event, ${matchId})">
                    <div style="display: grid; grid-template-columns: 1fr auto 1fr; gap: 1rem; align-items: center; background: rgba(0,0,0,0.3); border: 1px solid var(--border-card); padding: 1.25rem; border-radius: var(--radius-md); margin-bottom: 1.25rem;">
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

                    <div style="margin-bottom: 1.5rem;">
                        <label style="display: block; font-weight: 700; font-size: 0.9rem; margin-bottom: 0.5rem; color: #fff;">
                            📸 Screenshot Evidence <span style="color: var(--accent-cyan);">*</span>
                        </label>
                        
                        <div id="m-evidence-dropzone" class="evidence-dropzone" onclick="document.getElementById('m-evidence-file').click()" ondragover="App.handleEvidenceDragOver(event)" ondragleave="App.handleEvidenceDragLeave(event)" ondrop="App.handleEvidenceDrop(event)">
                            <div id="m-evidence-prompt">
                                <div style="font-size: 1.8rem; margin-bottom: 0.4rem;">📸</div>
                                <div style="font-size: 0.95rem; font-weight: 700; color: #fff; margin-bottom: 0.25rem;">
                                    Drag & drop screenshot here
                                </div>
                                <div style="font-size: 0.85rem; color: var(--text-secondary); margin-bottom: 0.75rem;">
                                    or
                                </div>
                                <button type="button" class="btn btn-secondary" style="padding: 0.4rem 1rem; font-size: 0.85rem;" onclick="event.stopPropagation(); document.getElementById('m-evidence-file').click()">
                                    📎 Choose Screenshot
                                </button>
                                <div style="font-size: 0.75rem; color: var(--text-muted); margin-top: 0.75rem;">
                                    PNG, JPG, WEBP • Max 10 MB
                                </div>
                            </div>
                            
                            <div id="m-evidence-preview" style="display: none;"></div>
                        </div>
                        <input type="file" id="m-evidence-file" accept="image/png, image/jpeg, image/jpg, image/webp" style="display: none;" onchange="App.handleEvidenceFileSelect(event)">
                        <p style="color: var(--text-secondary); font-size: 0.8rem; margin-top: 0.4rem;">
                            Upload a clear screenshot of the final match result.
                        </p>
                    </div>

                    <button type="submit" id="m-score-submit-btn" class="btn btn-primary" style="width: 100%; padding: 0.85rem; font-size: 1rem; font-weight: 700;">
                        🏆 SUBMIT RESULT & ADVANCE WINNER
                    </button>
                </form>
            </div>
        `);
    },

    handleEvidenceDragOver(e) {
        e.preventDefault();
        const dropzone = document.getElementById('m-evidence-dropzone');
        if (dropzone) dropzone.classList.add('dragover');
    },

    handleEvidenceDragLeave(e) {
        e.preventDefault();
        const dropzone = document.getElementById('m-evidence-dropzone');
        if (dropzone) dropzone.classList.remove('dragover');
    },

    handleEvidenceDrop(e) {
        e.preventDefault();
        const dropzone = document.getElementById('m-evidence-dropzone');
        if (dropzone) dropzone.classList.remove('dragover');
        if (e.dataTransfer && e.dataTransfer.files && e.dataTransfer.files[0]) {
            this.handleEvidenceFileSelect({ target: { files: e.dataTransfer.files } });
        }
    },

    handleEvidenceFileSelect(e) {
        const file = e.target.files ? e.target.files[0] : null;
        if (!file) return;

        const validTypes = ['image/png', 'image/jpeg', 'image/jpg', 'image/webp'];
        if (!validTypes.includes(file.type.toLowerCase())) {
            this.showToast('✕ Invalid file type. Only PNG, JPG, and WEBP images are allowed.', 'error');
            e.target.value = '';
            return;
        }

        if (file.size > 10 * 1024 * 1024) {
            const sizeMB = (file.size / (1024 * 1024)).toFixed(2);
            this.showToast(`✕ File size (${sizeMB} MB) exceeds maximum allowed limit of 10 MB.`, 'error');
            e.target.value = '';
            return;
        }

        this.selectedEvidenceFile = file;
        this.renderEvidencePreview(file);
    },

    renderEvidencePreview(file) {
        const promptEl = document.getElementById('m-evidence-prompt');
        const previewEl = document.getElementById('m-evidence-preview');
        if (!promptEl || !previewEl) return;

        const reader = new FileReader();
        reader.onload = (e) => {
            const sizeMB = (file.size / (1024 * 1024)).toFixed(2);
            previewEl.innerHTML = `
                <div class="evidence-preview-card">
                    <div style="display: flex; align-items: center; gap: 0.85rem; overflow: hidden;">
                        <img src="${e.target.result}" alt="Evidence Preview" style="width: 56px; height: 56px; border-radius: 8px; object-fit: cover; border: 2px solid var(--accent-cyan); flex-shrink: 0;">
                        <div style="text-align: left; overflow: hidden;">
                            <div style="font-weight: 700; font-size: 0.9rem; color: #fff; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">
                                ${this.escapeHtml(file.name)}
                            </div>
                            <div style="font-size: 0.8rem; color: var(--text-secondary);">
                                ${sizeMB} MB
                            </div>
                        </div>
                    </div>
                    <button type="button" class="btn btn-secondary" style="padding: 0.35rem 0.75rem; font-size: 0.8rem; color: var(--accent-red); border-color: var(--accent-red); flex-shrink: 0;" onclick="event.stopPropagation(); App.removeEvidenceFile();">
                        ✕ Remove
                    </button>
                </div>
            `;
            promptEl.style.display = 'none';
            previewEl.style.display = 'block';
        };
        reader.readAsDataURL(file);
    },

    removeEvidenceFile() {
        this.selectedEvidenceFile = null;
        const fileInput = document.getElementById('m-evidence-file');
        if (fileInput) fileInput.value = '';

        const promptEl = document.getElementById('m-evidence-prompt');
        const previewEl = document.getElementById('m-evidence-preview');
        if (promptEl && previewEl) {
            previewEl.style.display = 'none';
            previewEl.innerHTML = '';
            promptEl.style.display = 'block';
        }
    },

    async handleSaveMatchScore(e, matchId) {
        e.preventDefault();
        const score1 = parseInt(document.getElementById('m-score1').value || '0', 10);
        const score2 = parseInt(document.getElementById('m-score2').value || '0', 10);
        const submitBtn = document.getElementById('m-score-submit-btn');

        if (!this.selectedEvidenceFile) {
            this.showToast('✕ Screenshot evidence is required before submitting match result.', 'error');
            return;
        }

        try {
            if (submitBtn) {
                submitBtn.disabled = true;
                submitBtn.innerText = '⏳ Uploading Evidence & Saving...';
            }

            // Step 1: Upload evidence file
            const uploadRes = await Api.uploadMatchEvidence(this.selectedEvidenceFile, matchId);
            const evidenceUrl = uploadRes.url;

            // Step 2: Record match result & advance bracket
            await Api.submitMatchResult(this.adminApiKey, matchId, {
                team1_score: score1,
                team2_score: score2,
                status: 'COMPLETED',
                evidence_url: evidenceUrl
            });

            this.hideModal();
            this.showToast('🏆 Match score & evidence recorded! Winner advanced in bracket.', 'success');
            await this.refreshAdminData();
        } catch (err) {
            if (submitBtn) {
                submitBtn.disabled = false;
                submitBtn.innerText = '🏆 SUBMIT RESULT & ADVANCE WINNER';
            }
            this.showToast('✕ Error recording match score: ' + err.message, 'error');
        }
    }
};

window.App = App;
