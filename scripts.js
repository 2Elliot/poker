// Game State
const MIN_PLAYERS = 2;
const MAX_PLAYERS = 10;
const STARTING_CHIPS = 1000;

const state = {
    availableBots: [
        { id: 'aggressive-bot', name: 'Aggressive Bot', type: 'Premade' },
        { id: 'conservative-bot', name: 'Conservative Bot', type: 'Premade' },
        { id: 'random-bot', name: 'Random Bot', type: 'Premade' },
        { id: 'bluffer-bot', name: 'Bluffer Bot', type: 'Premade' },
    ],
    tablePlayers: [],
    isPlaying: false,
    isPaused: false,
    speed: 1,
    gameInterval: null,
    deck: [],
    communityCards: [],
    pot: 0,
    currentBet: 0,
    dealerPosition: 0,
    currentPlayerIndex: 0,
    gamePhase: 'waiting', // waiting, preflop, flop, turn, river, showdown
    statistics: {},
    gamesPlayed: 0,
    chipHistory: {}
};

// Initialize
function init() {
    renderBotList();
    updateStatus();
}

// Render bot list
function renderBotList() {
    const botList = document.getElementById('botList');
    botList.innerHTML = state.availableBots.map(bot => `
                <div class="bot-item" onclick="addBotToTable('${bot.id}')">
                    <div class="bot-name">${bot.name}</div>
                    <div class="bot-type">${bot.type}</div>
                </div>
            `).join('');
}

// Add bot to table
function addBotToTable(botId) {
    if (state.tablePlayers.length >= MAX_PLAYERS) {
        alert(`Maximum ${MAX_PLAYERS} players allowed`);
        return;
    }

    const bot = state.availableBots.find(b => b.id === botId);
    const playerId = `${botId}-${Date.now()}`;

    // Check if we need a unique identifier
    const sameNameCount = state.tablePlayers.filter(p => p.botId === botId).length;
    const displayName = sameNameCount > 0 ? `${bot.name} #${sameNameCount + 1}` : bot.name;

    const player = {
        id: playerId,
        botId: botId,
        name: displayName,
        chips: STARTING_CHIPS,
        bet: 0,
        cards: [],
        folded: false,
        allIn: false
    };

    state.tablePlayers.push(player);

    // Initialize stats for this player
    if (!state.statistics[playerId]) {
        state.statistics[playerId] = {
            gamesPlayed: 0,
            wins: 0,
            winRate: 0,
            totalChipsWon: 0,
            totalChipsLost: 0
        };
        // Initialize chip history with starting point
        state.chipHistory[playerId] = [{
            game: 0,
            chips: STARTING_CHIPS
        }];
    }

    logToConsole(`${displayName} joined the table`, 'event-action');
    renderTable();
    updateStatus();
}

// Clear table
function clearTable() {
    if (state.isPlaying && !confirm('Game in progress. Are you sure?')) {
        return;
    }

    state.tablePlayers = [];
    state.isPlaying = false;
    state.isPaused = false;
    stopGameLoop();
    logToConsole('Table cleared', 'event-action');
    renderTable();
    updateStatus();
}

// Console functions
function logToConsole(message, className = '') {
    const consoleContent = document.getElementById('consoleContent');
    const line = document.createElement('div');
    line.className = `console-line ${className}`;
    const timestamp = new Date().toLocaleTimeString();
    line.textContent = `[${timestamp}] ${message}`;
    consoleContent.appendChild(line);
    consoleContent.scrollTop = consoleContent.scrollHeight;
}

function clearConsole() {
    document.getElementById('consoleContent').innerHTML = '';
}

// Render table
function renderTable() {
    const emptyMessage = document.getElementById('emptyMessage');
    const pokerTable = document.getElementById('pokerTable');

    if (state.tablePlayers.length === 0) {
        emptyMessage.style.display = 'block';
        pokerTable.style.display = 'none';
        return;
    }

    emptyMessage.style.display = 'none';
    pokerTable.style.display = 'block';

    // Render players
    for (let i = 0; i < MAX_PLAYERS; i++) {
        const seat = document.querySelector(`[data-seat="${i}"]`);
        const player = state.tablePlayers[i];

        if (player) {
            seat.classList.remove('empty');
            seat.innerHTML = `
                        <div class="player-info ${i === state.currentPlayerIndex ? 'active' : ''} ${player.folded ? 'folded' : ''}">
                            <div class="player-name">${player.name}</div>
                            <div class="player-chips">$${player.chips}</div>
                            ${player.bet > 0 ? `<div class="player-bet">Bet: $${player.bet}</div>` : ''}
                        </div>
                        <div class="player-cards pos-${i}">
                            ${renderPlayerCards(player)}
                        </div>
                    `;
        } else {
            seat.classList.add('empty');
            seat.innerHTML = '';
        }
    }

    // Render community cards
    const communityCardsEl = document.getElementById('communityCards');
    communityCardsEl.innerHTML = state.communityCards.map(card => renderCard(card)).join('');

    // Update pot
    document.getElementById('potAmount').textContent = `$${state.pot}`;
}

