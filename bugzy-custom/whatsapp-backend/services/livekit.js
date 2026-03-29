/**
 * livekit.js — LiveKit Room Service client
 *
 * Provides helpers to create, list, and delete LiveKit rooms via the
 * LiveKit Server SDK.  Adapted from bugzy-voice/app/whatsapp-backend/services/livekit.js
 */

const { RoomServiceClient, Room } = require('livekit-server-sdk');
const logger = require('../utils/logger');

class LiveKitService {
    constructor() {
        const url = process.env.LIVEKIT_URL;
        const key = process.env.LIVEKIT_API_KEY;
        const secret = process.env.LIVEKIT_API_SECRET;

        if (!url || !key || !secret) {
            logger.error('LiveKit credentials missing — check LIVEKIT_URL / LIVEKIT_API_KEY / LIVEKIT_API_SECRET');
        }

        this.client = new RoomServiceClient(url, key, secret);
        logger.info('LiveKitService initialised', { url });
    }

    /**
     * Create a LiveKit room for an incoming call.
     * @param {string} roomName
     * @param {number} [emptyTimeoutSecs=60]
     */
    async createRoom(roomName, emptyTimeoutSecs = 60) {
        try {
            const room = await this.client.createRoom({
                name: roomName,
                emptyTimeout: emptyTimeoutSecs,
                maxParticipants: 10,
            });
            logger.info('LiveKit room created', { roomName: room.name, sid: room.sid });
            return room;
        } catch (err) {
            logger.error('Failed to create LiveKit room', err);
            throw err;
        }
    }

    /**
     * Delete a LiveKit room by name.
     * @param {string} roomName
     */
    async deleteRoom(roomName) {
        try {
            await this.client.deleteRoom(roomName);
            logger.info('LiveKit room deleted', { roomName });
        } catch (err) {
            logger.error('Failed to delete LiveKit room', { roomName, err });
        }
    }

    /**
     * List all active rooms.
     */
    async listRooms() {
        try {
            const rooms = await this.client.listRooms();
            return rooms;
        } catch (err) {
            logger.error('Failed to list LiveKit rooms', err);
            throw err;
        }
    }
}

module.exports = new LiveKitService();
