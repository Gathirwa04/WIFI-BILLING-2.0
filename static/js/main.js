document.addEventListener('DOMContentLoaded', function () {
    // Poll for payment status
    const paymentForm = document.getElementById('payment-form');
    const statusDiv = document.getElementById('payment-status');
    const loadingDiv = document.getElementById('loading');

    if (paymentForm) {
        paymentForm.addEventListener('submit', function (e) {
            e.preventDefault();

            const formData = new FormData(paymentForm);
            const submitBtn = paymentForm.querySelector('button[type="submit"]');

            submitBtn.disabled = true;
            submitBtn.innerText = 'Processing...';
            loadingDiv.classList.remove('hidden');
            statusDiv.innerHTML = 'Sending STK Push to phone...';
            statusDiv.style.color = 'var(--primary)';

            fetch('/stk_push', {
                method: 'POST',
                body: formData
            })
                .then(response => response.json())
                .then(data => {
                    if (data.success) {
                        statusDiv.innerHTML = 'Check your phone to enter PIN...<br><br><small>Test Mode: Waiting for callback...</small>';

                        // Inject Simulation Button
                        const simBtn = document.createElement('button');
                        simBtn.innerText = "Simulate Success (Localhost Only)";
                        simBtn.type = "button";
                        simBtn.className = "btn btn-secondary";
                        simBtn.style.marginTop = "10px";
                        simBtn.style.fontSize = "0.8rem";
                        simBtn.onclick = function () {
                            fetch(`/test/simulate_payment/${data.checkout_request_id}`)
                                .then(r => r.json())
                                .then(d => {
                                    statusDiv.innerHTML = d.message;
                                });
                        };
                        statusDiv.appendChild(simBtn);

                        // Start polling
                        pollPaymentStatus(data.checkout_request_id);
                    } else {
                        statusDiv.innerText = 'Error: ' + data.message;
                        statusDiv.style.color = 'var(--danger)';
                        submitBtn.disabled = false;
                        submitBtn.innerText = 'Pay Now';
                        loadingDiv.classList.add('hidden');
                    }
                })
                .catch(error => {
                    console.error('Error:', error);
                    statusDiv.innerText = 'An error occurred.';
                    statusDiv.style.color = 'var(--danger)';
                    submitBtn.disabled = false;
                    submitBtn.innerText = 'Pay Now';
                    loadingDiv.classList.add('hidden');
                });
        });
    }
});

function pollPaymentStatus(checkoutRequestId) {
    const statusDiv = document.getElementById('payment-status');
    let attempts = 0;
    const maxAttempts = 60; // 60 * 2 = 120 seconds timeout

    const interval = setInterval(() => {
        attempts++;
        if (attempts > maxAttempts) {
            clearInterval(interval);
            statusDiv.innerText = 'Payment timeout. Please try again.';
            statusDiv.style.color = 'var(--danger)';
            document.getElementById('loading').classList.add('hidden');
            document.querySelector('button[type="submit"]').disabled = false;
            document.querySelector('button[type="submit"]').innerText = 'Pay Now';
            return;
        }

        fetch(`/check_payment/${checkoutRequestId}`)
            .then(response => response.json())
            .then(data => {
                if (data.status === 'Completed') {
                    clearInterval(interval);
                    statusDiv.innerText = 'Payment Successful! Redirecting...';
                    statusDiv.style.color = 'var(--success)';
                    setTimeout(() => {
                        window.location.href = `/success?code=${data.access_code}`;
                    }, 1000);
                } else if (data.status === 'Failed') {
                    clearInterval(interval);
                    statusDiv.innerText = 'Payment Failed or Cancelled.';
                    statusDiv.style.color = 'var(--danger)';
                    document.getElementById('loading').classList.add('hidden');
                    document.querySelector('button[type="submit"]').disabled = false;
                    document.querySelector('button[type="submit"]').innerText = 'Pay Now';
                }
                // If Pending, continue polling
            });
    }, 2000); // Check every 2 seconds
}
