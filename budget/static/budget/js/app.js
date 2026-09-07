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