// Render player cards
function renderPlayerCards(player) {
    if (player.cards.length === 0) {
        return '';
    }
    return player.cards.map(card => renderCard(card)).join('');
}

// Render a card
function renderCard(card) {
    if (!card) return '';

    const suit = card.suit;
    const value = card.value;
    const color = (suit === '♥' || suit === '♦') ? 'red' : 'black';

    return `<div class="card ${color}">${value}${suit}</div>`;
}

// Create deck
function createDeck() {
    const suits = ['♠', '♥', '♦', '♣'];
    const values = ['2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K', 'A'];
    const deck = [];

    for (let suit of suits) {
        for (let value of values) {
            deck.push({ suit, value });
        }
    }

    // Shuffle
    for (let i = deck.length - 1; i > 0; i--) {
        const j = Math.floor(Math.random() * (i + 1));
        [deck[i], deck[j]] = [deck[j], deck[i]];
    }

    return deck;
}

// Start new game
function startNewGame() {
    if (state.tablePlayers.length < MIN_PLAYERS) {
        alert(`Need at least ${MIN_PLAYERS} players to start`);
        return;
    }

    logToConsole('=== Starting new game ===', 'event-phase');

    // Reset game state
    state.deck = createDeck();
    state.communityCards = [];
    state.pot = 0;
    state.currentBet = 0;
    state.gamePhase = 'preflop';
    state.currentPlayerIndex = (state.dealerPosition + 1) % state.tablePlayers.length;

    // Reset players
    state.tablePlayers.forEach(player => {
        player.cards = [];
        player.bet = 0;
        player.folded = false;
        player.allIn = false;
    });

    // Deal cards
    dealCards();
    renderTable();
    updateStatus();
}

// Deal cards
function dealCards() {
    // Deal 2 cards to each player
    for (let i = 0; i < 2; i++) {
        state.tablePlayers.forEach(player => {
            if (!player.folded) {
                player.cards.push(state.deck.pop());
            }
        });
    }

    // Log dealt cards
    state.tablePlayers.forEach(player => {
        const cardStr = player.cards.map(c => `${c.value}${c.suit}`).join(', ');
        logToConsole(`${player.name} dealt: ${cardStr}`, 'event-deal');
    });
}

// Game step (one action)
function stepGame() {
    if (state.tablePlayers.length < MIN_PLAYERS) {
        return;
    }

    if (state.gamePhase === 'waiting') {
        startNewGame();
        return;
    }

    // Handle current player action
    const currentPlayer = state.tablePlayers[state.currentPlayerIndex];

    if (!currentPlayer.folded) {
        // HOOK: This is where you'll call your bot logic
        // For now, simulate a random action
        const action = simulateBotAction(currentPlayer);
        executePlayerAction(currentPlayer, action);
    }

    // Move to next player
    state.currentPlayerIndex = (state.currentPlayerIndex + 1) % state.tablePlayers.length;

    // Check if betting round is complete
    if (isBettingRoundComplete()) {
        advanceGamePhase();
    }

    renderTable();
    updateStatus();
}

// Simulate bot action (placeholder for your bot logic)
function simulateBotAction(player) {
    // HOOK: Replace this with actual bot decision making
    const actions = ['call', 'raise', 'fold'];
    const weights = [0.5, 0.3, 0.2];

    const rand = Math.random();
    let sum = 0;

    for (let i = 0; i < actions.length; i++) {
        sum += weights[i];
        if (rand < sum) {
            if (actions[i] === 'raise') {
                return { type: 'raise', amount: Math.min(50, player.chips) };
            }
            return { type: actions[i] };
        }
    }

    return { type: 'call' };
}

