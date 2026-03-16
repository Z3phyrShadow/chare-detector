const formatTime = (seconds) => {
    if (isNaN(seconds) || seconds === null) return "0s";
    if (seconds < 60) return `${Math.floor(seconds)}s`;
    
    const h = Math.floor(seconds / 3600);
    const m = Math.floor((seconds % 3600) / 60);
    const s = Math.floor(seconds % 60);

    if (h > 0) return `${h}h ${m}m ${s}s`;
    return `${m}m ${s}s`;
};

const formatTimer = (seconds) => {
    if (isNaN(seconds) || seconds === null) return "00:00:00";
    const h = Math.floor(seconds / 3600).toString().padStart(2, '0');
    const m = Math.floor((seconds % 3600) / 60).toString().padStart(2, '0');
    const s = Math.floor(seconds % 60).toString().padStart(2, '0');
    return `${h}:${m}:${s}`;
};

const formatDate = (dateString) => {
    if (!dateString) return "Never";
    const d = new Date(dateString);
    return isNaN(d) ? "Never" : d.toLocaleString();
};

const updateUI = async () => {
    try {
        // Fetch Status
        const statusRes = await fetch('/api/status');
        const statusData = await statusRes.json();

        const onlineDot = document.getElementById('online-dot');
        const onlineText = document.getElementById('online-text');
        const afkCard = document.getElementById('afk-card');
        const afkStatusDisplay = document.getElementById('afk-status-display');
        const afkTimer = document.getElementById('afk-timer');

        if (statusData.online) {
            onlineDot.className = 'dot online';
            onlineText.textContent = 'STREAM ONLINE';
            
            if (statusData.state === 'AFK') {
                afkCard.className = 'card main-status afk';
                afkStatusDisplay.textContent = 'AWAY FROM KEYBOARD';
                afkTimer.textContent = formatTimer(statusData.current_afk_duration);
            } else if (statusData.state === 'NO_CAM') {
                afkCard.className = 'card main-status no-cam';
                afkStatusDisplay.textContent = 'NO CAMERA';
                afkTimer.textContent = '00:00:00';
            } else {
                afkCard.className = 'card main-status present';
                afkStatusDisplay.textContent = 'PRESENT';
                afkTimer.textContent = '00:00:00';
            }
            
        } else {
            onlineDot.className = 'dot offline';
            onlineText.textContent = 'STREAM OFFLINE';
            
            afkCard.className = 'card main-status offline-card';
            afkStatusDisplay.textContent = 'OFFLINE';
            afkTimer.textContent = '00:00:00';
        }

        // Fetch Stats
        const statsRes = await fetch('/api/stats');
        const statsData = await statsRes.json();

        document.getElementById('channel-name').textContent = statsData.channel.toUpperCase() || 'CHANNEL';
        document.getElementById('afk-this-stream').textContent = formatTime(statsData.afk_this_stream);
        document.getElementById('afk-this-month').textContent = formatTime(statsData.afk_this_month);
        document.getElementById('last-stream').textContent = formatDate(statsData.last_stream);

        // Update debug image cache buster
        const debugImg = document.getElementById('debug-image');
        if (debugImg) {
            debugImg.src = `/debug.jpg?t=${new Date().getTime()}`;
        }

    } catch (error) {
        console.error("Error fetching data:", error);
    }
};

// Initial update
updateUI();

// Refresh every 5 seconds
setInterval(updateUI, 5000);
