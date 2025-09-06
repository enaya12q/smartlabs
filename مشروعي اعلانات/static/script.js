let currentUser = null; // Stores user data after Telegram login

// Function to handle Telegram authentication
function onTelegramAuth(user) {
    console.log("Telegram User Data:", user);
    // In a real application, you would send this user data to your backend for verification and session management.
    // For now, we'll simulate a successful login.

    currentUser = {
        id: user.id,
        first_name: user.first_name,
        last_name: user.last_name,
        username: user.username,
        photo_url: user.photo_url,
        auth_date: user.auth_date,
        hash: user.hash,
        earnings: 0.0000,
        adsViewed: 0,
        referralLink: `https://smartcoinlabs.com/?ref=${user.id}` // Placeholder
    };

    // Simulate fetching user data from backend
    // In a real scenario, the backend would return the actual earnings, ads viewed, and referral link
    fetch('/api/login', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify(currentUser),
    })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                currentUser.earnings = data.user.earnings;
                currentUser.adsViewed = data.user.adsViewed;
                currentUser.referralLink = data.user.referralLink;
                updateDashboard();
                document.getElementById('auth-section').style.display = 'none';
                document.getElementById('dashboard').style.display = 'block';
            } else {
                alert('Login failed: ' + data.message);
            }
        })
        .catch(error => {
            console.error('Error during Telegram login:', error);
            alert('An error occurred during login.');
        });
}

// Function to update the dashboard with user data
function updateDashboard() {
    if (currentUser) {
        document.getElementById('username').textContent = currentUser.first_name || currentUser.username;
        document.getElementById('user-earnings').textContent = currentUser.earnings.toFixed(4);
        document.getElementById('ads-viewed').textContent = currentUser.adsViewed;
        document.getElementById('referral-link').textContent = currentUser.referralLink;
    }
}

// Event listener for "View Ad" button
document.getElementById('view-ad-button').addEventListener('click', () => {
    document.getElementById('ad-display').style.display = 'block';
    // In a real application, you would fetch an ad from the backend here.
});

// Event listener for "Close Ad" button
document.getElementById('close-ad-button').addEventListener('click', () => {
    document.getElementById('ad-display').style.display = 'none';

    // Simulate ad viewing and earning
    fetch('/api/view_ad', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({ userId: currentUser.id }),
    })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                currentUser.earnings = data.user.earnings;
                currentUser.adsViewed = data.user.adsViewed;
                updateDashboard();
                alert('Ad viewed! You earned 0.0001.');
            } else {
                alert('Failed to view ad: ' + data.message);
            }
        })
        .catch(error => {
            console.error('Error viewing ad:', error);
            alert('An error occurred while viewing the ad.');
        });
});

// Event listener for "Withdraw" button
document.getElementById('withdraw-button').addEventListener('click', () => {
    document.getElementById('withdrawal-form').style.display = 'block';
});

// Event listener for "Submit Withdrawal" button
document.getElementById('submit-withdrawal').addEventListener('click', () => {
    const tonWalletAddress = document.getElementById('ton-wallet-address').value;

    if (!tonWalletAddress) {
        alert('Please enter your TON wallet address.');
        return;
    }

    // In a real application, send withdrawal request to backend
    fetch('/api/withdraw', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({ userId: currentUser.id, tonWalletAddress: tonWalletAddress }),
    })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                currentUser.earnings = data.user.earnings; // Update earnings after withdrawal
                updateDashboard();
                document.getElementById('withdrawal-form').style.display = 'none';
                alert('Withdrawal request submitted successfully!');
            } else {
                alert('Withdrawal failed: ' + data.message);
            }
        })
        .catch(error => {
            console.error('Error during withdrawal:', error);
            alert('An error occurred during withdrawal.');
        });
});

// Initial dashboard update (will be hidden until login)
updateDashboard();