// Execute player action
function executePlayerAction(player, action) {
    switch (action.type) {
        case 'fold':
            player.folded = true;
            logToConsole(`${player.name} folds`, 'event-action');
            break;
        case 'call':
            const callAmount = Math.min(state.currentBet - player.bet, player.chips);
            player.chips -= callAmount;
            player.bet += callAmount;
            state.pot += callAmount;
            logToConsole(`${player.name} calls ${callAmount} (pot: ${state.pot})`, 'event-action');
            break;
        case 'raise':
            const raiseAmount = Math.min(action.amount, player.chips);
            player.chips -= raiseAmount;
            player.bet += raiseAmount;
            state.pot += raiseAmount;
            state.currentBet = player.bet;
            logToConsole(`${player.name} raises ${raiseAmount} (pot: ${state.pot})`, 'event-action');
            break;
    }
}

// Check if betting round is complete
function isBettingRoundComplete() {
    const activePlayers = state.tablePlayers.filter(p => !p.folded);
    if (activePlayers.length === 1) return true;

    return activePlayers.every(p => p.bet === state.currentBet || p.chips === 0);
}

// Advance game phase
function advanceGamePhase() {
    // Reset bets for next round
    state.tablePlayers.forEach(p => p.bet = 0);
    state.currentBet = 0;
    state.currentPlayerIndex = (state.dealerPosition + 1) % state.tablePlayers.length;

    switch (state.gamePhase) {
        case 'preflop':
            // Deal flop (3 cards)
            const flop = [state.deck.pop(), state.deck.pop(), state.deck.pop()];
            state.communityCards.push(...flop);
            state.gamePhase = 'flop';
            const flopStr = flop.map(c => `${c.value}${c.suit}`).join(', ');
            logToConsole(`FLOP: ${flopStr}`, 'event-phase');
            break;
        case 'flop':
            // Deal turn (1 card)
            const turn = state.deck.pop();
            state.communityCards.push(turn);
            state.gamePhase = 'turn';
            logToConsole(`TURN: ${turn.value}${turn.suit}`, 'event-phase');
            break;
        case 'turn':
            // Deal river (1 card)
            const river = state.deck.pop();
            state.communityCards.push(river);
            state.gamePhase = 'river';
            logToConsole(`RIVER: ${river.value}${river.suit}`, 'event-phase');
            break;
        case 'river':
            // Showdown
            state.gamePhase = 'showdown';
            logToConsole('SHOWDOWN', 'event-phase');
            determineWinner();
            break;
        case 'showdown':
            // Start new game
            state.dealerPosition = (state.dealerPosition + 1) % state.tablePlayers.length;
            state.gamesPlayed++;
            updateStatistics();
            startNewGame();
            break;
    }
}

// Determine winner (simplified)
function determineWinner() {
    const activePlayers = state.tablePlayers.filter(p => !p.folded);

    if (activePlayers.length === 1) {
        activePlayers[0].chips += state.pot;
        logToConsole(`${activePlayers[0].name} wins ${state.pot} (everyone else folded)`, 'event-winner');
        return;
    }

    // HOOK: Implement proper poker hand evaluation here
    // For now, randomly select a winner
    const winner = activePlayers[Math.floor(Math.random() * activePlayers.length)];
    winner.chips += state.pot;
    logToConsole(`${winner.name} wins ${state.pot}`, 'event-winner');
}

// Update statistics
function updateStatistics() {
    state.tablePlayers.forEach(player => {
        const stats = state.statistics[player.id];
        const history = state.chipHistory[player.id];

        // Get chips from previous game
        const prevChips = history.length > 0 ? history[history.length - 1].chips : STARTING_CHIPS;
        const chipDelta = player.chips - prevChips;

        stats.gamesPlayed++;

        // Record chip history (current chips at this game number)
        history.push({
            game: state.gamesPlayed,
            chips: player.chips
        });

        // Track if player won chips this game
        // HOOK: This could be more accurate with proper hand winner tracking
        if (chipDelta > 0) {
            stats.wins++;
            stats.totalChipsWon += chipDelta;
        } else if (chipDelta < 0) {
            stats.totalChipsLost += Math.abs(chipDelta);
        }

        stats.winRate = stats.gamesPlayed > 0 ? (stats.wins / stats.gamesPlayed * 100).toFixed(1) : 0;
    });

    renderStatistics();
}

