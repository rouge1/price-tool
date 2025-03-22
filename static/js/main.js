async function loadPriceHistory(websiteId) {
    try {
        const response = await fetch(`/price-history/${websiteId}`);
        const data = await response.json();
        
        if (!Array.isArray(data) || data.length === 0) {
            return;
        }

        const ctx = document.getElementById(`priceChart${websiteId}`).getContext('2d');
        const currency = data[0].currency;
        
        new Chart(ctx, {
            type: 'line',
            data: {
                labels: data.map(d => new Date(d.date).toLocaleDateString()),
                datasets: [{
                    label: 'Price History',
                    data: data.map(d => d.price),
                    borderColor: '#0d6efd',
                    backgroundColor: 'rgba(13, 110, 253, 0.1)',
                    tension: 0.1,
                    fill: true
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        display: false
                    },
                    title: {
                        display: true,
                        text: '30-Day Price History'
                    },
                    tooltip: {
                        callbacks: {
                            label: (context) => {
                                const value = context.parsed.y;
                                return `${currency}${value >= 100 ? 
                                    value.toLocaleString('en-US', {maximumFractionDigits: 0}) : 
                                    value.toLocaleString('en-US', {minimumFractionDigits: 2})}`;
                            }
                        }
                    }
                },
                scales: {
                    y: {
                        ticks: {
                            callback: (value) => {
                                return `${currency}${value >= 100 ? 
                                    value.toLocaleString('en-US', {maximumFractionDigits: 0}) : 
                                    value.toLocaleString('en-US', {minimumFractionDigits: 2})}`;
                            }
                        }
                    }
                }
            }
        });
    } catch (error) {
        console.error('Error loading price history:', error);
    }
}

document.addEventListener('DOMContentLoaded', function() {
    // Initialize price history charts
    document.querySelectorAll('[id^="priceChart"]').forEach(canvas => {
        const websiteId = canvas.id.replace('priceChart', '');
        loadPriceHistory(websiteId);
    });

    // Add Item Form Handling
    const addItemForm = document.getElementById('addItemForm');
    if (addItemForm) {
        addItemForm.addEventListener('submit', async function(e) {
            e.preventDefault();
            const url = document.getElementById('itemUrl').value;
            const errorMessage = document.getElementById('errorMessage');
            const submitButton = document.getElementById('submitButton');

            errorMessage.classList.add('d-none');
            submitButton.disabled = true;
            submitButton.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Adding...';

            if (url) {
                try {
                    const response = await fetch('/add-item', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                        },
                        body: JSON.stringify({ url: url })
                    });
                    
                    const data = await response.json();
                    
                    if (response.ok) {
                        const modal = bootstrap.Modal.getInstance(document.getElementById('addItemModal'));
                        modal.hide();
                        window.location.reload();
                    } else {
                        errorMessage.textContent = data.error || 'Error adding item';
                        errorMessage.classList.remove('d-none');
                    }
                } catch (error) {
                    console.error('Error:', error);
                    errorMessage.textContent = 'Network error occurred. Please try again.';
                    errorMessage.classList.remove('d-none');
                } finally {
                    submitButton.disabled = false;
                    submitButton.innerHTML = 'Add Item';
                }
            }
        });
    }

    // Clear error message when modal is hidden
    const addItemModal = document.getElementById('addItemModal');
    if (addItemModal) {
        addItemModal.addEventListener('hidden.bs.modal', function () {
            document.getElementById('errorMessage').classList.add('d-none');
            document.getElementById('itemUrl').value = '';
            document.getElementById('submitButton').disabled = false;
            document.getElementById('submitButton').innerHTML = 'Add Item';
        });
    }

    // Delete Item Handling
    let urlToDelete = '';
    window.confirmDelete = function(url) {
        urlToDelete = url;
        const deleteModal = new bootstrap.Modal(document.getElementById('deleteModal'));
        deleteModal.show();
    };

    const confirmDeleteBtn = document.getElementById('confirmDeleteBtn');
    if (confirmDeleteBtn) {
        confirmDeleteBtn.addEventListener('click', async function() {
            try {
                const response = await fetch('/delete-item', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({ url: urlToDelete })
                });
                
                if (response.ok) {
                    window.location.reload();
                } else {
                    alert('Error deleting item');
                }
            } catch (error) {
                console.error('Error:', error);
                alert('Error deleting item');
            }
        });
    }

    // Edit Description Handling
    const editModal = document.getElementById('editDescriptionModal');
    const editForm = document.getElementById('editDescriptionForm');
    const descInput = document.getElementById('itemDescription');
    const urlInput = document.getElementById('itemUrl');
    const errorMessage = document.getElementById('editErrorMessage');
    
    if (editModal && editForm) {
        // When edit button is clicked
        document.querySelectorAll('.edit-description').forEach(button => {
            button.addEventListener('click', function() {
                const url = this.dataset.url;
                const description = this.dataset.description;
                descInput.value = description;
                urlInput.value = url;
                errorMessage.classList.add('d-none');
            });
        });
        
        // When save button is clicked
        const saveDescriptionBtn = document.getElementById('saveDescriptionBtn');
        if (saveDescriptionBtn) {
            saveDescriptionBtn.addEventListener('click', async function() {
                if (!descInput.value.trim()) {
                    errorMessage.textContent = 'Description cannot be empty';
                    errorMessage.classList.remove('d-none');
                    return;
                }
                
                try {
                    const response = await fetch('/update-description', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                        },
                        body: JSON.stringify({
                            url: urlInput.value,
                            description: descInput.value.trim()
                        })
                    });
                    
                    if (response.ok) {
                        window.location.reload();
                    } else {
                        const data = await response.json();
                        errorMessage.textContent = data.error || 'Error updating description';
                        errorMessage.classList.remove('d-none');
                    }
                } catch (error) {
                    console.error('Error:', error);
                    errorMessage.textContent = 'Network error occurred';
                    errorMessage.classList.remove('d-none');
                }
            });
        }
    }
}); 