document.addEventListener("DOMContentLoaded", function () {
    console.log("TranscribeHub is ready!");
});


// Redirect to index.html after form submission
function redirectToIndex(event) {
    event.preventDefault(); // Prevent the default form submission
    window.location.href = "index.html"; // Redirect to index.html
}

// Initialize Google Sign-In
function initializeGoogleSignIn() {
    google.accounts.id.initialize({
        client_id: 'YOUR_GOOGLE_CLIENT_ID', // Replace with your actual Google Client ID
        callback: handleGoogleSignIn,
    });

    // Render the Google Sign-In button
    google.accounts.id.renderButton(
        document.getElementById('google-signin'),
        { theme: 'outline', size: 'large' } // Customize the button
    );
}

// Handle Google Sign-In response
function handleGoogleSignIn(response) {
    console.log('Google Sign-In Response:', response);
    const user = decodeJWT(response.credential);
    console.log('User Info:', user);
    // Redirect to the dashboard or home page
    window.location.href = 'index.html';
}

// Decode JWT token
function decodeJWT(token) {
    const base64Url = token.split('.')[1];
    const base64 = base64Url.replace(/-/g, '+').replace(/_/g, '/');
    return JSON.parse(atob(base64));
}

// Initialize Google SDK on page load
window.onload = () => {
    initializeGoogleSignIn();
};



document.addEventListener('DOMContentLoaded', function () {
    const emailInput = document.getElementById('email');
    const submitButton = document.querySelector('.cta-button');
    
    // Simple email validation on submit
    submitButton.addEventListener('click', function(event) {
        const email = emailInput.value;
        
        if (!email || !validateEmail(email)) {
            event.preventDefault();
            alert('Please enter a valid email address.');
        }
    });

    function validateEmail(email) {
        const re = /^[a-zA-Z0-9._-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,6}$/;
        return re.test(email);
    }
});
