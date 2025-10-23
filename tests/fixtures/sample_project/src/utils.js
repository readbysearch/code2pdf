// Utility functions for the sample project

/**
 * Format a date to a readable string
 * @param {Date} date - The date to format
 * @returns {string} Formatted date string
 */
function formatDate(date) {
    return date.toLocaleDateString('en-US', {
        year: 'numeric',
        month: 'long',
        day: 'numeric'
    });
}

/**
 * Generate a random ID
 * @returns {string} Random ID string
 */
function generateId() {
    return Math.random().toString(36).substr(2, 9);
}

module.exports = {
    formatDate,
    generateId
};