// Render statistics
function renderStatistics() {
    const statsGrid = document.getElementById('statsGrid');

    let html = '';
    state.tablePlayers.forEach(player => {
        const stats = state.statistics[player.id];
        html += `
                    <div class="stat-card">
                        <h3>${player.name}</h3>
                        <div class="stat-item">
                            <span class="stat-label">Games Played</span>
                            <span class="stat-value">${stats.gamesPlayed}</span>
                        </div>
                        <div class="stat-item">
                            <span class="stat-label">Wins</span>
                            <span class="stat-value">${stats.wins}</span>
                        </div>
                        <div class="stat-item">
                            <span class="stat-label">Win Rate</span>
                            <span class="stat-value">${stats.winRate}%</span>
                        </div>
                        <div class="stat-item">
                            <span class="stat-label">Current Chips</span>
                            <span class="stat-value">${player.chips}</span>
                        </div>
                        <div class="stat-item">
                            <span class="stat-label">Total Won</span>
                            <span class="stat-value" style="color: #4a90e2;">+${stats.totalChipsWon}</span>
                        </div>
                        <div class="stat-item">
                            <span class="stat-label">Total Lost</span>
                            <span class="stat-value" style="color: #e24a4a;">-${stats.totalChipsLost}</span>
                        </div>
                    </div>
                `;
    });

    statsGrid.innerHTML = html || '<p style="color: #666;">Add players to see statistics</p>';

    // Draw chips over time chart
    drawChipsChart();
}

// Draw chips over time chart
function drawChipsChart() {
    const canvas = document.getElementById('chipsChart');
    const ctx = canvas.getContext('2d');

    // Clear canvas
    ctx.clearRect(0, 0, canvas.width, canvas.height);

    if (state.gamesPlayed === 0 || state.tablePlayers.length === 0) {
        ctx.fillStyle = '#666';
        ctx.font = '14px Arial';
        ctx.textAlign = 'center';
        ctx.fillText('Play games to see chip progression', canvas.width / 2, canvas.height / 2);
        return;
    }

    const padding = 40;
    const chartWidth = canvas.width - padding * 2;
    const chartHeight = canvas.height - padding * 2;

    // Find max chips and games for scaling
    let maxChips = STARTING_CHIPS;
    let maxGames = state.gamesPlayed;

    state.tablePlayers.forEach(player => {
        const history = state.chipHistory[player.id];
        history.forEach(point => {
            maxChips = Math.max(maxChips, point.chips);
        });
    });

    // Draw axes
    ctx.strokeStyle = '#444';
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(padding, padding);
    ctx.lineTo(padding, canvas.height - padding);
    ctx.lineTo(canvas.width - padding, canvas.height - padding);
    ctx.stroke();

    // Draw grid lines
    ctx.strokeStyle = '#333';
    ctx.lineWidth = 0.5;
    for (let i = 0; i <= 5; i++) {
        const y = padding + (chartHeight / 5) * i;
        ctx.beginPath();
        ctx.moveTo(padding, y);
        ctx.lineTo(canvas.width - padding, y);
        ctx.stroke();

        // Y-axis labels
        const chipValue = Math.round(maxChips - (maxChips / 5) * i);
        ctx.fillStyle = '#888';
        ctx.font = '10px Arial';
        ctx.textAlign = 'right';
        ctx.fillText(`${chipValue}`, padding - 5, y + 4);
    }

    // X-axis labels
    ctx.fillStyle = '#888';
    ctx.font = '10px Arial';
    ctx.textAlign = 'center';
    for (let i = 0; i <= Math.min(maxGames, 10); i++) {
        const x = padding + (chartWidth / Math.min(maxGames, 10)) * i;
        const gameNum = Math.round((maxGames / Math.min(maxGames, 10)) * i);
        ctx.fillText(gameNum, x, canvas.height - padding + 15);
    }

    // Draw lines for each player
    const colors = ['#4a90e2', '#e24a4a', '#5ac', '#f90', '#9c3', '#c6c', '#fc3', '#6cf', '#f6c'];

    state.tablePlayers.forEach((player, idx) => {
        const history = state.chipHistory[player.id];
        if (history.length === 0) return;

        ctx.strokeStyle = colors[idx % colors.length];
        ctx.lineWidth = 2;
        ctx.beginPath();

        history.forEach((point, i) => {
            const x = padding + (chartWidth / maxGames) * point.game;
            const y = canvas.height - padding - (chartHeight * point.chips / maxChips);

            if (i === 0) {
                ctx.moveTo(x, y);
            } else {
                ctx.lineTo(x, y);
            }
        });

        ctx.stroke();

        // Draw legend
        const legendX = canvas.width - padding - 150;
        const legendY = padding + 20 + (idx * 20);
        ctx.fillStyle = colors[idx % colors.length];
        ctx.fillRect(legendX, legendY - 6, 12, 12);
        ctx.fillStyle = '#e0e0e0';
        ctx.font = '11px Arial';
        ctx.textAlign = 'left';
        ctx.fillText(player.name, legendX + 18, legendY + 4);
    });

    // Chart title
    ctx.fillStyle = '#4a90e2';
    ctx.font = 'bold 12px Arial';
    ctx.textAlign = 'left';
    ctx.fillText('Games', canvas.width / 2 - 20, canvas.height - 5);

    ctx.save();
    ctx.translate(15, canvas.height / 2);
    ctx.rotate(-Math.PI / 2);
    ctx.fillText('Chips', 0, 0);
    ctx.restore();
}

