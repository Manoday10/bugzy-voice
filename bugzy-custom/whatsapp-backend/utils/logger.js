const fs = require('fs');
const path = require('path');

const logFile = path.join(__dirname, '../server.log');

const logToFile = (level, msg, meta) => {
    const timestamp = new Date().toISOString();
    const safeMeta = meta instanceof Error ? { message: meta.message, stack: meta.stack } : (meta || {});
    const logEntry = `[${timestamp}] [${level}] ${msg} ${JSON.stringify(safeMeta)}\n`;
    try {
        fs.appendFileSync(logFile, logEntry);
    } catch (e) {
        console.error('Failed to write to log file', e);
    }
};

const logger = {
    info: (msg, meta = {}) => {
        console.log(`[${new Date().toISOString()}] [INFO] ${msg}`, meta);
        logToFile('INFO', msg, meta);
    },
    error: (msg, error = {}) => {
        console.error(`[${new Date().toISOString()}] [ERROR] ${msg}`, error);
        logToFile('ERROR', msg, error);
    },
    warn: (msg, meta = {}) => {
        console.warn(`[${new Date().toISOString()}] [WARN] ${msg}`, meta);
        logToFile('WARN', msg, meta);
    },
    debug: (msg, meta = {}) => {
        logToFile('DEBUG', msg, meta);
        if (process.env.DEBUG) {
            console.debug(`[${new Date().toISOString()}] [DEBUG] ${msg}`, meta);
        }
    }
};

module.exports = logger;
