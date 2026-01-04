// Global variables
let userRole = 'viewer'; 

// Initialize on page load
document.addEventListener('DOMContentLoaded', function() {
    initializeSettings();
});

/**
 * Initialize all settings
 */
function initializeSettings() {
    // Check user role and show appropriate sections
    checkUserRole();
    
    // Load data
    loadThresholds();
    loadDeviceStatus();
    loadNotificationSettings();
    
    // Setup auto-refresh
    setupAutoRefresh();
    
    console.log('Settings page initialized');
}

/**
 * Check user role and display appropriate sections
 */
function checkUserRole() {
    if (userRole === 'admin') {
        const userMgmtSection = document.getElementById('userManagementSection');
        if (userMgmtSection) {
            userMgmtSection.style.display = 'block';
            loadUsers();
        }
    }
}

/**
 * Load threshold settings from API
 */
async function loadThresholds() {
    try {
        const response = await fetch('/api/thresholds');
        const thresholds = await response.json();

        thresholds.forEach(threshold => {
            if (threshold.parameter === 'ph') {
                document.getElementById('phMin').value = threshold.min_value;
                document.getElementById('phMax').value = threshold.max_value;
            } else if (threshold.parameter === 'temperature') {
                document.getElementById('tempMin').value = threshold.min_value;
                document.getElementById('tempMax').value = threshold.max_value;
            } else if (threshold.parameter === 'tds') {
                document.getElementById('tdsMin').value = threshold.min_value;
                document.getElementById('tdsMax').value = threshold.max_value;
            }
        });
        
        console.log('Thresholds loaded successfully');
    } catch (error) {
        console.error('Error loading thresholds:', error);
        showNotification('Gagal memuat pengaturan threshold', 'error');
    }
}

/**
 * Save threshold settings
 */
async function saveThresholds() {
    // Validate inputs
    const phMin = parseFloat(document.getElementById('phMin').value);
    const phMax = parseFloat(document.getElementById('phMax').value);
    const tempMin = parseFloat(document.getElementById('tempMin').value);
    const tempMax = parseFloat(document.getElementById('tempMax').value);
    const tdsMin = parseFloat(document.getElementById('tdsMin').value);
    const tdsMax = parseFloat(document.getElementById('tdsMax').value);

    // Validation
    if (phMin >= phMax) {
        showNotification('pH minimum harus lebih kecil dari maksimum!', 'error');
        return;
    }
    if (tempMin >= tempMax) {
        showNotification('Suhu minimum harus lebih kecil dari maksimum!', 'error');
        return;
    }
    if (tdsMin >= tdsMax) {
        showNotification('TDS minimum harus lebih kecil dari maksimum!', 'error');
        return;
    }

    const thresholds = [
        {
            parameter: 'ph',
            min_value: phMin,
            max_value: phMax,
            unit: 'pH'
        },
        {
            parameter: 'temperature',
            min_value: tempMin,
            max_value: tempMax,
            unit: '°C'
        },
        {
            parameter: 'tds',
            min_value: tdsMin,
            max_value: tdsMax,
            unit: 'ppm'
        }
    ];

    try {
        // Show loading
        showLoading('Menyimpan pengaturan...');

        for (const threshold of thresholds) {
            const response = await fetch('/api/thresholds', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(threshold)
            });

            if (!response.ok) {
                throw new Error('Failed to save threshold');
            }
        }

        hideLoading();
        showNotification('✓ Pengaturan threshold berhasil disimpan!', 'success');
        
        // Reload to show updated values
        setTimeout(() => loadThresholds(), 1000);
        
    } catch (error) {
        hideLoading();
        console.error('Error saving thresholds:', error);
        showNotification('✗ Gagal menyimpan pengaturan', 'error');
    }
}

/**
 * Reset thresholds to default values
 */
function resetThresholds() {
    if (confirm('Reset threshold ke nilai default (sesuai Permenkes)?')) {
        document.getElementById('phMin').value = 6.0;
        document.getElementById('phMax').value = 9.0;
        document.getElementById('tempMin').value = 0;
        document.getElementById('tempMax').value = 30;
        document.getElementById('tdsMin').value = 0;
        document.getElementById('tdsMax').value = 2000;
        showNotification('Threshold direset ke nilai default', 'info');
    }
}

/**
 * Load device status
 */
async function loadDeviceStatus() {
    try {
        const response = await fetch('/api/device/status');
        const device = await response.json();
        
        // Update UI
        document.getElementById('deviceId').textContent = device.device_name || 'ESP32-IPAL-01';
        
        const statusEl = document.getElementById('deviceStatus');
        if (device.status === 'online') {
            statusEl.textContent = '🟢 Online';
            statusEl.style.color = '#10b981';
        } else {
            statusEl.textContent = '🔴 Offline';
            statusEl.style.color = '#ef4444';
        }
        
        document.getElementById('signalStrength').textContent = 
            device.signal_strength ? device.signal_strength + '%' : '-';
        
        const lastSeen = device.last_seen ? 
            new Date(device.last_seen).toLocaleString('id-ID') : 
            'Just now';
        document.getElementById('lastSeen').textContent = lastSeen;
        
    } catch (error) {
        console.error('Error loading device status:', error);
        document.getElementById('deviceStatus').textContent = '❓ Unknown';
    }
}

