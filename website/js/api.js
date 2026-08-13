/**
 * GEN Esports API Client
 */
const API_BASE = '/api';

const Api = {
    /**
     * Fetch public configuration (e.g., Discord Invite URL)
     */
    async getConfig() {
        try {
            const res = await fetch(`${API_BASE}/public/config`);
            if (!res.ok) throw new Error(`HTTP error ${res.status}`);
            return await res.json();
        } catch (err) {
            console.error('Failed to fetch public config:', err);
            return {
                discord_invite_url: 'https://discord.gg/G568r5MFqB'
            };
        }
    },

    /**
     * Fetch public stats overview
     */
    async getStats() {
        try {
            const res = await fetch(`${API_BASE}/public/stats`);
            if (!res.ok) throw new Error(`HTTP error ${res.status}`);
            return await res.json();
        } catch (err) {
            console.error('Failed to fetch public stats:', err);
            return {
                total_registrations: 0,
                approved_registrations: 0,
                pending_registrations: 0,
                total_tournaments: 0,
                completed_matches: 0,
                registered_players: 0
            };
        }
    },

    /**
     * Fetch detailed tournament list
     */
    async getTournaments() {
        try {
            const res = await fetch(`${API_BASE}/public/tournaments`);
            if (!res.ok) throw new Error(`HTTP error ${res.status}`);
            return await res.json();
        } catch (err) {
            console.error('Failed to fetch tournaments:', err);
            return [];
        }
    },

    /**
     * Fetch single tournament by slug/title/ID
     */
    async getTournamentDetails(slug) {
        if (!slug) return null;
        try {
            const res = await fetch(`${API_BASE}/public/tournaments/${encodeURIComponent(slug)}`);
            if (!res.ok) throw new Error(`HTTP error ${res.status}`);
            const data = await res.json();
            if (data && data.tournament) {
                return data;
            }
            const approved_teams = await this.getApprovedTeams(slug);
            return { tournament: data, approved_teams };
        } catch (err) {
            console.error(`Failed to fetch tournament details for ${slug}:`, err);
            return null;
        }
    },

    /**
     * Fetch approved teams for a specific tournament or all public teams
     */
    async getApprovedTeams(tournamentSlug) {
        if (!tournamentSlug) {
            return this.getTeams();
        }
        try {
            const res = await fetch(`${API_BASE}/public/tournaments/${encodeURIComponent(tournamentSlug)}/approved-teams`);
            if (!res.ok) throw new Error(`HTTP error ${res.status}`);
            return await res.json();
        } catch (err) {
            console.error(`Failed to fetch approved teams for ${tournamentSlug}:`, err);
            return [];
        }
    },

    /**
     * Fetch tournament bracket matches
     */
    async getTournamentBracket(tournamentSlug) {
        try {
            const res = await fetch(`${API_BASE}/public/tournaments/${encodeURIComponent(tournamentSlug)}/bracket`);
            if (!res.ok) throw new Error(`HTTP error ${res.status}`);
            return await res.json();
        } catch (err) {
            console.error(`Failed to fetch bracket for ${tournamentSlug}:`, err);
            return [];
        }
    },

    /**
     * Fetch tournament standings
     */
    async getTournamentStandings(tournamentSlug) {
        try {
            const res = await fetch(`${API_BASE}/public/tournaments/${encodeURIComponent(tournamentSlug)}/standings`);
            if (!res.ok) throw new Error(`HTTP error ${res.status}`);
            return await res.json();
        } catch (err) {
            console.error(`Failed to fetch standings for ${tournamentSlug}:`, err);
            return [];
        }
    },

    /**
     * Fetch public matches (live, upcoming, completed)
     */
    async getMatches() {
        try {
            const res = await fetch(`${API_BASE}/public/matches`);
            if (!res.ok) throw new Error(`HTTP error ${res.status}`);
            return await res.json();
        } catch (err) {
            console.error('Failed to fetch public matches:', err);
            return [];
        }
    },

    /**
     * Fetch admin statistics
     */
    async getAdminStats(apiKey) {
        const res = await fetch(`${API_BASE}/admin/stats`, {
            headers: { 'X-API-Key': apiKey }
        });
        if (!res.ok) throw new Error(`HTTP error ${res.status}`);
        return await res.json();
    },

    /**
     * Fetch admin registrations
     */
    async getAdminRegistrations(apiKey, statusFilter = '') {
        const url = statusFilter ? `${API_BASE}/admin/registrations?status_filter=${statusFilter}` : `${API_BASE}/admin/registrations`;
        const res = await fetch(url, {
            headers: { 'X-API-Key': apiKey }
        });
        if (!res.ok) throw new Error(`HTTP error ${res.status}`);
        return await res.json();
    },

    /**
     * Approve registration via Admin API
     */
    async approveRegistration(apiKey, ticketId) {
        const res = await fetch(`${API_BASE}/admin/registrations/${ticketId}/approve`, {
            method: 'POST',
            headers: { 'X-API-Key': apiKey }
        });
        if (!res.ok) {
            const err = await res.json().catch(() => ({}));
            throw new Error(err.detail || `HTTP error ${res.status}`);
        }
        return await res.json();
    },

    /**
     * Reject registration via Admin API
     */
    async rejectRegistration(apiKey, ticketId, reason) {
        const res = await fetch(`${API_BASE}/admin/registrations/${ticketId}/reject`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'X-API-Key': apiKey },
            body: JSON.stringify({ reason })
        });
        if (!res.ok) {
            const err = await res.json().catch(() => ({}));
            throw new Error(err.detail || `HTTP error ${res.status}`);
        }
        return await res.json();
    },

    /**
     * Fetch tournaments for Admin panel
     */
    async getAdminTournaments(apiKey) {
        const res = await fetch(`${API_BASE}/admin/tournaments`, {
            headers: { 'X-API-Key': apiKey }
        });
        if (!res.ok) throw new Error(`HTTP error ${res.status}`);
        return await res.json();
    },

    /**
     * Create tournament via Admin API
     */
    async createTournament(apiKey, data) {
        const res = await fetch(`${API_BASE}/admin/tournaments`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'X-API-Key': apiKey },
            body: JSON.stringify(data)
        });
        if (!res.ok) {
            const err = await res.json().catch(() => ({}));
            throw new Error(err.detail || `HTTP error ${res.status}`);
        }
        return await res.json();
    },

    /**
     * Update tournament via Admin API
     */
    async updateTournament(apiKey, tournamentId, data) {
        const res = await fetch(`${API_BASE}/admin/tournaments/${tournamentId}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json', 'X-API-Key': apiKey },
            body: JSON.stringify(data)
        });
        if (!res.ok) {
            const err = await res.json().catch(() => ({}));
            throw new Error(err.detail || `HTTP error ${res.status}`);
        }
        return await res.json();
    },

    /**
     * Cancel tournament via Admin API
     */
    async cancelTournament(apiKey, tournamentId) {
        const res = await fetch(`${API_BASE}/admin/tournaments/${tournamentId}`, {
            method: 'DELETE',
            headers: { 'X-API-Key': apiKey }
        });
        if (!res.ok) {
            const err = await res.json().catch(() => ({}));
            throw new Error(err.detail || `HTTP error ${res.status}`);
        }
        return await res.json();
    },

    /**
     * Fetch public players directory
     */
    async getPlayers() {
        try {
            const res = await fetch(`${API_BASE}/public/players`);
            if (!res.ok) throw new Error(`HTTP error ${res.status}`);
            return await res.json();
        } catch (err) {
            console.error('Failed to fetch public players:', err);
            return [];
        }
    },

    /**
     * Fetch public player profile
     */
    async getPlayerProfile(slug) {
        try {
            const res = await fetch(`${API_BASE}/public/players/${encodeURIComponent(slug)}`);
            if (!res.ok) throw new Error(`HTTP error ${res.status}`);
            return await res.json();
        } catch (err) {
            console.error(`Failed to fetch player profile ${slug}:`, err);
            return null;
        }
    },

    /**
     * Fetch public teams directory
     */
    async getTeams() {
        try {
            const res = await fetch(`${API_BASE}/public/teams`);
            if (!res.ok) throw new Error(`HTTP error ${res.status}`);
            return await res.json();
        } catch (err) {
            console.error('Failed to fetch public teams:', err);
            return [];
        }
    },

    /**
     * Fetch public team profile
     */
    async getTeamProfile(slug) {
        try {
            const res = await fetch(`${API_BASE}/public/teams/${encodeURIComponent(slug)}`);
            if (!res.ok) throw new Error(`HTTP error ${res.status}`);
            return await res.json();
        } catch (err) {
            console.error(`Failed to fetch team profile ${slug}:`, err);
            return null;
        }
    },

    /**
     * Fetch full user dashboard data
     */
    async getUserDashboard(userId) {
        try {
            const res = await fetch(`${API_BASE}/public/user/dashboard?user_id=${encodeURIComponent(userId)}`);
            if (!res.ok) throw new Error(`HTTP error ${res.status}`);
            return await res.json();
        } catch (err) {
            console.error('Failed to fetch user dashboard:', err);
            return null;
        }
    },

    /**
     * Open tournament registration via Admin API
     */
    async openRegistration(apiKey, tournamentId) {
        const res = await fetch(`${API_BASE}/admin/tournaments/${tournamentId}/open-registration`, {
            method: 'POST',
            headers: { 'X-API-Key': apiKey }
        });
        if (!res.ok) {
            const err = await res.json().catch(() => ({}));
            throw new Error(err.detail || `HTTP error ${res.status}`);
        }
        return await res.json();
    },

    /**
     * Close tournament registration via Admin API
     */
    async closeRegistration(apiKey, tournamentId) {
        const res = await fetch(`${API_BASE}/admin/tournaments/${tournamentId}/close-registration`, {
            method: 'POST',
            headers: { 'X-API-Key': apiKey }
        });
        if (!res.ok) {
            const err = await res.json().catch(() => ({}));
            throw new Error(err.detail || `HTTP error ${res.status}`);
        }
        return await res.json();
    },

    /**
     * Change tournament main status via Admin API
     */
    async setTournamentStatus(apiKey, tournamentId, status) {
        const res = await fetch(`${API_BASE}/admin/tournaments/${tournamentId}/status`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'X-API-Key': apiKey },
            body: JSON.stringify({ status })
        });
        if (!res.ok) {
            const err = await res.json().catch(() => ({}));
            throw new Error(err.detail || `HTTP error ${res.status}`);
        }
        return await res.json();
    },

    /**
     * Fetch audit log entries via Admin API
     */
    async getAuditLogs(apiKey) {
        const res = await fetch(`${API_BASE}/admin/audit-logs`, {
            headers: { 'X-API-Key': apiKey }
        });
        if (!res.ok) throw new Error(`HTTP error ${res.status}`);
        return await res.json();
    },

    /**
     * Generate bracket via Admin API
     */
    async generateBracket(apiKey, tournamentId) {
        const res = await fetch(`${API_BASE}/admin/tournaments/${tournamentId}/generate-bracket`, {
            method: 'POST',
            headers: { 'X-API-Key': apiKey }
        });
        if (!res.ok) {
            const err = await res.json().catch(() => ({}));
            throw new Error(err.detail || `HTTP error ${res.status}`);
        }
        return await res.json();
    },

    /**
     * Submit match result via Admin API
     */
    async submitMatchResult(apiKey, matchId, data) {
        const res = await fetch(`${API_BASE}/admin/matches/${matchId}/result`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'X-API-Key': apiKey },
            body: JSON.stringify(data)
        });
        if (!res.ok) {
            const err = await res.json().catch(() => ({}));
            throw new Error(err.detail || `HTTP error ${res.status}`);
        }
        return await res.json();
    },

    /**
     * Fetch tournament ruleset
     */
    async getTournamentRules(tournamentId) {
        try {
            const res = await fetch(`${API_BASE}/public/tournaments/${tournamentId}/rules`);
            if (!res.ok) throw new Error(`HTTP error ${res.status}`);
            return await res.json();
        } catch (err) {
            console.error(`Failed to fetch rules for tournament ${tournamentId}:`, err);
            return null;
        }
    },

    /**
     * Fetch match map veto state
     */
    async getMatchVetoState(matchId) {
        try {
            const res = await fetch(`${API_BASE}/public/matches/${matchId}/veto`);
            if (!res.ok) throw new Error(`HTTP error ${res.status}`);
            return await res.json();
        } catch (err) {
            console.error(`Failed to fetch veto state for match ${matchId}:`, err);
            return null;
        }
    },

    /**
     * Fetch live spectator hub matches
     */
    async getLiveMatches() {
        try {
            const res = await fetch(`${API_BASE}/public/live`);
            if (!res.ok) throw new Error(`HTTP error ${res.status}`);
            return await res.json();
        } catch (err) {
            console.error('Failed to fetch live spectator matches:', err);
            return [];
        }
    },

    /**
     * Fetch competitive leaderboard
     */
    async getLeaderboard(game = 'VALORANT') {
        try {
            const res = await fetch(`${API_BASE}/public/leaderboard?game=${encodeURIComponent(game)}`);
            if (!res.ok) throw new Error(`HTTP error ${res.status}`);
            return await res.json();
        } catch (err) {
            console.error('Failed to fetch leaderboard:', err);
            return { teams: [], players: [] };
        }
    },

    /**
     * Fetch competitive seasons list
     */
    async getSeasons() {
        try {
            const res = await fetch(`${API_BASE}/public/seasons`);
            if (!res.ok) throw new Error(`HTTP error ${res.status}`);
            return await res.json();
        } catch (err) {
            console.error('Failed to fetch seasons:', err);
            return [];
        }
    },

    /**
     * Fetch tournament economy & prize pool
     */
    async getTournamentEconomy(tournamentId) {
        try {
            const res = await fetch(`${API_BASE}/public/tournaments/${tournamentId}/economy`);
            if (!res.ok) throw new Error(`HTTP error ${res.status}`);
            return await res.json();
        } catch (err) {
            console.error(`Failed to fetch economy for tournament ${tournamentId}:`, err);
            return null;
        }
    },

    /**
     * Global platform search
     */
    async globalSearch(query) {
        try {
            const res = await fetch(`${API_BASE}/public/search?q=${encodeURIComponent(query)}`);
            if (!res.ok) throw new Error(`HTTP error ${res.status}`);
            return await res.json();
        } catch (err) {
            console.error(`Global search failed for '${query}':`, err);
            return { players: [], teams: [], tournaments: [], matches: [] };
        }
    },

    /**
     * Fetch user notifications
     */
    async getUserNotifications(userId) {
        try {
            const res = await fetch(`${API_BASE}/public/user/notifications?user_id=${encodeURIComponent(userId)}`);
            if (!res.ok) throw new Error(`HTTP error ${res.status}`);
            return await res.json();
        } catch (err) {
            console.error(`Failed to fetch notifications for ${userId}:`, err);
            return [];
        }
    }
};

window.Api = Api;

