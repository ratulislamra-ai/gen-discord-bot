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
        try {
            const res = await fetch(`${API_BASE}/public/tournaments/${encodeURIComponent(slug)}`);
            if (!res.ok) throw new Error(`HTTP error ${res.status}`);
            return await res.json();
        } catch (err) {
            console.error(`Failed to fetch tournament ${slug}:`, err);
            return null;
        }
    },

    /**
     * Fetch approved teams for a specific tournament
     */
    async getApprovedTeams(tournamentSlug) {
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
    }
};

window.Api = Api;

