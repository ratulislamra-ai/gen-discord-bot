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
        try {
            const res = await fetch(`${API_BASE}/admin/stats`, {
                headers: { 'X-API-Key': apiKey }
            });
            if (!res.ok) throw new Error(`HTTP error ${res.status}`);
            return await res.json();
        } catch (err) {
            console.error('Failed to fetch admin stats:', err);
            throw err;
        }
    }
};

window.Api = Api;
