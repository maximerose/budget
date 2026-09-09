document.addEventListener("DOMContentLoaded", () => {
    // =========================================================================
    // 1. GESTION DES NOTIFICATIONS (TOASTS)
    // =========================================================================
    const messages = document.querySelectorAll("#django-messages > div");
    messages.forEach((msg) => {
        const text = msg.getAttribute("data-message");
        const bgColor = msg.getAttribute("data-tag") === "error" ? "#f43f5e" : "#10b981"; 

        Toastify({
            text: text, duration: 2000, gravity: "bottom", position: "center",
            style: { background: bgColor, borderRadius: "9999px", padding: "8px 16px", fontSize: "0.875rem", color: "#020617", fontWeight: "600", boxShadow: "0 4px 15px -3px rgba(0, 0, 0, 0.3)", marginBottom: "5rem" }
        }).showToast();
    });

    // =========================================================================
    // 2. ANIMATION DU LOGO AU SCROLL (MOBILE)
    // =========================================================================
    const logo = document.getElementById('brand-logo');
    if (logo) {
        window.addEventListener('scroll', () => {
            if (window.innerWidth < 640) {
                const isScrolled = window.scrollY > 20;
                logo.style.transform = isScrolled ? 'scale(0)' : 'scale(1)';
                logo.style.width = isScrolled ? '0px' : 'auto';
                logo.style.opacity = isScrolled ? '0' : '1';
            } else {
                logo.style.transform = ''; logo.style.width = ''; logo.style.opacity = '';
            }
        });
    }
});

// =========================================================================
// 3. INTERCEPTION DES CONFIRMATIONS HTMX (SWEETALERT2)
// =========================================================================
document.body.addEventListener('htmx:confirm', (evt) => {
    if (!evt.detail.question) return;
    evt.preventDefault();

    Swal.fire({
        title: 'Êtes-vous sûr ?', text: evt.detail.question, icon: 'warning', showCancelButton: true,
        confirmButtonColor: '#f43f5e', cancelButtonColor: '#1e293b', confirmButtonText: 'Oui, continuer', cancelButtonText: 'Annuler',
        background: '#0f172a', color: '#f1f5f9',      
        customClass: { popup: 'border border-slate-700 rounded-[1.5rem]', confirmButton: 'font-bold rounded-xl px-5 py-2.5', cancelButton: 'font-bold rounded-xl px-5 py-2.5' }
    }).then((result) => {
        if (result.isConfirmed) evt.detail.issueRequest(true);
    });
});

// =========================================================================
// 4. FORMATAGE ET RESIZE DU CHAMP MONTANT (QUICK TRANSACTION)
// =========================================================================
function formatCurrency(inputEl, hiddenId) {
    let raw = inputEl.value.replace(',', '.').replace(/[^0-9.-]/g, '');
    const hiddenEl = document.getElementById(hiddenId);
    if (hiddenEl) hiddenEl.value = raw;
}

function formatCurrencyOnBlur(inputEl, hiddenId) {
    let hiddenEl = document.getElementById(hiddenId);
    if (!hiddenEl) return;
    let val = parseFloat(hiddenEl.value);
    if (!isNaN(val)) {
        inputEl.value = val.toFixed(2);
    }
}

// Mise à jour automatique des barres de progression
function syncProgressBars() {
    document.querySelectorAll('.progress-bar-fill').forEach((el) => {
        const val = el.getAttribute('data-progress') || '0';
        el.style.setProperty('--progress-val', val);
    });
}

document.addEventListener('DOMContentLoaded', syncProgressBars);
document.body.addEventListener('htmx:afterSettle', syncProgressBars);

// =========================================================================
// 5. TUTORIEL INTERACTIF & SPOTLIGHT OVERLAY
// =========================================================================
function highlightElement(selector, fallbackUrl) {
    const target = document.querySelector(selector);
    
    // Si l'élément est hors écran ou dans une modale dédiée non présente
    if (!target) {
        if (fallbackUrl) window.location.href = fallbackUrl;
        return;
    }

    // 1. Création de l'overlay sombre s'il n'existe pas
    let overlay = document.getElementById('tour-overlay');
    if (!overlay) {
        overlay = document.createElement('div');
        overlay.id = 'tour-overlay';
        overlay.className = 'fixed inset-0 bg-slate-950/80 z-40 transition-opacity duration-300 pointer-events-auto cursor-pointer';
        overlay.onclick = dismissHighlight;
        document.body.appendChild(overlay);
    }

    // 2. Faire défiler jusqu'à l'élément et appliquer l'effet Spotlight
    target.scrollIntoView({ behavior: 'smooth', block: 'center' });
    
    target.classList.add('relative', 'z-50', 'ring-4', 'ring-brand', 'ring-offset-4', 'ring-offset-slate-900', 'rounded-xl', 'transition-all');
    target.dataset.spotlight = "true";
}

function dismissHighlight() {
    const overlay = document.getElementById('tour-overlay');
    if (overlay) overlay.remove();

    document.querySelectorAll('[data-spotlight="true"]').forEach((el) => {
        el.classList.remove('relative', 'z-50', 'ring-4', 'ring-brand', 'ring-offset-4', 'ring-offset-slate-900');
        delete el.dataset.spotlight;
    });
}