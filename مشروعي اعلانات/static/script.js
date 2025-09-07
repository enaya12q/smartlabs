let currentUser = null; // Stores user data after Telegram login

// Function to handle Telegram authentication
function onTelegramAuth(user) {
    console.log("Telegram User Data:", user);

    // Send user data to backend for verification and session management
    fetch('/api/login', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify(user), // Send the raw user object from Telegram
    })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                currentUser = data.user; // Store the user data returned from the backend
                localStorage.setItem('currentUser', JSON.stringify(currentUser)); // Store in localStorage
                window.location.href = '/dashboard'; // Redirect to the dashboard page
            } else {
                alert('Login failed: ' + data.message);
            }
        })
        .catch(error => {
            console.error('Error during Telegram login:', error);
            alert('An error occurred during login.');
        });
}

// Function to check login status and update navigation
function checkLoginStatus() {
    const storedUser = localStorage.getItem('currentUser');
    if (storedUser) {
        currentUser = JSON.parse(storedUser);
        updateNavigation();
    } else {
        // Try to fetch user data from session if not in localStorage (e.g., after refresh)
        fetch('/api/user_data')
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    currentUser = data.user;
                    localStorage.setItem('currentUser', JSON.stringify(currentUser));
                    updateNavigation();
                } else {
                    console.log("Not logged in or session expired.");
                    // Clear currentUser if backend says not authenticated
                    currentUser = null;
                    localStorage.removeItem('currentUser');
                    updateNavigation();
                }
            })
            .catch(error => {
                console.error('Error checking login status:', error);
                currentUser = null;
                localStorage.removeItem('currentUser');
                updateNavigation();
            });
    }
}

// Function to update the navigation bar
function updateNavigation() {
    const navDashboardLink = document.getElementById('nav-dashboard-link');
    if (navDashboardLink) {
        if (currentUser) {
            navDashboardLink.innerHTML = `<a href="/dashboard">Dashboard</a>`;
        } else {
            navDashboardLink.innerHTML = ''; // Clear the link if not logged in
        }
    }
}

// This function will be called on the dashboard page
function loadDashboardData() {
    fetch('/api/user_data') // A new endpoint to fetch user data for the dashboard
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                currentUser = data.user;
                localStorage.setItem('currentUser', JSON.stringify(currentUser)); // Update localStorage
                updateDashboardUI();
            } else {
                alert('Failed to load dashboard data: ' + data.message);
                window.location.href = '/'; // Redirect to home if data cannot be loaded
            }
        })
        .catch(error => {
            console.error('Error loading dashboard data:', error);
            alert('An error occurred while loading dashboard data.');
            window.location.href = '/'; // Redirect to home on error
        });
}

// Function to update the dashboard UI with user data
function updateDashboardUI() {
    if (currentUser) {
        document.getElementById('dashboard-username').textContent = currentUser.first_name || currentUser.username;
        document.getElementById('dashboard-user-earnings').textContent = currentUser.earnings.toFixed(4);
        document.getElementById('dashboard-ads-viewed').textContent = currentUser.adsViewed;

        const referralLinkElement = document.getElementById('dashboard-referral-link');
        if (referralLinkElement) {
            referralLinkElement.innerHTML = `<a href="${currentUser.referralLink}" target="_blank">${currentUser.referralLink}</a> <button id="copy-referral-link">Copy</button>`;
            document.getElementById('copy-referral-link').addEventListener('click', () => {
                navigator.clipboard.writeText(currentUser.referralLink).then(() => {
                    alert('Referral link copied to clipboard!');
                }).catch(err => {
                    console.error('Failed to copy referral link: ', err);
                });
            });
        }
    }
}

// Event listener for "Watch Ad" button on dashboard
document.addEventListener('DOMContentLoaded', () => {
    checkLoginStatus(); // Check login status on every page load

    if (document.getElementById('dashboard-view-ad-button')) {
        loadDashboardData(); // Load data when dashboard is accessed

        document.getElementById('dashboard-view-ad-button').addEventListener('click', () => {
            document.getElementById('dashboard-ad-display').style.display = 'block';
            const closeAdButton = document.getElementById('dashboard-close-ad-button');
            closeAdButton.disabled = true; // Disable close button initially

            // Simulate ad viewing time
            setTimeout(() => {
                closeAdButton.disabled = false; // Enable close button after 5 seconds
                alert('You can now close the ad.');
            }, 5000); // 5 seconds

            // In a real application, you would fetch an ad from the backend here.
            // For now, we'll just show the static ad content.
        });

        // Event listener for "Close Ad" button on dashboard
        document.getElementById('dashboard-close-ad-button').addEventListener('click', () => {
            document.getElementById('dashboard-ad-display').style.display = 'none';
            document.getElementById('dashboard-close-ad-button').disabled = false; // Ensure button is re-enabled for next ad

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
                        updateDashboardUI();
                        alert('Ad viewed! Your stats have been updated!');
                    } else {
                        alert('Failed to view ad: ' + data.message);
                    }
                })
                .catch(error => {
                    console.error('Error viewing ad:', error);
                    alert('An error occurred while viewing the ad.');
                });
        });

        // Add a logout button for testing purposes
        const logoutButton = document.createElement('button');
        logoutButton.textContent = 'Logout';
        logoutButton.id = 'logout-button';
        logoutButton.addEventListener('click', () => {
            localStorage.removeItem('currentUser');
            fetch('/api/logout', { method: 'POST' }) // Assuming a logout endpoint exists or will be created
                .then(() => {
                    currentUser = null;
                    updateNavigation();
                    window.location.href = '/';
                })
                .catch(error => {
                    console.error('Error during logout:', error);
                    alert('An error occurred during logout.');
                });
        });
        document.querySelector('main').appendChild(logoutButton); // Add logout button to main content

        // Event listener for "Withdraw Earnings" button on dashboard
        document.getElementById('dashboard-withdraw-button').addEventListener('click', () => {
            document.getElementById('dashboard-withdrawal-form').style.display = 'block';
        });

        // Event listener for "Submit Withdrawal" button on dashboard
        document.getElementById('dashboard-submit-withdrawal').addEventListener('click', () => {
            const tonWalletAddress = document.getElementById('dashboard-ton-wallet-address').value;

            if (!tonWalletAddress) {
                alert('Please enter your TON wallet address.');
                return;
            }

            fetch('/api/withdraw', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ tonWalletAddress: tonWalletAddress }), // userId is from session on backend
            })
                .then(response => response.json())
                .then(data => {
                    if (data.success) {
                        currentUser.earnings = data.user.earnings; // Update earnings after withdrawal
                        localStorage.setItem('currentUser', JSON.stringify(currentUser)); // Update localStorage
                        updateDashboardUI();
                        document.getElementById('dashboard-withdrawal-form').style.display = 'none';
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
    }
});