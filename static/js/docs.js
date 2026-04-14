// Highlight all code blocks
hljs.highlightAll();

// Copy snippet functionality
function copySnippet(btn) {
    const code = btn.previousElementSibling.innerText;
    navigator.clipboard.writeText(code).then(() => {
        const originalText = btn.innerText;
        btn.innerText = 'Copied!';
        setTimeout(() => btn.innerText = originalText, 2000);
    });
}

// Expose globally for onclick handlers
window.copySnippet = copySnippet;

// Smooth scrolling for sidebar links
document.querySelectorAll('.sidebar-link').forEach(anchor => {
    anchor.addEventListener('click', function (e) {
        e.preventDefault();
        document.querySelector(this.getAttribute('href')).scrollIntoView({
            behavior: 'smooth'
        });
    });
});
