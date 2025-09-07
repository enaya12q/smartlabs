document.addEventListener('DOMContentLoaded', () => {
    const usersTableBody = document.querySelector('#users-table tbody');
    const withdrawalsTableBody = document.querySelector('#withdrawals-table tbody');
    const userSearchInput = document.getElementById('user-search-input');
    const userSearchButton = document.getElementById('user-search-button');
    const withdrawalSearchInput = document.getElementById('withdrawal-search-input');
    const withdrawalSearchButton = document.getElementById('withdrawal-search-button');
    const adminLogoutButton = document.getElementById('admin-logout-button');

    async function fetchUsers(searchTerm = '') {
        try {
            const response = await fetch(`/api/admin/users?search=${searchTerm}`);
            const data = await response.json();
            if (data.success) {
                renderUsers(data.users);
            } else {
                alert('Failed to fetch users: ' + data.message);
            }
        } catch (error) {
            console.error('Error fetching users:', error);
            alert('An error occurred while fetching users.');
        }
    }

    function renderUsers(users) {
        usersTableBody.innerHTML = '';
        users.forEach(user => {
            const row = usersTableBody.insertRow();
            row.insertCell().textContent = user.id;
            row.insertCell().textContent = user.telegram_id;
            row.insertCell().textContent = user.username || 'N/A';
            row.insertCell().textContent = user.first_name || 'N/A';
            row.insertCell().textContent = user.earnings.toFixed(4);
            row.insertCell().textContent = user.ads_viewed;
            row.insertCell().textContent = user.referral_code;
            row.insertCell().textContent = user.referrer_id || 'N/A';
            row.insertCell().textContent = new Date(user.created_at).toLocaleString();
        });
    }

    async function fetchWithdrawals(searchTerm = '') {
        try {
            const response = await fetch(`/api/admin/withdrawals?search=${searchTerm}`);
            const data = await response.json();
            if (data.success) {
                renderWithdrawals(data.withdrawals);
            } else {
                alert('Failed to fetch withdrawals: ' + data.message);
            }
        } catch (error) {
            console.error('Error fetching withdrawals:', error);
            alert('An error occurred while fetching withdrawals.');
        }
    }

    function renderWithdrawals(withdrawals) {
        withdrawalsTableBody.innerHTML = '';
        withdrawals.forEach(withdrawal => {
            const row = withdrawalsTableBody.insertRow();
            row.insertCell().textContent = withdrawal.id;
            row.insertCell().textContent = withdrawal.user_id;
            row.insertCell().textContent = withdrawal.username || 'N/A'; // Assuming username is joined from users table
            row.insertCell().textContent = withdrawal.amount.toFixed(4);
            row.insertCell().textContent = withdrawal.ton_wallet_address;
            row.insertCell().textContent = withdrawal.status;
            row.insertCell().textContent = new Date(withdrawal.created_at).toLocaleString();

            const actionsCell = row.insertCell();
            if (withdrawal.status === 'pending') {
                const approveButton = document.createElement('button');
                approveButton.textContent = 'Approve';
                approveButton.classList.add('approve-button');
                approveButton.addEventListener('click', () => updateWithdrawalStatus(withdrawal.id, 'completed'));
                actionsCell.appendChild(approveButton);

                const rejectButton = document.createElement('button');
                rejectButton.textContent = 'Reject';
                rejectButton.classList.add('reject-button');
                rejectButton.addEventListener('click', () => updateWithdrawalStatus(withdrawal.id, 'rejected'));
                actionsCell.appendChild(rejectButton);
            } else {
                actionsCell.textContent = 'N/A';
            }
        });
    }

    async function updateWithdrawalStatus(withdrawalId, status) {
        try {
            const response = await fetch(`/api/admin/withdrawals/${withdrawalId}/${status}`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
            });
            const data = await response.json();
            if (data.success) {
                alert(`Withdrawal ${withdrawalId} ${status} successfully.`);
                fetchWithdrawals(); // Refresh withdrawals table
            } else {
                alert(`Failed to ${status} withdrawal ${withdrawalId}: ` + data.message);
            }
        } catch (error) {
            console.error(`Error updating withdrawal status for ${withdrawalId}:`, error);
            alert('An error occurred while updating withdrawal status.');
        }
    }

    // Event Listeners for search
    userSearchButton.addEventListener('click', () => fetchUsers(userSearchInput.value));
    withdrawalSearchButton.addEventListener('click', () => fetchWithdrawals(withdrawalSearchInput.value));

    // Initial load
    fetchUsers();
    fetchWithdrawals();

    // Admin Logout
    adminLogoutButton.addEventListener('click', () => {
        localStorage.removeItem('currentUser'); // Clear user data from local storage
        fetch('/api/logout', { method: 'POST' }) // Call the logout endpoint
            .then(() => {
                window.location.href = '/'; // Redirect to home page
            })
            .catch(error => {
                console.error('Error during admin logout:', error);
                alert('An error occurred during logout.');
            });
    });
});