// Toggle play/pause
function togglePlay() {
    if (state.tablePlayers.length < MIN_PLAYERS) {
        alert(`Need at least ${MIN_PLAYERS} players to start`);
        return;
    }

    state.isPlaying = !state.isPlaying;

    const playBtn = document.getElementById('playBtn');
    if (state.isPlaying) {
        playBtn.textContent = 'Pause';
        startGameLoop();
    } else {
        playBtn.textContent = 'Play';
        stopGameLoop();
    }
}

// Start game loop
function startGameLoop() {
    const interval = 1000 / state.speed;
    state.gameInterval = setInterval(stepGame, interval);
}

// Stop game loop
function stopGameLoop() {
    if (state.gameInterval) {
        clearInterval(state.gameInterval);
        state.gameInterval = null;
    }
}

// Change speed
function changeSpeed(delta) {
    const speeds = [0.25, 0.5, 1, 2, 4, 8, 32, 64, 256];
    let currentIndex = speeds.indexOf(state.speed);
    currentIndex = Math.max(0, Math.min(speeds.length - 1, currentIndex + delta));
    state.speed = speeds[currentIndex];

    document.getElementById('speedValue').textContent = state.speed + 'x';

    if (state.isPlaying) {
        stopGameLoop();
        startGameLoop();
    }
}

// Reset game
function resetGame() {
    if (state.isPlaying && !confirm('Game in progress. Are you sure?')) {
        return;
    }

    state.isPlaying = false;
    stopGameLoop();

    // Reset chips
    state.tablePlayers.forEach(player => {
        player.chips = STARTING_CHIPS;
        player.cards = [];
        player.bet = 0;
        player.folded = false;
    });

    state.gamePhase = 'waiting';
    state.communityCards = [];
    state.pot = 0;
    state.dealerPosition = 0;

    logToConsole('Game reset - all chips restored to starting amount', 'event-action');
    document.getElementById('playBtn').textContent = 'Play';
    renderTable();
    updateStatus();
}

// Update status
function updateStatus() {
    document.getElementById('playerCount').textContent = state.tablePlayers.length;
    document.getElementById('gamesPlayed').textContent = state.gamesPlayed;

    let status = 'Ready';
    if (state.isPlaying) {
        status = `Playing - ${state.gamePhase}`;
    } else if (state.tablePlayers.length < MIN_PLAYERS) {
        status = `Need ${MIN_PLAYERS - state.tablePlayers.length} more player(s)`;
    }
    document.getElementById('gameStatus').textContent = status;
}

// Switch tabs
function switchTab(tab) {
    document.querySelectorAll('.nav-tab').forEach(t => t.classList.remove('active'));
    document.querySelectorAll('.tab-content').forEach(t => t.classList.remove('active'));

    if (tab === 'game') {
        document.querySelectorAll('.nav-tab')[0].classList.add('active');
        document.getElementById('gameTab').classList.add('active');
    } else {
        document.querySelectorAll('.nav-tab')[1].classList.add('active');
        document.getElementById('statsTab').classList.add('active');
        renderStatistics();
    }
}

// Initialize on load
init();
logToConsole('Poker tournament system initialized', 'event-phase');