/**
 * Load notification settings from localStorage
 */
function loadNotificationSettings() {
    const emailNotif = localStorage.getItem('emailNotif') !== 'false';
    const notifEmail = localStorage.getItem('notifEmail') || '';
    const whatsappNotif = localStorage.getItem('whatsappNotif') === 'true';
    const whatsappNumber = localStorage.getItem('whatsappNumber') || '';
    
    document.getElementById('emailNotif').checked = emailNotif;
    document.getElementById('notifEmail').value = notifEmail;
    document.getElementById('whatsappNotif').checked = whatsappNotif;
    document.getElementById('whatsappNumber').value = whatsappNumber;
    
    console.log('Notification settings loaded');
}

/**
 * Save notification settings
 */
function saveNotificationSettings() {
    const emailNotif = document.getElementById('emailNotif').checked;
    const notifEmail = document.getElementById('notifEmail').value;
    const whatsappNotif = document.getElementById('whatsappNotif').checked;
    const whatsappNumber = document.getElementById('whatsappNumber').value;

    // Validate email if enabled
    if (emailNotif && !notifEmail) {
        showNotification('Harap masukkan email penerima!', 'error');
        return;
    }

    // Validate email format
    if (notifEmail && !isValidEmail(notifEmail)) {
        showNotification('Format email tidak valid!', 'error');
        return;
    }

    // Save to localStorage
    localStorage.setItem('emailNotif', emailNotif);
    localStorage.setItem('notifEmail', notifEmail);
    localStorage.setItem('whatsappNotif', whatsappNotif);
    localStorage.setItem('whatsappNumber', whatsappNumber);

    showNotification('✓ Pengaturan notifikasi berhasil disimpan!', 'success');
}

/**
 * Load users list (admin only)
 */
async function loadUsers() {
    try {
        // This would fetch from API in production
        const tbody = document.getElementById('userTableBody');
        
        // For now, show placeholder
        tbody.innerHTML = `
            <tr>
                <td>admin</td>
                <td>admin@rsmatapwt.com</td>
                <td><span class="status-badge badge-normal">Admin</span></td>
                <td>
                    <button class="btn btn-secondary" style="padding: 0.5rem 1rem;" onclick="editUser(1)">
                        ✏️ Edit
                    </button>
                </td>
            </tr>
        `;
        
        console.log('Users loaded');
    } catch (error) {
        console.error('Error loading users:', error);
    }
}

/**
 * Show add user modal
 */
function showAddUserModal() {
    showNotification('Fitur tambah user akan segera tersedia!', 'info');
    // TODO: Implement user add modal
}

/**
 * Edit user
 */
function editUser(userId) {
    showNotification('Fitur edit user akan segera tersedia!', 'info');
    // TODO: Implement user edit modal
}

/**
 * Export database
 */
async function exportDatabase() {
    if (confirm('Export database ke file SQL?')) {
        showNotification('Fitur export database akan segera tersedia!', 'info');
        // TODO: Implement database export
    }
}

/**
 * Clear old data (>90 days)
 */
async function clearOldData() {
    if (confirm('PERINGATAN: Apakah Anda yakin ingin menghapus semua data yang lebih dari 90 hari?\n\nAksi ini TIDAK DAPAT DIBATALKAN!')) {
        showNotification('Fitur ini akan segera tersedia!', 'info');
        // TODO: Implement data cleanup
    }
}

/**
 * Setup auto-refresh for device status
 */
function setupAutoRefresh() {
    // Refresh device status every 30 seconds
    setInterval(loadDeviceStatus, 30000);
    console.log('Auto-refresh enabled (30s interval)');
}

/**
 * Validate email format
 */
function isValidEmail(email) {
    const re = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    return re.test(email);
}

/**
 * Show notification
 */
function showNotification(message, type = 'info') {
    // For now, use alert
    // TODO: Implement custom notification component
    alert(message);
}

/**
 * Show loading indicator
 */
function showLoading(message = 'Loading...') {
    // TODO: Implement loading overlay
    console.log('Loading:', message);
}

/**
 * Hide loading indicator
 */
function hideLoading() {
    // TODO: Implement loading overlay removal
    console.log('Loading complete');
}

/**
 * Set user role (called by backend template)
 */
function setUserRole(role) {
    userRole = role;
    checkUserRole();
}

// Export functions for use in other scripts
window.settingsApp = {
    setUserRole,
    loadThresholds,
    saveThresholds,
    resetThresholds,
    loadDeviceStatus,
    saveNotificationSettings,
    exportDatabase,
    clearOldData
};