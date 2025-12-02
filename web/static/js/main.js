// Wait for the DOM to be fully loaded before attaching event listeners
document.addEventListener('DOMContentLoaded', () => {

  // Get all the elements we need to interact with
  const panelContainer = document.getElementById('side-panel-container');
  const toggleBtn = document.getElementById('toggle-btn');
  const closeBtnInside = document.getElementById('close-btn-inside');
  const openIcon = document.getElementById('open-icon');
  const closeIcon = document.getElementById('close-icon');

  // State variable to track if the panel is open
  let isOpen = false;

  // Function to open the panel
  function openPanel() {
    panelContainer.classList.remove('translate-x-full');
    panelContainer.classList.add('translate-x-0');
    openIcon.classList.add('hidden');
    closeIcon.classList.remove('hidden');
    isOpen = true;
  }

  // Function to close the panel
  function closePanel() {
    panelContainer.classList.add('translate-x-full');
    panelContainer.classList.remove('translate-x-0');
    openIcon.classList.remove('hidden');
    closeIcon.classList.add('hidden');
    isOpen = false;
  }

  // Main toggle function
  function togglePanel() {
    if (isOpen) {
      closePanel();
    } else {
      openPanel();
    }
  }

  // Attach event listeners
  toggleBtn.addEventListener('click', togglePanel);
  closeBtnInside.addEventListener('click', closePanel);
});