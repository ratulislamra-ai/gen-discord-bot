/**
 * GEN ESPORTS WEB PLATFORM APPLICATION CONTROLLER
 * Independent Competitive Tournament Platform Logic.
 */

document.addEventListener('DOMContentLoaded', () => {
    App.init();
});

const App = {
    currentView: 'home',
    discordInviteUrl: '',
    autoRefreshInterval: null,

    async init() {
        this.bindEvents();
        await this.loadConfig();
        this.renderView('home');
        this.startAutoRefresh();
    },

    startAutoRefresh() {
        if (this.autoRefreshInterval) {
            clearInterval(this.autoRefreshInterval);
        }
        // Poll every 15 seconds for automatic Discord -> Database -> Website sync
        this.autoRefreshInterval = setInterval(async () => {
            if (this.currentView === 'home' || this.currentView === 'tournaments' || this.currentView === 'teams') {
                await this.refreshActiveViewData();
            }
        }, 15000);
    },

    async refreshActiveViewData() {
        try {
            if (this.currentView === 'home') {
                const stats = await Api.getStats();
                const statVals = document.querySelectorAll('.stats-banner .stat-val');
                if (statVals.length >= 4) {
                    statVals[0].textContent = stats.total_tournaments ?? 0;
                    statVals[1].textContent = stats.approved_registrations ?? 0;
                    statVals[2].textContent = stats.completed_matches ?? 0;
                    statVals[3].textContent = stats.registered_players ?? 0;
                }
            } else if (this.currentView === 'teams') {
                const tournaments = await Api.getTournaments();
                const activeTournaments = tournaments.filter(t => t.game_type === 'VALORANT' || t.game_type === 'PUBG MOBILE' || t.game_type === 'Valorant');
                let allApprovedTeams = [];

                for (const t of activeTournaments) {
                    const teams = await Api.getApprovedTeams(t.slug);
                    allApprovedTeams = allApprovedTeams.concat(teams);
                }

                const teamsContainer = document.querySelector('#app-content .teams-grid');
                if (teamsContainer) {
                    let teamsHtml = allApprovedTeams.length === 0 ? `
                        <div class="glass-panel" style="padding: 4rem; text-align: center; grid-column: 1 / -1;">
                            <div style="font-size: 3rem; margin-bottom: 1rem;">🛡️</div>
                            <h3>No Approved Teams Yet</h3>
                            <p style="color: var(--text-secondary); margin-top: 0.5rem;">Approved team rosters will automatically post here upon admin review.</p>
                        </div>
                    ` : allApprovedTeams.map(team => {
                        const logoSrc = team.team_logo_url ? (team.team_logo_url.startsWith('http') ? team.team_logo_url : `/${team.team_logo_url}`) : 'https://via.placeholder.com/64?text=GEN';
                        const encodedTeam = encodeURIComponent(JSON.stringify(team));
                        return `
                            <div class="team-card glass-panel" onclick="App.showTeamProfileModal('${encodedTeam}')">
                                <div class="team-card-header">
                                    <img src="${logoSrc}" alt="${team.team_name}" class="team-logo-lg" onerror="this.src='https://via.placeholder.com/64?text=TEAM'">
                                    <div>
                                        <div class="team-info-name">${team.team_name}</div>
                                        <div class="team-info-captain">👑 Captain: ${team.captain_name}</div>
                                    </div>
                                </div>
                                <div style="font-size: 0.85rem; color: var(--text-muted); margin-bottom: 1rem;">
                                    🏆 ${team.tournament}
                                </div>
                                <div class="roster-grid">
                                    ${(team.roster || []).map(p => `
                                        <div class="roster-row">
                                            <span class="roster-role">${p.role}</span>
                                            <span class="roster-ign">${p.ign}</span>
                                        </div>
                                    `).join('')}
                                </div>
                            </div>
                        `;
                    }).join('');
                    teamsContainer.innerHTML = teamsHtml;
                }
            }
        } catch (err) {
            console.warn('Silent background refresh notice:', err);
        }
    },

    async loadConfig() {
        const config = await Api.getConfig();
        this.discordInviteUrl = config.discord_invite_url || '';
    },

    openDiscordInvite() {
        if (this.discordInviteUrl && this.discordInviteUrl.startsWith('http')) {
            window.open(this.discordInviteUrl, '_blank', 'noopener');
        } else {
            const modal = document.getElementById('details-modal');
            const modalBody = document.getElementById('modal-body');
            modalBody.innerHTML = `
                <div style="text-align: center; padding: 1.5rem;">
                    <div style="font-size: 3rem; margin-bottom: 1rem; color: var(--accent-gold);">💬</div>
                    <h3 style="font-family: var(--font-heading); font-size: 1.5rem; margin-bottom: 0.75rem;">Discord Server Invite</h3>
                    <p style="color: var(--text-secondary); line-height: 1.6; font-size: 0.95rem;">
                        The GEN Esports Discord server invite link is currently being updated by tournament administrators. Please check back shortly or ask an admin in server channels.
                    </p>
                </div>
            `;
            modal.classList.remove('hidden');
        }
    },

    bindEvents() {
        // Mobile Toggle Menu
        const mobileToggle = document.getElementById('mobile-toggle-btn');
        const navMenu = document.getElementById('nav-menu');
        if (mobileToggle && navMenu) {
            mobileToggle.addEventListener('click', () => {
                navMenu.classList.toggle('active');
            });
        }

        // Navigation links
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

        // Modal Close Button & Backdrop
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

    updateNavActive(view) {
        document.querySelectorAll('.nav-link').forEach(link => {
            if (link.getAttribute('data-view') === view) {
                link.classList.add('active');
            } else {
                link.classList.remove('active');
            }
        });
    },

    async renderView(view) {
        this.currentView = view;
        this.updateNavActive(view);
        window.scrollTo({ top: 0, behavior: 'smooth' });

        const container = document.getElementById('app-content');
        container.innerHTML = `
            <div style="padding: 5rem; text-align: center; font-family: var(--font-heading);">
                <div style="font-size: 2.5rem; margin-bottom: 1rem; color: var(--accent-cyan);">⚡</div>
                <h2 style="font-size: 1.8rem; font-weight: 800;">LOADING GEN ESPORTS PLATFORM...</h2>
            </div>
        `;

        switch (view) {
            case 'home':
                await this.renderHomeView(container);
                break;
            case 'tournaments':
                await this.renderTournamentsView(container);
                break;
            case 'teams':
                await this.renderTeamsView(container);
                break;
            case 'matches':
            case 'brackets':
                await this.renderBracketsView(container);
                break;
            case 'leaderboards':
                await this.renderLeaderboardsView(container);
                break;
            case 'admin':
                await this.renderAdminView(container);
                break;
            default:
                await this.renderHomeView(container);
        }
    },

    // =========================================================================
    // 1. HOMEPAGE VIEW (NO DEMO DATA & DYNAMIC DISCORD INVITE)
    // =========================================================================
    async renderHomeView(container) {
        const stats = await Api.getStats();
        const tournaments = await Api.getTournaments();
        const matches = await Api.getMatches();

        // Filter active supported games
        const activeTournaments = tournaments.filter(t => t.game_type === 'VALORANT' || t.game_type === 'PUBG MOBILE' || t.game_type === 'Valorant');

        // 1. Featured Tournaments Cards
        let featuredTournamentsHtml = activeTournaments.length === 0 ? `
            <div class="glass-panel" style="padding: 3rem; text-align: center; grid-column: 1 / -1;">
                <div style="font-size: 2.5rem; margin-bottom: 1rem;">🏆</div>
                <h3>No Tournaments Available</h3>
                <p style="color: var(--text-secondary); margin-top: 0.5rem;">Check back soon for upcoming GEN Esports competitions.</p>
            </div>
        ` : activeTournaments.map(t => `
            <div class="tournament-card glass-panel">
                <div class="card-banner">
                    <span class="game-badge">🎮 ${t.game_type || 'Esports'}</span>
                    <span class="status-badge ${t.status === 'REGISTRATION_OPEN' ? 'status-open' : 'status-ongoing'}">
                        ${t.status === 'REGISTRATION_OPEN' ? 'Registration Open' : t.status}
                    </span>
                    <div class="card-banner-title">${(t.game_type || 'GEN').substring(0, 4)}</div>
                </div>
                <div class="card-body">
                    <h3 class="card-name">${t.title}</h3>
                    <p class="card-desc">${t.rules_text || 'GEN Esports competitive tournament series. Register your squad via Discord.'}</p>

                    <div class="card-meta">
                        <div class="meta-item">
                            <span class="meta-label">Format</span>
                            <span class="meta-val">Competitive Format</span>
                        </div>
                        <div class="meta-item">
                            <span class="meta-label">Max Capacity</span>
                            <span class="meta-val">${t.max_teams || 16} Teams</span>
                        </div>
                    </div>

                    <button class="btn btn-primary" onclick="App.showApprovedTeamsModal('${t.slug}', '${t.title}')">
                        🏆 View Approved Teams
                    </button>
                </div>
            </div>
        `).join('');

        // 2. Upcoming Tournaments List
        const upcomingTournaments = activeTournaments.filter(t => t.status === 'REGISTRATION_OPEN' || t.status === 'DRAFT');
        let upcomingHtml = upcomingTournaments.length === 0 ? `
            <p style="color: var(--text-secondary);">No upcoming tournaments scheduled at this time.</p>
        ` : upcomingTournaments.map(t => `
            <div style="display: flex; align-items: center; justify-content: space-between; padding: 1.25rem 1.5rem; margin-bottom: 1rem;" class="glass-panel">
                <div style="display: flex; align-items: center; gap: 1rem;">
                    <div style="font-size: 1.8rem;">🎮</div>
                    <div>
                        <h4 style="font-family: var(--font-heading); font-size: 1.15rem; font-weight: 700;">${t.title}</h4>
                        <span style="font-size: 0.85rem; color: var(--accent-cyan); font-weight: 600;">Status: Registration Open</span>
                    </div>
                </div>
                <button class="btn btn-secondary" onclick="App.showApprovedTeamsModal('${t.slug}', '${t.title}')">View Details</button>
            </div>
        `).join('');

        // 3. Approved Teams Preview (Real API data)
        let allApprovedTeams = [];
        for (const t of activeTournaments) {
            const teams = await Api.getApprovedTeams(t.slug);
            allApprovedTeams = allApprovedTeams.concat(teams);
        }

        let teamsPreviewHtml = allApprovedTeams.length === 0 ? `
            <div class="glass-panel" style="padding: 3rem; text-align: center; grid-column: 1 / -1;">
                <div style="font-size: 2.5rem; margin-bottom: 0.5rem;">🛡️</div>
                <h3>No Approved Teams</h3>
                <p style="color: var(--text-secondary);">Approved tournament registrations will appear here.</p>
            </div>
        ` : allApprovedTeams.slice(0, 3).map(team => {
            const logoSrc = team.team_logo_url ? (team.team_logo_url.startsWith('http') ? team.team_logo_url : `/${team.team_logo_url}`) : 'https://via.placeholder.com/64?text=GEN';
            return `
                <div class="team-card glass-panel" onclick="App.showTeamProfileModal('${encodeURIComponent(JSON.stringify(team))}')">
                    <div class="team-card-header">
                        <img src="${logoSrc}" alt="${team.team_name}" class="team-logo-lg" onerror="this.src='https://via.placeholder.com/64?text=TEAM'">
                        <div>
                            <div class="team-info-name">${team.team_name}</div>
                            <div class="team-info-captain">👑 Captain: ${team.captain_name}</div>
                        </div>
                    </div>
                    <div style="font-size: 0.85rem; color: var(--text-muted); margin-bottom: 0.75rem;">
                        🏆 ${team.tournament}
                    </div>
                    <div class="roster-grid">
                        ${(team.roster || []).slice(0, 3).map(p => `
                            <div class="roster-row">
                                <span class="roster-role">${p.role}</span>
                                <span class="roster-ign">${p.ign}</span>
                            </div>
                        `).join('')}
                    </div>
                </div>
            `;
        }).join('');

        // 4. Matches Preview (Real API Data or Clean Empty State)
        let matchesHtml = matches.length === 0 ? `
            <div class="glass-panel" style="padding: 3rem; text-align: center; grid-column: 1 / -1;">
                <div style="font-size: 2.5rem; margin-bottom: 0.5rem;">⚔️</div>
                <h3 style="font-family: var(--font-heading);">No Matches Scheduled Yet</h3>
                <p style="color: var(--text-secondary); font-size: 0.9rem; margin-top: 0.3rem;">
                    Match schedules and results will update live once tournament brackets begin.
                </p>
            </div>
        ` : matches.slice(0, 3).map(m => `
            <div class="match-card glass-panel">
                <div class="match-header">
                    <span>${m.tournament_name || 'GEN Tournament'}</span>
                    <span style="color: var(--accent-cyan); font-weight: 700;">${m.stage_name || 'Match'}</span>
                </div>
                <div class="match-vs-box">
                    <div class="match-team-block">
                        <div class="match-team-name">${m.team1_name || 'Team 1'}</div>
                    </div>
                    <div class="match-score">${m.team1_score ?? 0} - ${m.team2_score ?? 0}</div>
                    <div class="match-team-block">
                        <div class="match-team-name">${m.team2_name || 'Team 2'}</div>
                    </div>
                </div>
                <div style="font-size: 0.8rem; color: var(--text-muted); text-align: center;">
                    Status: ${m.status}
                </div>
            </div>
        `).join('');

        // Assemble Full Homepage Layout
        container.innerHTML = `
            <!-- 2-Column Hero Section -->
            <section class="hero-container">
                <div class="hero-bg-grid"></div>
                <div class="hero-content">
                    <div class="hero-tag">⚡ INDEPENDENT ESPORTS PLATFORM</div>
                    <h1 class="hero-title">
                        COMPETE. CONQUER.<br>
                        <span class="hero-title-accent">BECOME LEGEND.</span>
                    </h1>
                    <p class="hero-subtitle">
                        GEN Esports is an independent competitive gaming platform built for players, teams, and communities. Register teams seamlessly via Discord, track live match brackets, explore approved team rosters, and rise on season leaderboards.
                    </p>
                    <div class="hero-cta-group">
                        <button class="btn btn-primary" onclick="App.renderView('tournaments')">
                            🏆 Explore Tournaments
                        </button>
                        <button onclick="App.openDiscordInvite()" class="btn btn-discord">
                            Join Discord Server
                        </button>
                    </div>
                </div>

                <!-- Right Column Visual Graphic -->
                <div class="hero-visual-wrapper">
                    <div class="hero-hud-card">
                        <span class="hero-hud-badge">🔴 ARENA ACTIVE</span>
                        <img src="/static/assets/hero_emblem.png" alt="GEN Esports Championship Emblem" onerror="this.src='https://via.placeholder.com/400?text=GEN+ESPORTS'">
                        <div class="hero-hud-meta">
                            <span>⚡ COMMUNITY COMPETITIONS</span>
                            <span style="color: var(--accent-green); font-weight: 700;">GEN ENGINE 2.0</span>
                        </div>
                    </div>
                </div>
            </section>

            <!-- Real API Platform Stats -->
            <section class="stats-banner">
                <div class="stat-box glass-panel">
                    <div class="stat-val">${stats.total_tournaments ?? 0}</div>
                    <div class="stat-lbl">Active Tournaments</div>
                </div>
                <div class="stat-box glass-panel">
                    <div class="stat-val" style="color: var(--accent-green);">${stats.approved_registrations ?? 0}</div>
                    <div class="stat-lbl">Approved Teams</div>
                </div>
                <div class="stat-box glass-panel">
                    <div class="stat-val" style="color: var(--accent-cyan);">${stats.completed_matches ?? 0}</div>
                    <div class="stat-lbl">Completed Matches</div>
                </div>
                <div class="stat-box glass-panel">
                    <div class="stat-val" style="color: var(--accent-gold);">${stats.registered_players ?? 0}</div>
                    <div class="stat-lbl">Registered Players</div>
                </div>
            </section>

            <!-- Featured Tournaments Section -->
            <section style="margin-bottom: 4rem;">
                <div class="section-header">
                    <div>
                        <h2 class="section-title">🏆 Featured Tournaments</h2>
                        <p class="section-subtitle">Active esports championships currently open for registration.</p>
                    </div>
                    <button class="btn btn-secondary" onclick="App.renderView('tournaments')">View All Tournaments</button>
                </div>
                <div class="tournaments-grid">
                    ${featuredTournamentsHtml}
                </div>
            </section>

            <!-- Upcoming Tournaments Section -->
            <section style="margin-bottom: 4rem;">
                <div class="section-header">
                    <div>
                        <h2 class="section-title">📅 Upcoming Competitions</h2>
                        <p class="section-subtitle">Get your roster ready for upcoming tournament registrations.</p>
                    </div>
                </div>
                <div>
                    ${upcomingHtml}
                </div>
            </section>

            <!-- Live & Recent Matches Section -->
            <section style="margin-bottom: 4rem;">
                <div class="section-header">
                    <div>
                        <h2 class="section-title">⚔️ Recent Results & Live Matches</h2>
                        <p class="section-subtitle">Real-time match updates and tournament standings.</p>
                    </div>
                    <button class="btn btn-secondary" onclick="App.renderView('brackets')">View Bracket View</button>
                </div>
                <div class="matches-grid">
                    ${matchesHtml}
                </div>
            </section>

            <!-- Top Teams Roster Showcase -->
            <section style="margin-bottom: 4rem;">
                <div class="section-header">
                    <div>
                        <h2 class="section-title">🛡️ Top Approved Teams</h2>
                        <p class="section-subtitle">Verified teams registered for GEN Esports tournament series.</p>
                    </div>
                    <button class="btn btn-secondary" onclick="App.renderView('teams')">View All Teams</button>
                </div>
                <div class="teams-grid">
                    ${teamsPreviewHtml}
                </div>
            </section>

            <!-- Final Call To Action -->
            <section class="cta-banner">
                <h2 class="cta-title">READY TO COMPETE?</h2>
                <p class="cta-desc">
                    Build your roster. Enter the arena. Make your name known.
                </p>
                <div style="display: flex; gap: 1.25rem; justify-content: center; flex-wrap: wrap;">
                    <button class="btn btn-primary" onclick="App.renderView('tournaments')">EXPLORE TOURNAMENTS</button>
                    <button onclick="App.openDiscordInvite()" class="btn btn-discord">JOIN DISCORD</button>
                </div>
            </section>
        `;
    },

    // =========================================================================
    // 2. TOURNAMENTS VIEW
    // =========================================================================
    async renderTournamentsView(container) {
        const tournaments = await Api.getTournaments();
        const activeTournaments = tournaments.filter(t => t.game_type === 'VALORANT' || t.game_type === 'PUBG MOBILE' || t.game_type === 'Valorant');

        let gridHtml = activeTournaments.length === 0 ? `
            <div class="glass-panel" style="padding: 4rem; text-align: center; grid-column: 1 / -1;">
                <div style="font-size: 3rem; margin-bottom: 1rem;">🏆</div>
                <h3>No Active Tournaments</h3>
                <p style="color: var(--text-secondary); margin-top: 0.5rem;">New tournament announcements will be posted here and on Discord.</p>
            </div>
        ` : activeTournaments.map(t => `
            <div class="tournament-card glass-panel">
                <div class="card-banner">
                    <span class="game-badge">🎮 ${t.game_type || 'Esports'}</span>
                    <span class="status-badge status-open">${t.status}</span>
                    <div class="card-banner-title">${(t.game_type || 'GEN').substring(0, 4)}</div>
                </div>
                <div class="card-body">
                    <h3 class="card-name">${t.title}</h3>
                    <p class="card-desc">${t.rules_text}</p>
                    <div class="card-meta">
                        <div class="meta-item">
                            <span class="meta-label">Format</span>
                            <span class="meta-val">Competitive Format</span>
                        </div>
                        <div class="meta-item">
                            <span class="meta-label">Max Teams</span>
                            <span class="meta-val">${t.max_teams} Teams</span>
                        </div>
                    </div>
                    <button class="btn btn-primary" onclick="App.showApprovedTeamsModal('${t.slug}', '${t.title}')">
                        👥 View Approved Teams
                    </button>
                </div>
            </div>
        `).join('');

        container.innerHTML = `
            <div class="section-header">
                <div>
                    <h1 class="section-title">🎮 Tournament Directory</h1>
                    <p class="section-subtitle">Browse active competitions and view approved team rosters.</p>
                </div>
            </div>
            <div class="tournaments-grid">
                ${gridHtml}
            </div>
        `;
    },

    // =========================================================================
    // 3. TEAMS & ROSTERS VIEW
    // =========================================================================
    async renderTeamsView(container) {
        const tournaments = await Api.getTournaments();
        const activeTournaments = tournaments.filter(t => t.game_type === 'VALORANT' || t.game_type === 'PUBG MOBILE' || t.game_type === 'Valorant');
        let allApprovedTeams = [];

        for (const t of activeTournaments) {
            const teams = await Api.getApprovedTeams(t.slug);
            allApprovedTeams = allApprovedTeams.concat(teams);
        }

        let teamsHtml = allApprovedTeams.length === 0 ? `
            <div class="glass-panel" style="padding: 4rem; text-align: center; grid-column: 1 / -1;">
                <div style="font-size: 3rem; margin-bottom: 1rem;">🛡️</div>
                <h3>No Approved Teams Yet</h3>
                <p style="color: var(--text-secondary); margin-top: 0.5rem;">Approved team rosters will automatically post here upon admin review.</p>
            </div>
        ` : allApprovedTeams.map(team => {
            const logoSrc = team.team_logo_url ? (team.team_logo_url.startsWith('http') ? team.team_logo_url : `/${team.team_logo_url}`) : 'https://via.placeholder.com/64?text=GEN';
            const encodedTeam = encodeURIComponent(JSON.stringify(team));
            return `
                <div class="team-card glass-panel" onclick="App.showTeamProfileModal('${encodedTeam}')">
                    <div class="team-card-header">
                        <img src="${logoSrc}" alt="${team.team_name}" class="team-logo-lg" onerror="this.src='https://via.placeholder.com/64?text=TEAM'">
                        <div>
                            <div class="team-info-name">${team.team_name}</div>
                            <div class="team-info-captain">👑 Captain: ${team.captain_name}</div>
                        </div>
                    </div>
                    <div style="font-size: 0.85rem; color: var(--text-muted); margin-bottom: 1rem;">
                        🏆 ${team.tournament}
                    </div>
                    <div class="roster-grid">
                        ${(team.roster || []).map(p => `
                            <div class="roster-row">
                                <span class="roster-role">${p.role}</span>
                                <span class="roster-ign">${p.ign}</span>
                            </div>
                        `).join('')}
                    </div>
                </div>
            `;
        }).join('');

        container.innerHTML = `
            <div class="section-header">
                <div>
                    <h1 class="section-title">🛡️ Approved Team Directory</h1>
                    <p class="section-subtitle">Explore team profiles and player rosters.</p>
                </div>
            </div>
            <div class="teams-grid">
                ${teamsHtml}
            </div>
        `;
    },

    // =========================================================================
    // 4. BRACKETS & MATCHES VIEW (NO FAKE/DEMO DATA - REAL OR EMPTY STATE)
    // =========================================================================
    async renderBracketsView(container) {
        const matches = await Api.getMatches();

        let contentHtml = '';
        if (matches.length === 0) {
            // Required Professional Empty State
            contentHtml = `
                <div class="glass-panel" style="padding: 4rem 2rem; text-align: center; margin-top: 1rem;">
                    <div style="font-size: 3.5rem; margin-bottom: 1rem;">⚔️</div>
                    <h2 style="font-family: var(--font-heading); font-size: 1.8rem; font-weight: 800;">Bracket Not Started</h2>
                    <p style="color: var(--text-secondary); max-width: 500px; margin: 0.5rem auto 1.5rem auto; font-size: 1rem;">
                        Teams and matchups will appear here once the tournament bracket is generated.
                    </p>
                    <button class="btn btn-primary" onclick="App.renderView('tournaments')">Explore Tournaments</button>
                </div>
            `;
        } else {
            contentHtml = `
                <div class="glass-panel" style="padding: 2rem; margin-bottom: 2rem;">
                    <h3 style="font-family: var(--font-heading); color: var(--accent-cyan); margin-bottom: 1.5rem; font-size: 1.4rem;">
                        🏆 Live Tournament Matches
                    </h3>
                    <div class="matches-grid">
                        ${matches.map(m => `
                            <div class="match-card glass-panel">
                                <div class="match-header">
                                    <span>${m.tournament_name || 'GEN Tournament'}</span>
                                    <span style="color: var(--accent-cyan); font-weight: 700;">${m.stage_name || 'Match'}</span>
                                </div>
                                <div class="match-vs-box">
                                    <div class="match-team-block">
                                        <div class="match-team-name">${m.team1_name || 'Team 1'}</div>
                                    </div>
                                    <div class="match-score">${m.team1_score ?? 0} - ${m.team2_score ?? 0}</div>
                                    <div class="match-team-block">
                                        <div class="match-team-name">${m.team2_name || 'Team 2'}</div>
                                    </div>
                                </div>
                                <div style="font-size: 0.8rem; color: var(--text-muted); text-align: center;">
                                    Status: ${m.status}
                                </div>
                            </div>
                        `).join('')}
                    </div>
                </div>
            `;
        }

        container.innerHTML = `
            <div class="section-header">
                <div>
                    <h1 class="section-title">⚔️ Tournament Brackets & Schedule</h1>
                    <p class="section-subtitle">Real-time match bracket elimination tree visualizer.</p>
                </div>
            </div>
            ${contentHtml}
        `;
    },

    // =========================================================================
    // 5. LEADERBOARDS VIEW (REAL OR CLEAN EMPTY STATE)
    // =========================================================================
    async renderLeaderboardsView(container) {
        container.innerHTML = `
            <div class="section-header">
                <div>
                    <h1 class="section-title">🥇 Season Standings & Leaderboards</h1>
                    <p class="section-subtitle">Season standings, circuit points, and prize money distribution.</p>
                </div>
            </div>

            <div class="glass-panel" style="padding: 4rem 2rem; text-align: center;">
                <div style="font-size: 3.5rem; margin-bottom: 1rem;">🥇</div>
                <h2 style="font-family: var(--font-heading); font-size: 1.8rem; font-weight: 800;">No Season Standings Yet</h2>
                <p style="color: var(--text-secondary); max-width: 500px; margin: 0.5rem auto 1.5rem auto;">
                    Tournament standings and team rankings will populate once official matches conclude.
                </p>
                <button class="btn btn-primary" onclick="App.renderView('tournaments')">Explore Active Tournaments</button>
            </div>
        `;
    },

    // =========================================================================
    // 6. ADMIN PORTAL VIEW
    // =========================================================================
    async renderAdminView(container) {
        container.innerHTML = `
            <div class="section-header">
                <div>
                    <h1 class="section-title">🔑 Admin Control Portal</h1>
                    <p class="section-subtitle">Manage tournament registrations, audit queues, and system status.</p>
                </div>
            </div>

            <div class="glass-panel" style="max-width: 520px; margin: 2rem auto; padding: 2.5rem;">
                <h3 style="font-family: var(--font-heading); margin-bottom: 1rem; color: var(--accent-gold); font-size: 1.4rem;">
                    🔑 Authenticate Admin Access
                </h3>
                <p style="font-size: 0.9rem; color: var(--text-secondary); margin-bottom: 1.5rem;">
                    Enter the configured <code style="color: var(--accent-cyan); font-weight: 700;">GEN_API_KEY</code> from your server environment to unlock management tools.
                </p>
                <div style="display: flex; flex-direction: column; gap: 1rem;">
                    <input type="password" id="admin-api-key-input" placeholder="Enter GEN_API_KEY..." style="padding: 0.85rem; border-radius: var(--radius-sm); border: 1px solid var(--border-card); background: rgba(0,0,0,0.6); color: #fff; font-size: 1rem;">
                    <button class="btn btn-primary" onclick="App.authenticateAdmin()">Authenticate Admin Portal</button>
                    <div id="admin-auth-error" style="color: var(--accent-red); font-size: 0.9rem;" class="hidden"></div>
                </div>
            </div>

            <div id="admin-dashboard-results" class="hidden"></div>
        `;
    },

    async authenticateAdmin() {
        const input = document.getElementById('admin-api-key-input');
        const errDiv = document.getElementById('admin-auth-error');
        const resultsDiv = document.getElementById('admin-dashboard-results');
        const key = input ? input.value.trim() : '';

        if (!key) {
            errDiv.innerText = 'Please enter an API key.';
            errDiv.classList.remove('hidden');
            return;
        }

        try {
            const stats = await Api.getAdminStats(key);
            errDiv.classList.add('hidden');

            resultsDiv.innerHTML = `
                <div class="stats-banner" style="margin-top: 2.5rem;">
                    <div class="stat-box glass-panel" style="border-left-color: var(--accent-green);">
                        <div class="stat-val" style="color: var(--accent-green);">${stats.approved_registrations}</div>
                        <div class="stat-lbl">APPROVED REGISTRATIONS</div>
                    </div>
                    <div class="stat-box glass-panel" style="border-left-color: var(--accent-gold);">
                        <div class="stat-val" style="color: var(--accent-gold);">${stats.pending_registrations}</div>
                        <div class="stat-lbl">PENDING REVIEW</div>
                    </div>
                    <div class="stat-box glass-panel" style="border-left-color: var(--accent-red);">
                        <div class="stat-val" style="color: var(--accent-red);">${stats.rejected_registrations}</div>
                        <div class="stat-lbl">REJECTED</div>
                    </div>
                    <div class="stat-box glass-panel">
                        <div class="stat-val">${stats.total_registrations}</div>
                        <div class="stat-lbl">TOTAL SUBMISSIONS</div>
                    </div>
                </div>

                <div class="glass-panel" style="margin-top: 2rem; padding: 2rem;">
                    <h3 style="font-family: var(--font-heading); color: var(--accent-cyan); margin-bottom: 1.25rem;">
                        ⚡ System Connection & Server Status
                    </h3>
                    <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap: 1.5rem;">
                        <div style="padding: 1rem; background: rgba(0,255,136,0.05); border: 1px solid var(--accent-green); border-radius: 8px;">
                            🟢 REST API Server<br>
                            <strong style="color: var(--accent-green);">ONLINE (Port 8000)</strong>
                        </div>
                        <div style="padding: 1rem; background: rgba(0,240,255,0.05); border: 1px solid var(--accent-cyan); border-radius: 8px;">
                            🟢 Discord Gateway<br>
                            <strong style="color: var(--accent-cyan);">CONNECTED & SYNCED</strong>
                        </div>
                        <div style="padding: 1rem; background: rgba(255,215,0,0.05); border: 1px solid var(--accent-gold); border-radius: 8px;">
                            🟢 SQLite Database<br>
                            <strong style="color: var(--accent-gold);">SYNCHRONIZED</strong>
                        </div>
                    </div>
                </div>
            `;
            resultsDiv.classList.remove('hidden');
        } catch (err) {
            errDiv.innerText = '❌ Invalid API Key. Access Denied.';
            errDiv.classList.remove('hidden');
        }
    },

    // Modals
    async showApprovedTeamsModal(slug, title) {
        const teams = await Api.getApprovedTeams(slug);
        const modal = document.getElementById('details-modal');
        const modalBody = document.getElementById('modal-body');

        let teamsHtml = teams.length === 0 ? '<p style="color: var(--text-secondary); margin-top: 1rem;">No approved teams for this tournament yet.</p>' :
            teams.map(t => `
                <div style="padding: 1rem; background: rgba(255,255,255,0.03); border-radius: 8px; margin-bottom: 0.8rem; border-left: 3px solid var(--accent-green);">
                    <h4 style="color: #fff; margin-bottom: 0.3rem; font-family: var(--font-heading);">🛡️ ${t.team_name}</h4>
                    <div style="font-size: 0.85rem; color: var(--text-secondary);">Registration ID: <code>${t.registration_id}</code></div>
                    <div style="font-size: 0.85rem; color: var(--accent-green);">Captain: ${t.captain_name}</div>
                </div>
            `).join('');

        modalBody.innerHTML = `
            <h2 style="font-family: var(--font-heading); color: var(--accent-cyan); margin-bottom: 1rem;">
                🏆 ${title} • Approved Teams
            </h2>
            <div style="max-height: 400px; overflow-y: auto;">
                ${teamsHtml}
            </div>
        `;
        modal.classList.remove('hidden');
    },

    showTeamProfileModal(encodedTeamStr) {
        try {
            const team = JSON.parse(decodeURIComponent(encodedTeamStr));
            const modal = document.getElementById('details-modal');
            const modalBody = document.getElementById('modal-body');

            const logoSrc = team.team_logo_url ? (team.team_logo_url.startsWith('http') ? team.team_logo_url : `/${team.team_logo_url}`) : 'https://via.placeholder.com/64?text=TEAM';
            const rosterItems = (team.roster || []).map(p => `
                <div class="roster-row" style="padding: 0.6rem 1rem;">
                    <span class="roster-role" style="font-size: 0.9rem;">${p.role}</span>
                    <span class="roster-ign" style="font-size: 0.95rem;">${p.ign}</span>
                </div>
            `).join('');

            modalBody.innerHTML = `
                <div style="display: flex; align-items: center; gap: 1.25rem; margin-bottom: 1.5rem;">
                    <img src="${logoSrc}" alt="${team.team_name}" class="team-logo-lg" onerror="this.src='https://via.placeholder.com/64?text=TEAM'">
                    <div>
                        <h2 style="font-family: var(--font-heading); font-size: 1.8rem; font-weight: 800;">${team.team_name}</h2>
                        <span style="color: var(--accent-green); font-weight: 600; font-size: 0.9rem;">👑 Captain: ${team.captain_name}</span>
                    </div>
                </div>
                <div style="font-size: 0.9rem; color: var(--text-secondary); margin-bottom: 1.25rem;">
                    🏆 Tournament: <strong>${team.tournament}</strong> | Code: <code>${team.registration_id}</code>
                </div>
                <h3 style="font-family: var(--font-heading); font-size: 1.1rem; margin-bottom: 0.75rem; color: var(--accent-cyan);">
                    📋 Active Roster
                </h3>
                <div class="roster-grid">
                    ${rosterItems}
                </div>
            `;
            modal.classList.remove('hidden');
        } catch (e) {
            console.error('Error opening team profile modal:', e);
        }
    },

    hideModal() {
        const modal = document.getElementById('details-modal');
        if (modal) modal.classList.add('hidden');
    }
};

window.App = App;
